"""Platform for Dali Center energy sensors."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfEnergy, LIGHT_LUX
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from functools import cached_property
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN, MANUFACTURER
from PySrDaliGateway import DaliGateway, Device
from PySrDaliGateway.helper import is_light_device, is_motion_sensor, is_illuminance_sensor
from .types import DaliCenterConfigEntry

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,  # pylint: disable=unused-argument
    entry: DaliCenterConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:

    gateway: DaliGateway = entry.runtime_data.gateway
    devices: list[Device] = [
        Device(gateway, device)
        for device in entry.data.get("devices", [])
    ]

    _LOGGER.info("Setting up sensor platform: %d devices", len(devices))

    added_devices: set[str] = set()
    new_sensors: list[SensorEntity] = []
    for device in devices:
        if device.dev_id in added_devices:
            continue

        if is_light_device(device.dev_type):
            new_sensors.append(DaliCenterEnergySensor(device))
            added_devices.add(device.dev_id)
        elif is_motion_sensor(device.dev_type):
            new_sensors.append(DaliCenterMotionSensor(device))
            added_devices.add(device.dev_id)
        elif is_illuminance_sensor(device.dev_type):
            new_sensors.append(DaliCenterIlluminanceSensor(device))
            added_devices.add(device.dev_id)
        # Panel devices are now handled by event entities
        # elif is_panel_device(device.dev_type):
        #     new_sensors.append(DaliCenterPanelSensor(device))
        #     added_devices.add(device.dev_id)

    if new_sensors:
        async_add_entities(new_sensors)


class DaliCenterEnergySensor(SensorEntity):
    """Representation of a Dali Center Energy Sensor."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfEnergy.WATT_HOUR
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_suggested_display_precision = 2
    _attr_has_entity_name = True

    def __init__(self, device: Device) -> None:
        self._device = device

        self._attr_name = "Energy"
        self._attr_unique_id = f"{device.unique_id}_energy"

        self._attr_available = device.status == "online"
        self._attr_native_value = 0.0

    @cached_property
    def device_info(self) -> DeviceInfo | None:
        return {
            "identifiers": {(DOMAIN, self._device.dev_id)},
        }

    async def async_added_to_hass(self) -> None:
        signal = f"dali_center_energy_update_{self._device.dev_id}"
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, signal, self._handle_energy_update
            )
        )

        signal = f"dali_center_update_available_{self._device.dev_id}"
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, signal, self._handle_device_update_available
            )
        )

    def _handle_device_update_available(self, available: bool) -> None:
        self._attr_available = available
        self.hass.loop.call_soon_threadsafe(
            self.schedule_update_ha_state
        )

    def _handle_energy_update(self, energy_value: float) -> None:
        self._attr_native_value = energy_value

        self.hass.loop.call_soon_threadsafe(
            self.schedule_update_ha_state
        )


