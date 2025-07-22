"""Platform for Dali Center energy sensors."""
from __future__ import annotations

import logging
from typing import Optional

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfEnergy, LIGHT_LUX
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN, MANUFACTURER
from PySrDaliGateway import DaliGateway, Device
from PySrDaliGateway.helper import is_light_device, is_motion_sensor, is_illuminance_sensor

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    # pylint: disable=unused-argument

    gateway: DaliGateway = hass.data[DOMAIN][entry.entry_id]
    devices: list[Device] = [
        Device(gateway, device)
        for device in entry.data.get("devices", [])
    ]

    _LOGGER.debug(
        "Processing initially known devices for energy sensors: %s",
        devices
    )

    added_devices = set()
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
    _attr_has_entity_name = True

    def __init__(self, device: Device) -> None:
        self._device = device

        self._name = "Current Hour Energy"
        self._unique_id = f"{device.unique_id}_energy"
        self._device_id = device.unique_id

        self._available = device.status == "online"
        self._state: float = 0.0

    @property
    def name(self) -> str:
        return self._name

    @property
    def unique_id(self) -> str:
        return self._unique_id

    @property
    def device_info(self) -> DeviceInfo | None:
        return {
            "identifiers": {(DOMAIN, self._device_id)},
        }

    @property
    def available(self) -> bool:
        return self._available

    @property
    def native_value(self) -> float | None:
        return self._state

    async def async_added_to_hass(self) -> None:
        signal = f"dali_center_energy_update_{self._device_id}"
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, signal, self._handle_energy_update
            )
        )

        signal = f"dali_center_update_available_{self._device_id}"
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, signal, self._handle_device_update_available
            )
        )

    def _handle_device_update_available(self, available: bool) -> None:
        self._available = available
        self.hass.loop.call_soon_threadsafe(
            self.schedule_update_ha_state
        )

    def _handle_energy_update(self, energy_value: float) -> None:
        self._state = energy_value

        self.hass.loop.call_soon_threadsafe(
            self.schedule_update_ha_state
        )


class DaliCenterMotionSensor(SensorEntity):
    """Representation of a Dali Center Motion Sensor."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["no_motion", "motion", "vacant", "presence", "occupancy"]
    _attr_has_entity_name = True

    def __init__(self, device: Device) -> None:
        self._device = device
        self._name = "State"
        self._unique_id = f"{device.unique_id}"
        self._device_id = device.unique_id
        self._available = device.status == "online"
        self._state: str = "no_motion"

    @property
    def icon(self) -> str:
        return "mdi:motion-sensor"

    @property
    def name(self) -> str:
        return self._name

    @property
    def unique_id(self) -> str:
        return self._unique_id

    @property
    def device_info(self) -> DeviceInfo | None:
        return {
            "identifiers": {(DOMAIN, self._device_id)},
            "name": self._device.name,
            "manufacturer": MANUFACTURER,
            "model": f"Motion Sensor Type {self._device.dev_type}",
            "via_device": (DOMAIN, self._device.gw_sn),
        }

    @property
    def available(self) -> bool:
        return self._available

    @property
    def native_value(self) -> str | None:
        return self._state

    async def async_added_to_hass(self) -> None:
        signal = f"dali_center_update_{self._unique_id}"
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, signal, self._handle_device_update
            )
        )

        signal = f"dali_center_update_available_{self._unique_id}"
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, signal, self._handle_device_update_available
            )
        )

        # Read initial status
        self._device.read_status()

    def _handle_device_update_available(self, available: bool) -> None:
        self._available = available
        self.hass.loop.call_soon_threadsafe(
            self.schedule_update_ha_state
        )

    def _handle_device_update(self, property_list: list) -> None:

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
                    self._state = motion_map[dpid]
                    _LOGGER.debug(
                        "%s %s state changed to: %s (dpid: %s) %s",
                        self._name, self._unique_id,
                        self._state, dpid, prop
                    )
                else:
                    # Default to no_motion for unknown dpid values
                    self._state = "no_motion"
                    _LOGGER.debug(
                        "%s %s unknown dpid: %s, setting to no_motion",
                        self._name, self._unique_id, dpid
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
        self._name = "State"
        self._unique_id = f"{device.unique_id}"
        self._device_id = device.unique_id
        self._available = device.status == "online"
        self._state: Optional[float] = None
        self._sensor_enabled: bool = True  # Track sensor enable state

    @property
    def name(self) -> str:
        return self._name

    @property
    def unique_id(self) -> str:
        return self._unique_id

    @property
    def device_info(self) -> DeviceInfo | None:
        return {
            "identifiers": {(DOMAIN, self._device_id)},
            "name": self._device.name,
            "manufacturer": MANUFACTURER,
            "model": f"Illuminance Sensor Type {self._device.dev_type}",
            "via_device": (DOMAIN, self._device.gw_sn),
        }

    @property
    def available(self) -> bool:
        return self._available

    @property
    def native_value(self) -> float | None:
        return self._state

    async def async_added_to_hass(self) -> None:
        signal = f"dali_center_update_{self._unique_id}"
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, signal, self._handle_device_update
            )
        )

        signal = f"dali_center_update_available_{self._unique_id}"
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, signal, self._handle_device_update_available
            )
        )
        
        # Listen for sensor on/off state updates
        signal = f"dali_center_sensor_on_off_{self._unique_id}"
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, signal, self._handle_sensor_on_off_update
            )
        )

        # Read initial status
        self._device.read_status()

    def _handle_device_update_available(self, available: bool) -> None:
        self._available = available
        self.hass.loop.call_soon_threadsafe(
            self.schedule_update_ha_state
        )

    def _handle_device_update(self, property_list: list) -> None:

        for prop in property_list:
            dpid = prop.get("dpid")
            value = prop.get("value")

            # Handle illuminance sensor status (dpid 4 for illuminance value)
            if dpid == 4 and value is not None:
                if value > 1000 or value <= 0:
                    _LOGGER.warning(
                        "%s %s value is not normal: %s lux (dpid: %s) %s",
                        self._name, self._unique_id,
                        value, dpid, prop
                    )
                    continue

                self._state = float(value)
                _LOGGER.debug(
                    "%s %s value updated to: %s lux (dpid: %s) %s",
                    self._name, self._unique_id,
                    self._state, dpid, prop
                )

        self.hass.loop.call_soon_threadsafe(
            self.schedule_update_ha_state
        )

    def _handle_sensor_on_off_update(self, on_off: bool) -> None:
        """Handle sensor on/off state updates from gateway."""
        self._sensor_enabled = on_off
        _LOGGER.debug(
            "Illuminance sensor enable state for device %s updated to: %s",
            self._device_id, on_off
        )

        # If sensor is disabled, clear the current state
        if not self._sensor_enabled:
            self._state = None

        self.hass.loop.call_soon_threadsafe(
            self.schedule_update_ha_state
        )
