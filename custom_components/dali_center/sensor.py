"""Platform for Dali Center energy sensors."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
import logging
from typing import Any

from propcache.api import cached_property
from PySrDaliGateway import DaliGateway, Device
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
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import DOMAIN, MANUFACTURER
from .entity import GatewayAvailabilityMixin
from .helper import gateway_to_dict
from .types import DaliCenterConfigEntry

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DaliCenterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Dali Center sensor entities from config entry."""
    gateway: DaliGateway = entry.runtime_data.gateway
    devices: list[Device] = entry.runtime_data.devices

    def _on_motion_status(dev_id: str, status: MotionStatus) -> None:
        signal = f"dali_center_update_{dev_id}"
        hass.add_job(async_dispatcher_send, hass, signal, status)

    def _on_illuminance_status(dev_id: str, status: IlluminanceStatus) -> None:
        signal = f"dali_center_update_{dev_id}"
        hass.add_job(async_dispatcher_send, hass, signal, status)

    gateway.on_motion_status = _on_motion_status
    gateway.on_illuminance_status = _on_illuminance_status

    _LOGGER.info("Setting up sensor platform: %d devices", len(devices))

    added_devices: set[str] = set()
    new_sensors: list[SensorEntity] = []
    for device in devices:
        if device.dev_id in added_devices:
            continue

        if is_light_device(device.dev_type):
            new_sensors.append(DaliCenterEnergySensor(device, gateway_to_dict(gateway)))
            added_devices.add(device.dev_id)
        elif is_motion_sensor(device.dev_type):
            new_sensors.append(DaliCenterMotionSensor(device, gateway_to_dict(gateway)))
            added_devices.add(device.dev_id)
        elif is_illuminance_sensor(device.dev_type):
            new_sensors.append(
                DaliCenterIlluminanceSensor(device, gateway_to_dict(gateway))
            )
            added_devices.add(device.dev_id)

    if new_sensors:
        async_add_entities(new_sensors)


class DaliCenterEnergySensor(GatewayAvailabilityMixin, SensorEntity):
    """Representation of a Dali Center Energy Sensor."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfEnergy.WATT_HOUR
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_suggested_display_precision = 2
    _attr_has_entity_name = True

    def __init__(self, device: Device, gateway: dict[str, Any]) -> None:
        """Initialize the energy sensor."""
        GatewayAvailabilityMixin.__init__(self, device.gw_sn, gateway)
        SensorEntity.__init__(self)

        self._device = device
        self._attr_name = "Energy"
        self._attr_unique_id = f"{device.unique_id}_energy"
        self._attr_available = device.status == "online"
        self._attr_native_value = 0.0

    @cached_property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, self._device.dev_id)},
        }

    async def async_added_to_hass(self) -> None:
        """Handle entity addition to Home Assistant."""
        await super().async_added_to_hass()

        signal = f"dali_center_energy_update_{self._device.dev_id}"
        self.async_on_remove(
            async_dispatcher_connect(self.hass, signal, self._handle_energy_update)
        )

        signal = f"dali_center_update_available_{self._device.dev_id}"
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, signal, self._handle_device_availability
            )
        )

    def _handle_energy_update(self, energy_value: float) -> None:
        self._attr_native_value = energy_value

        self.hass.loop.call_soon_threadsafe(self.schedule_update_ha_state)

    @cached_property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the optional state attributes."""
        attributes = self._get_gateway_attributes()
        device_attrs = self._get_device_base_attributes(self._device)
        attributes.update(device_attrs)
        return attributes


