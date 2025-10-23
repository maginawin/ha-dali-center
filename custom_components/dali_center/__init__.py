"""The Dali Center integration."""

from __future__ import annotations

import logging

import async_timeout
from PySrDaliGateway import DaliGateway
from PySrDaliGateway.exceptions import DaliGatewayError

from homeassistant.components.persistent_notification import async_create
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .const import CONF_GATEWAY_LEGACY, CONF_SERIAL_NUMBER, DOMAIN, MANUFACTURER
from .helper import migrate_gateway_config
from .types import DaliCenterConfigEntry, DaliCenterData

_PLATFORMS: list[Platform] = [
    Platform.LIGHT,
    Platform.SENSOR,
    Platform.BUTTON,
    Platform.EVENT,
    Platform.SWITCH,
    Platform.SCENE,
]
_LOGGER = logging.getLogger(__name__)


def _setup_dependency_logging() -> None:
    """Set up PySrDaliGateway logging to match integration level."""
    current_logger = logging.getLogger(__name__)
    current_level = current_logger.getEffectiveLevel()

    gateway_logger = logging.getLogger("PySrDaliGateway")
    gateway_logger.setLevel(current_level)


async def _notify_user_error(
    hass: HomeAssistant, title: str, message: str, gw_sn: str = ""
) -> None:
    """Create persistent notification for user-visible errors."""
    notification_id = f"dali_center_{gw_sn}_{hash(title + message)}"
    gw_part = f" ({gw_sn})" if gw_sn else ""
    full_title = f"DALI Center{gw_part}: {title}"

    async_create(
        hass,
        message,
        title=full_title,
        notification_id=notification_id,
    )


async def async_migrate_entry(
    hass: HomeAssistant, entry: DaliCenterConfigEntry
) -> bool:
    """Migrate old entry format to new format."""
    if entry.version == 1:
        old_data = dict(entry.data)

        if CONF_GATEWAY_LEGACY in old_data:
            _LOGGER.info("Migrating gateway configuration from legacy format")
            new_data = migrate_gateway_config(old_data)

            hass.config_entries.async_update_entry(
                entry,
                data=new_data,
                version=2,
            )
            _LOGGER.info("Migration to version 2 completed successfully")
        else:
            hass.config_entries.async_update_entry(entry, version=2)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: DaliCenterConfigEntry) -> bool:
    """Set up dali_center from a config entry using paho-mqtt."""
    _setup_dependency_logging()

    gateway = DaliGateway(
        gw_sn=entry.data[CONF_SERIAL_NUMBER],
        gw_ip=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        username=entry.data[CONF_USERNAME],
        passwd=entry.data[CONF_PASSWORD],
        name=entry.data[CONF_NAME],
    )
    gw_sn = gateway.gw_sn
    is_tls = gateway.is_tls

    _LOGGER.info("Setting up DALI Center gateway %s (TLS: %s)", gw_sn, is_tls)

    try:
        async with async_timeout.timeout(30):
            await gateway.connect()
    except DaliGatewayError as exc:
        _LOGGER.exception("Error connecting to gateway %s", gw_sn)
        await _notify_user_error(hass, "Connection Failed", str(exc), gw_sn)
        raise ConfigEntryNotReady(
            "You can try to delete the gateway and add it again"
        ) from exc
    except TimeoutError as exc:
        _LOGGER.warning("Overall timeout connecting to gateway %s", gw_sn)
        await _notify_user_error(
            hass,
            "Connection Timeout",
            f"Timeout while connecting to DALI Center gateway. {exc}",
            gw_sn,
        )

    try:
        version = await gateway.get_version()
    except DaliGatewayError as exc:
        _LOGGER.warning("Failed to get gateway %s version: %s", gw_sn, exc)
        await _notify_user_error(hass, "Version Query Failed", str(exc), gw_sn)
        version = None

    if version:
        _LOGGER.info(
            "Gateway %s version - Software: %s, Firmware: %s",
            gw_sn,
            version.get("software"),
            version.get("firmware"),
        )

    dev_reg = dr.async_get(hass)
    dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, gw_sn)},
        manufacturer=MANUFACTURER,
        name=f"{gateway.name} (Secure)" if is_tls else gateway.name,
        model="SR-GW-EDA",
        sw_version=version["software"] if version else None,
        hw_version=version["firmware"] if version else None,
        serial_number=gw_sn,
    )

    try:
        devices = await gateway.discover_devices()
    except DaliGatewayError as exc:
        _LOGGER.warning("Failed to discover devices on gateway %s: %s", gw_sn, exc)
        devices = []

    try:
        groups = await gateway.discover_groups()
    except DaliGatewayError as exc:
        _LOGGER.warning("Failed to discover groups on gateway %s: %s", gw_sn, exc)
        groups = []

    try:
        scenes = await gateway.discover_scenes()
    except DaliGatewayError as exc:
        _LOGGER.warning("Failed to discover scenes on gateway %s: %s", gw_sn, exc)
        scenes = []

    entry.runtime_data = DaliCenterData(
        gateway=gateway,
        devices=devices,
        groups=groups,
        scenes=scenes,
    )

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    _LOGGER.info(
        "DALI Center gateway %s setup completed successfully "
        "(%d devices, %d groups, %d scenes)",
        gw_sn,
        len(devices),
        len(groups),
        len(scenes),
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: DaliCenterConfigEntry) -> bool:
    """Unload a config entry."""
    gateway = entry.runtime_data.gateway
    _LOGGER.info("Disconnecting from gateway %s", gateway.gw_sn)

    try:
        await gateway.disconnect()
    except DaliGatewayError as exc:
        _LOGGER.exception("Error disconnecting from gateway %s", gateway.gw_sn)
        await _notify_user_error(hass, "Disconnection Failed", str(exc), gateway.gw_sn)

    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
