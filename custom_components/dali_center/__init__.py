"""The Dali Center integration."""

from __future__ import annotations
from .types import DaliCenterConfigEntry
from PySrDaliGateway import DaliGateway
from .const import DOMAIN, MANUFACTURER

import asyncio
import logging

import async_timeout
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_send

_PLATFORMS: list[Platform] = [
    Platform.LIGHT, Platform.SENSOR, Platform.BUTTON,
    Platform.EVENT, Platform.SWITCH
]
_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, hass_config: dict) -> bool:
    # pylint: disable=unused-argument
    hass.data.setdefault(DOMAIN, {})

    # Gateway discovery and credential updates would be implemented here
    # if automatic discovery is needed in the future

    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: DaliCenterConfigEntry
) -> bool:
    """Set up dali_center from a config entry using paho-mqtt."""
    gateway: DaliGateway = DaliGateway(entry.data["gateway"])
    is_tls = entry.data["gateway"]["is_tls"]
    gw_sn = gateway.gw_sn

    try:
        async with async_timeout.timeout(30):
            connected = await gateway.connect()
            if not connected:
                raise ConfigEntryNotReady(
                    f"Failed to connect to gateway {gw_sn}")
    except asyncio.TimeoutError as exc:
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
        raise ConfigEntryNotReady(
            f"Failed to get gateway {gw_sn} version")

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

    # Store gateway instance
    hass.data[DOMAIN][entry.entry_id] = gateway

    # Register update listener
    entry.async_on_unload(entry.add_update_listener(update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if entry.entry_id in hass.data[DOMAIN]:
        gateway = hass.data[DOMAIN][entry.entry_id]
        await gateway.disconnect()
        del hass.data[DOMAIN][entry.entry_id]

    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    if entry.entry_id in hass.data[DOMAIN]:
        _LOGGER.debug("Updating gateway instance")
    else:
        _LOGGER.warning("No gateway instance found in hass.data[DOMAIN]")
