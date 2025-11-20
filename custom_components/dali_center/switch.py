"""Platform for Dali Center illuminance sensor enable/disable switches."""

from __future__ import annotations

import logging
from typing import Any

from PySrDaliGateway import CallbackEventType, Device
from PySrDaliGateway.helper import is_illuminance_sensor

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, MANUFACTURER
from .types import DaliCenterConfigEntry

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DaliCenterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Dali Center illuminance sensor enable/disable switches."""
    devices = entry.runtime_data.devices

    async_add_entities(
        DaliCenterIlluminanceSensorEnableSwitch(device)
        for device in devices
        if is_illuminance_sensor(device.dev_type)
    )


class DaliCenterIlluminanceSensorEnableSwitch(SwitchEntity):
    """Representation of an Illuminance Sensor Enable/Disable Switch."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_has_entity_name = True
    _attr_name = "Sensor Enable"
    _attr_icon = "mdi:brightness-6"

    def __init__(self, device: Device) -> None:
        """Initialize the illuminance sensor enable/disable switch."""

        self._device = device
        self._attr_unique_id = f"{device.dev_id}_sensor_enable"
        self._attr_available = device.status == "online"
        self._attr_is_on: bool | None = True
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device.dev_id)},
            "name": device.name,
            "manufacturer": MANUFACTURER,
            "model": device.model,
            "via_device": (DOMAIN, device.gw_sn),
        }
        self._attr_extra_state_attributes = {
            "gateway_sn": device.gw_sn,
            "address": device.address,
            "channel": device.channel,
            "device_type": device.dev_type,
            "device_model": device.model,
        }

        self._sync_sensor_state()

    def _sync_sensor_state(self) -> None:
        self._device.get_sensor_enabled()

    async def async_turn_on(self, **_kwargs: Any) -> None:
        """Enable the illuminance sensor."""
        self._device.set_sensor_enabled(True)
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **_kwargs: Any) -> None:
        """Disable the illuminance sensor."""
        self._device.set_sensor_enabled(False)
        self._attr_is_on = False
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""

        self.async_on_remove(
            self._device.register_listener(
                CallbackEventType.SENSOR_ON_OFF, self._handle_sensor_on_off
            )
        )

        self.async_on_remove(
            self._device.register_listener(
                CallbackEventType.ONLINE_STATUS, self._handle_availability
            )
        )

        self._sync_sensor_state()

    @callback
    def _handle_sensor_on_off(self, on_off: bool) -> None:
        """Handle sensor on/off updates."""
        self._attr_is_on = on_off
        self.schedule_update_ha_state()

    @callback
    def _handle_availability(self, available: bool) -> None:
        self._attr_available = available
        self.schedule_update_ha_state()
