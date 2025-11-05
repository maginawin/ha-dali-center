"""The Dali Center integration."""

from __future__ import annotations

import asyncio
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
    current_logger = logging.getLogger(__name__)
    current_level = current_logger.getEffectiveLevel()

    gateway_logger = logging.getLogger("PySrDaliGateway")
    gateway_logger.setLevel(current_level)


async def _notify_user_error(
    hass: HomeAssistant, title: str, message: str, gw_sn: str = ""
) -> None:
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

            _ = hass.config_entries.async_update_entry(
                entry,
                data=new_data,
                version=2,
            )
            _LOGGER.info("Migration to version 2 completed successfully")
        else:
            _ = hass.config_entries.async_update_entry(entry, version=2)

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

    # Reduce timeout from 60s to 15s for local devices
    try:
        async with async_timeout.timeout(15):
            await gateway.connect()
    except DaliGatewayError as exc:
        _LOGGER.exception("Error connecting to gateway %s", gateway.gw_sn)
        await _notify_user_error(hass, "Connection Failed", str(exc), gateway.gw_sn)
        raise ConfigEntryNotReady(
            "You can try to delete the gateway and add it again"
        ) from exc
    except TimeoutError as exc:
        _LOGGER.warning("Timeout connecting to gateway %s", gateway.gw_sn)
        await _notify_user_error(
            hass,
            "Connection Timeout",
            f"Timeout while connecting to DALI Center gateway. {exc}",
            gateway.gw_sn,
        )
        raise ConfigEntryNotReady(
            f"Gateway {gateway.gw_sn} connection timeout"
        ) from exc

    # Parallel discovery: fetch devices, groups, scenes simultaneously
    try:
        devices, groups, scenes = await asyncio.gather(
            gateway.discover_devices(),
            gateway.discover_groups(),
            gateway.discover_scenes(),
        )
    except DaliGatewayError as exc:
        _LOGGER.exception("Error discovering entities for gateway %s", gateway.gw_sn)
        await _notify_user_error(hass, "Discovery Failed", str(exc), gateway.gw_sn)
        await gateway.disconnect()
        raise ConfigEntryNotReady(
            f"Failed to discover entities for gateway {gateway.gw_sn}"
        ) from exc

    entry.runtime_data = DaliCenterData(
        gateway=gateway,
        devices=devices,
        groups=groups,
        scenes=scenes,
    )

    # Get version in background (non-blocking)
    async def _fetch_version() -> None:
        try:
            version = await gateway.get_version()
            if version:
                dev_reg = dr.async_get(hass)
                device = dev_reg.async_get_device(identifiers={(DOMAIN, gateway.gw_sn)})
                if device:
                    _ = dev_reg.async_update_device(
                        device.id,
                        sw_version=version.get("software"),
                        hw_version=version.get("firmware"),
                    )
        except DaliGatewayError as exc:
            _LOGGER.warning("Failed to get gateway %s version: %s", gateway.gw_sn, exc)

    # Create gateway device entry (without version initially)
    dev_reg = dr.async_get(hass)
    _ = dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, gateway.gw_sn)},
        manufacturer=MANUFACTURER,
        name=gateway.name,
        model="SR-GW-EDA",
        serial_number=gateway.gw_sn,
    )

    # Fetch version in background
    _ = entry.async_create_background_task(
        hass, _fetch_version(), f"dali_version_{gateway.gw_sn}"
    )

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)
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
