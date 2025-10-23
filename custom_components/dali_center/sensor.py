"""Platform for Dali Center energy sensors."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
import logging

from PySrDaliGateway import CallbackEventType, DaliGateway, Device
from PySrDaliGateway.helper import (
    is_illuminance_sensor,
    is_light_device,
    is_motion_sensor,
)
from PySrDaliGateway.types import IlluminanceStatus, MotionStatus

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import LIGHT_LUX, EntityCategory, UnitOfEnergy
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import DOMAIN, MANUFACTURER
from .types import DaliCenterConfigEntry

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DaliCenterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Dali Center sensor entities from config entry."""
    gateway = entry.runtime_data.gateway
    devices = entry.runtime_data.devices

    sensors: list[SensorEntity] = []
    for device in devices:
        if is_light_device(device.dev_type):
            sensors.append(DaliCenterEnergySensor(device, gateway))
        elif is_motion_sensor(device.dev_type):
            sensors.append(DaliCenterMotionSensor(device, gateway))
        elif is_illuminance_sensor(device.dev_type):
            sensors.append(DaliCenterIlluminanceSensor(device, gateway))

    if sensors:
        async_add_entities(sensors)


class DaliCenterEnergySensor(SensorEntity):
    """Representation of a Dali Center Energy Sensor."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfEnergy.WATT_HOUR
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_suggested_display_precision = 2
    _attr_has_entity_name = True
    _attr_name = "Energy"

    def __init__(self, device: Device, gateway: DaliGateway) -> None:
        """Initialize the energy sensor."""

        self._device = device
        self._gateway = gateway
        self._attr_unique_id = f"{device.unique_id}_energy"
        self._attr_available = device.status == "online"
        self._attr_native_value = 0.0
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device.dev_id)},
        }
        self._attr_extra_state_attributes = {
            "gateway_sn": device.gw_sn,
            "address": device.address,
            "channel": device.channel,
            "device_type": device.dev_type,
            "device_model": device.model,
        }

    async def async_added_to_hass(self) -> None:
        """Handle entity addition to Home Assistant."""

        self.async_on_remove(
            self._gateway.register_listener(
                CallbackEventType.ENERGY_REPORT, self._handle_energy_update
            )
        )

        self.async_on_remove(
            self._gateway.register_listener(
                CallbackEventType.ONLINE_STATUS, self._handle_availability
            )
        )

    @callback
    def _handle_energy_update(self, dev_id: str, energy_value: float) -> None:
        """Update energy value."""
        if dev_id != self._device.dev_id:
            return
        self._attr_native_value = energy_value
        self.schedule_update_ha_state()

    @callback
    def _handle_availability(self, dev_id: str, available: bool) -> None:
        """Handle device-specific availability changes."""
        if dev_id != self._device.dev_id:
            return

        self._attr_available = available
        self.schedule_update_ha_state()


class DaliCenterMotionSensor(SensorEntity):
    """Representation of a Dali Center Motion Sensor."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["no_motion", "motion", "vacant", "presence", "occupancy"]
    _attr_has_entity_name = True
    _attr_icon = "mdi:motion-sensor"
    _attr_name = "State"

    def __init__(self, device: Device, gateway: DaliGateway) -> None:
        """Initialize the motion sensor."""

        self._device = device
        self._gateway = gateway
        self._attr_unique_id = f"{device.unique_id}"
        self._attr_available = device.status == "online"
        self._attr_native_value = "no_motion"
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

    async def async_added_to_hass(self) -> None:
        """Handle entity addition to Home Assistant."""

        self.async_on_remove(
            self._gateway.register_listener(
                CallbackEventType.MOTION_STATUS, self._handle_motion_status
            )
        )

        self.async_on_remove(
            self._gateway.register_listener(
                CallbackEventType.ONLINE_STATUS, self._handle_availability
            )
        )

        self._device.read_status()

    @callback
    def _handle_motion_status(self, dev_id: str, status: MotionStatus) -> None:
        """Handle motion status updates."""
        if dev_id != self._attr_unique_id:
            return

        motion_state = status["motion_state"]
        self._attr_native_value = motion_state.value
        self.schedule_update_ha_state()

    @callback
    def _handle_availability(self, dev_id: str, available: bool) -> None:
        """Handle device-specific availability changes."""
        if dev_id not in (self._device.dev_id, self._device.gw_sn):
            return

        self._attr_available = available
        self.schedule_update_ha_state()


class DaliCenterIlluminanceSensor(SensorEntity):
    """Representation of a Dali Center Illuminance Sensor."""

    _attr_device_class = SensorDeviceClass.ILLUMINANCE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = LIGHT_LUX
    _attr_has_entity_name = True
    _attr_name = "State"

    def __init__(self, device: Device, gateway: DaliGateway) -> None:
        """Initialize the illuminance sensor."""

        self._device = device
        self._gateway = gateway
        self._attr_unique_id = f"{device.unique_id}"
        self._attr_available = device.status == "online"
        self._attr_native_value: StateType | date | datetime | Decimal = None
        self._sensor_enabled: bool = True
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

    async def async_added_to_hass(self) -> None:
        """Handle entity addition to Home Assistant."""

        self.async_on_remove(
            self._gateway.register_listener(
                CallbackEventType.ILLUMINANCE_STATUS, self._handle_illuminance_status
            )
        )

        self.async_on_remove(
            self._gateway.register_listener(
                CallbackEventType.ONLINE_STATUS, self._handle_availability
            )
        )

        self.async_on_remove(
            self._gateway.register_listener(
                CallbackEventType.SENSOR_ON_OFF, self._handle_sensor_on_off
            )
        )

        self._device.read_status()

    @callback
    def _handle_illuminance_status(
        self, dev_id: str, status: IlluminanceStatus
    ) -> None:
        """Handle illuminance status updates."""
        if dev_id != self._attr_unique_id:
            return

        illuminance_value = status["illuminance_value"]
        is_valid = status["is_valid"]

        if not is_valid:
            _LOGGER.debug(
                "%s %s value is not valid: %s lux",
                self._attr_name,
                self._attr_unique_id,
                illuminance_value,
            )
            return

        self._attr_native_value = illuminance_value
        self.schedule_update_ha_state()

    @callback
    def _handle_availability(self, dev_id: str, available: bool) -> None:
        """Handle device-specific availability changes."""
        if dev_id not in (self._device.dev_id, self._device.gw_sn):
            return

        self._attr_available = available
        self.schedule_update_ha_state()

    @callback
    def _handle_sensor_on_off(self, dev_id: str, on_off: bool) -> None:
        """Handle sensor on/off updates."""
        if dev_id != self._attr_unique_id:
            return

        self._sensor_enabled = on_off
        _LOGGER.debug(
            "Illuminance sensor enable state for device %s updated to: %s",
            self._device.dev_id,
            on_off,
        )

        if not self._sensor_enabled:
            self._attr_native_value = None

        self.schedule_update_ha_state()