class DaliCenterMotionSensor(SensorEntity):
    """Representation of a Dali Center Motion Sensor."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["no_motion", "motion", "vacant", "presence", "occupancy"]
    _attr_has_entity_name = True
    _attr_icon = "mdi:motion-sensor"

    def __init__(self, device: Device) -> None:
        self._device = device
        self._attr_name = "State"
        self._attr_unique_id = f"{device.unique_id}"
        self._attr_available = device.status == "online"
        self._attr_native_value = "no_motion"

    @cached_property
    def device_info(self) -> DeviceInfo | None:
        return {
            "identifiers": {(DOMAIN, self._device.dev_id)},
            "name": self._device.name,
            "manufacturer": MANUFACTURER,
            "model": f"Motion Sensor Type {self._device.dev_type}",
            "via_device": (DOMAIN, self._device.gw_sn),
        }

    async def async_added_to_hass(self) -> None:
        signal = f"dali_center_update_{self._attr_unique_id}"
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, signal, self._handle_device_update
            )
        )

        signal = f"dali_center_update_available_{self._attr_unique_id}"
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, signal, self._handle_device_update_available
            )
        )

        # Read initial status
        self._device.read_status()

    def _handle_device_update_available(self, available: bool) -> None:
        self._attr_available = available
        self.hass.loop.call_soon_threadsafe(
            self.schedule_update_ha_state
        )

    def _handle_device_update(
        self, property_list: list[dict[str, Any]]
    ) -> None:

        for prop in property_list:
            dpid = prop.get("dpid")
            if dpid is not None:
                # For motion sensor, the dpid itself represents the motion state
                # Map dpid values to enum options
                motion_map = {
                    1: "no_motion",
                    2: "motion",
                    3: "vacant",
                    4: "occupancy",
                    5: "presence"
                }
                if dpid in motion_map:
                    self._attr_native_value = motion_map[dpid]
                    _LOGGER.debug(
                        "%s %s state changed to: %s (dpid: %s) %s",
                        self._attr_name, self._attr_unique_id,
                        self._attr_native_value, dpid, prop
                    )
                else:
                    # Default to no_motion for unknown dpid values
                    self._attr_native_value = "no_motion"
                    _LOGGER.debug(
                        "%s %s unknown dpid: %s, setting to no_motion",
                        self._attr_name, self._attr_unique_id, dpid
                    )

        self.hass.loop.call_soon_threadsafe(
            self.schedule_update_ha_state
        )


class DaliCenterIlluminanceSensor(SensorEntity):
    """Representation of a Dali Center Illuminance Sensor."""

    _attr_device_class = SensorDeviceClass.ILLUMINANCE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = LIGHT_LUX
    _attr_has_entity_name = True

    def __init__(self, device: Device) -> None:
        self._device = device
        self._attr_name = "State"
        self._attr_unique_id = f"{device.unique_id}"
        self._attr_available = device.status == "online"
        self._attr_native_value = None
        self._sensor_enabled: bool = True  # Track sensor enable state

    @cached_property
    def device_info(self) -> DeviceInfo | None:
        return {
            "identifiers": {(DOMAIN, self._device.dev_id)},
            "name": self._device.name,
            "manufacturer": MANUFACTURER,
            "model": f"Illuminance Sensor Type {self._device.dev_type}",
            "via_device": (DOMAIN, self._device.gw_sn),
        }

    async def async_added_to_hass(self) -> None:
        signal = f"dali_center_update_{self._attr_unique_id}"
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, signal, self._handle_device_update
            )
        )

        signal = f"dali_center_update_available_{self._attr_unique_id}"
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, signal, self._handle_device_update_available
            )
        )

        # Listen for sensor on/off state updates
        signal = f"dali_center_sensor_on_off_{self._attr_unique_id}"
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, signal, self._handle_sensor_on_off_update
            )
        )

        # Read initial status
        self._device.read_status()

    def _handle_device_update_available(self, available: bool) -> None:
        self._attr_available = available
        self.hass.loop.call_soon_threadsafe(
            self.schedule_update_ha_state
        )

    def _handle_device_update(
        self, property_list: list[dict[str, Any]]
    ) -> None:

        for prop in property_list:
            dpid = prop.get("dpid")
            value = prop.get("value")

            # Handle illuminance sensor status (dpid 4 for illuminance value)
            if dpid == 4 and value is not None:
                if value > 1000 or value <= 0:
                    _LOGGER.warning(
                        "%s %s value is not normal: %s lux (dpid: %s) %s",
                        self._attr_name, self._attr_unique_id,
                        value, dpid, prop
                    )
                    continue

                self._attr_native_value = float(value)
                _LOGGER.debug(
                    "%s %s value updated to: %s lux (dpid: %s) %s",
                    self._attr_name, self._attr_unique_id,
                    self._attr_native_value, dpid, prop
                )

        self.hass.loop.call_soon_threadsafe(
            self.schedule_update_ha_state
        )

    def _handle_sensor_on_off_update(self, on_off: bool) -> None:
        """Handle sensor on/off state updates from gateway."""
        self._sensor_enabled = on_off
        _LOGGER.debug(
            "Illuminance sensor enable state for device %s updated to: %s",
            self._device.dev_id, on_off
        )

        # If sensor is disabled, clear the current state
        if not self._sensor_enabled:
            self._attr_native_value = None

        self.hass.loop.call_soon_threadsafe(
            self.schedule_update_ha_state
        )
