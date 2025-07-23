"""The Dali Center integration."""

from __future__ import annotations

import asyncio
import logging

import async_timeout
from homeassistant.components.persistent_notification import async_create
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import DOMAIN, MANUFACTURER
from PySrDaliGateway import DaliGateway
from .types import DaliCenterConfigEntry, DaliCenterData

_PLATFORMS: list[Platform] = [
    Platform.LIGHT, Platform.SENSOR, Platform.BUTTON,
    Platform.EVENT, Platform.SWITCH
]
_LOGGER = logging.getLogger(__name__)


def _setup_dependency_logging() -> None:
    """Set up PySrDaliGateway logging to match integration level."""
    current_logger = logging.getLogger(__name__)
    current_level = current_logger.getEffectiveLevel()

    gateway_logger = logging.getLogger("PySrDaliGateway")
    gateway_logger.setLevel(current_level)

    _LOGGER.debug(
        "Configured PySrDaliGateway logging level to %s", current_level
    )


async def _notify_user_error(
    hass: HomeAssistant, title: str, message: str, gw_sn: str = ""
) -> None:
    """Create persistent notification for user-visible errors."""
    notification_id = f"dali_center_{gw_sn}_{hash(title + message)}"
    full_title = f"DALI Center{f" ({gw_sn})" if gw_sn else ""}: {title}"

    async_create(
        hass,
        message,
        title=full_title,
        notification_id=notification_id,
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: DaliCenterConfigEntry
) -> bool:
    """Set up dali_center from a config entry using paho-mqtt."""
    # Setup dependency logging first
    _setup_dependency_logging()

    gateway: DaliGateway = DaliGateway(entry.data["gateway"])
    gw_sn = gateway.gw_sn
    is_tls = entry.data["gateway"].get("is_tls", False)

    _LOGGER.info("Setting up DALI Center gateway %s (TLS: %s)", gw_sn, is_tls)

    try:
        async with async_timeout.timeout(30):
            connected = await gateway.connect()
            if not connected:
                _LOGGER.warning("Failed to connect to gateway %s", gw_sn)
                await _notify_user_error(
                    hass, "Connection Failed",
                    "Unable to connect to DALI Center gateway."
                    "Please check if the gateway is online and accessible",
                    gw_sn
                )
                raise ConfigEntryNotReady(
                    f"Failed to connect to gateway {gw_sn}")
            _LOGGER.info("Successfully connected to gateway %s", gw_sn)
    except asyncio.TimeoutError as exc:
        _LOGGER.warning("Timeout connecting to gateway %s", gw_sn)
        await _notify_user_error(
            hass, "Connection Timeout",
            "Timeout while connecting to DALI Center gateway. "
            "The gateway may be slow to respond or unreachable",
            gw_sn
        )
        raise ConfigEntryNotReady(
            f"Timeout connecting to gateway {gw_sn}") from exc

    def on_online_status(unique_id: str, available: bool) -> None:
        signal = f"dali_center_update_available_{unique_id}"
        hass.add_job(
            async_dispatcher_send, hass, signal, available
        )

    def on_device_status(unique_id: str, property_list: list) -> None:
        signal = f"dali_center_update_{unique_id}"
        hass.add_job(
            async_dispatcher_send, hass, signal, property_list
        )

    def on_energy_report(unique_id: str, energy: float) -> None:
        signal = f"dali_center_energy_update_{unique_id}"
        hass.add_job(
            async_dispatcher_send, hass, signal, energy
        )

    def on_sensor_on_off(unique_id: str, on_off: bool) -> None:
        signal = f"dali_center_sensor_on_off_{unique_id}"
        hass.add_job(
            async_dispatcher_send, hass, signal, on_off
        )

    gateway.on_online_status = on_online_status
    gateway.on_device_status = on_device_status
    gateway.on_energy_report = on_energy_report
    gateway.on_sensor_on_off = on_sensor_on_off

    version = await gateway.get_version()
    if version is None:
        _LOGGER.warning("Failed to get gateway %s version", gw_sn)
        await _notify_user_error(
            hass, "Version Query Failed",
            "Unable to retrieve version information from DALI Center gateway. "
            "The gateway may not be responding properly",
            gw_sn
        )
        raise ConfigEntryNotReady(
            f"Failed to get gateway {gw_sn} version")

    _LOGGER.info(
        "Gateway %s version - Software: %s, Firmware: %s",
        gw_sn, version.get("software"), version.get("firmware")
    )

    dev_reg = dr.async_get(hass)
    dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, gw_sn)},
        manufacturer=MANUFACTURER,
        name=f"{gateway.name} (Secure)" if is_tls else gateway.name,
        model="SR-GW-EDA",
        sw_version=version["software"],
        hw_version=version["firmware"],
        serial_number=gw_sn,
    )

    # Store gateway instance in runtime_data
    entry.runtime_data = DaliCenterData(gateway=gateway)

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    _LOGGER.info("DALI Center gateway %s setup completed successfully", gw_sn)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: DaliCenterConfigEntry
) -> bool:
    gateway = entry.runtime_data.gateway
    _LOGGER.info("Disconnecting from gateway %s", gateway.gw_sn)
    await gateway.disconnect()

    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