class DaliCenterMotionSensor(GatewayAvailabilityMixin, SensorEntity):
    """Representation of a Dali Center Motion Sensor."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["no_motion", "motion", "vacant", "presence", "occupancy"]
    _attr_has_entity_name = True
    _attr_icon = "mdi:motion-sensor"

    def __init__(self, device: Device, gateway: dict[str, Any]) -> None:
        """Initialize the motion sensor."""
        GatewayAvailabilityMixin.__init__(self, device.gw_sn, gateway)
        SensorEntity.__init__(self)

        self._device = device
        self._attr_name = "State"
        self._attr_unique_id = f"{device.unique_id}"
        self._attr_available = device.status == "online"
        self._attr_native_value = "no_motion"

    @cached_property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, self._device.dev_id)},
            "name": self._device.name,
            "manufacturer": MANUFACTURER,
            "model": self._device.model,
            "via_device": (DOMAIN, self._device.gw_sn),
        }

    async def async_added_to_hass(self) -> None:
        """Handle entity addition to Home Assistant."""
        await super().async_added_to_hass()

        signal = f"dali_center_update_{self._attr_unique_id}"
        self.async_on_remove(
            async_dispatcher_connect(self.hass, signal, self._handle_device_update)
        )

        signal = f"dali_center_update_available_{self._attr_unique_id}"
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, signal, self._handle_device_availability
            )
        )

        self._device.read_status()

    def _handle_device_update(self, status: MotionStatus) -> None:
        motion_state = status["motion_state"]
        self._attr_native_value = motion_state.value

        self.hass.loop.call_soon_threadsafe(self.schedule_update_ha_state)

    @cached_property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the optional state attributes."""
        attributes = self._get_gateway_attributes()
        device_attrs = self._get_device_base_attributes(self._device)
        attributes.update(device_attrs)
        return attributes


class DaliCenterIlluminanceSensor(GatewayAvailabilityMixin, SensorEntity):
    """Representation of a Dali Center Illuminance Sensor."""

    _attr_device_class = SensorDeviceClass.ILLUMINANCE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = LIGHT_LUX
    _attr_has_entity_name = True

    def __init__(self, device: Device, gateway: dict[str, Any]) -> None:
        """Initialize the illuminance sensor."""
        GatewayAvailabilityMixin.__init__(self, device.gw_sn, gateway)
        SensorEntity.__init__(self)

        self._device = device
        self._attr_name = "State"
        self._attr_unique_id = f"{device.unique_id}"
        self._attr_available = device.status == "online"
        self._attr_native_value: StateType | date | datetime | Decimal = None
        self._sensor_enabled: bool = True  # Track sensor enable state

    @cached_property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, self._device.dev_id)},
            "name": self._device.name,
            "manufacturer": MANUFACTURER,
            "model": self._device.model,
            "via_device": (DOMAIN, self._device.gw_sn),
        }

    async def async_added_to_hass(self) -> None:
        """Handle entity addition to Home Assistant."""
        await super().async_added_to_hass()

        signal = f"dali_center_update_{self._attr_unique_id}"
        self.async_on_remove(
            async_dispatcher_connect(self.hass, signal, self._handle_device_update)
        )

        signal = f"dali_center_update_available_{self._attr_unique_id}"
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, signal, self._handle_device_availability
            )
        )

        signal = f"dali_center_sensor_on_off_{self._attr_unique_id}"
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, signal, self._handle_sensor_on_off_update
            )
        )

        self._device.read_status()

    def _handle_device_update(self, status: IlluminanceStatus) -> None:
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

        self.hass.loop.call_soon_threadsafe(self.schedule_update_ha_state)

    @cached_property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the optional state attributes."""
        attributes = self._get_gateway_attributes()
        device_attrs = self._get_device_base_attributes(self._device)
        attributes.update(device_attrs)
        return attributes

    def _handle_sensor_on_off_update(self, on_off: bool) -> None:
        """Handle sensor on/off state updates from gateway."""
        self._sensor_enabled = on_off
        _LOGGER.debug(
            "Illuminance sensor enable state for device %s updated to: %s",
            self._device.dev_id,
            on_off,
        )

        if not self._sensor_enabled:
            self._attr_native_value = None

        self.hass.loop.call_soon_threadsafe(self.schedule_update_ha_state)
