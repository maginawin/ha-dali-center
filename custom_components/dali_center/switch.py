"""Platform for Dali Center illuminance sensor enable/disable switches."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.dispatcher import async_dispatcher_connect, async_dispatcher_send

from .const import DOMAIN, MANUFACTURER
from .types import DaliCenterConfigEntry
from PySrDaliGateway import DaliGateway, Device
from PySrDaliGateway.helper import is_illuminance_sensor

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DaliCenterConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Dali Center illuminance sensor enable/disable switches."""
    # pylint: disable=unused-argument

    gateway: DaliGateway = entry.runtime_data.gateway
    devices: list[Device] = [
        Device(gateway, device)
        for device in entry.data.get("devices", [])
    ]

    _LOGGER.debug(
        "Processing initially for illuminance sensor switches: %s",
        devices
    )

    added_devices = set()
    new_switches: list[SwitchEntity] = []
    for device in devices:
        if device.dev_id in added_devices:
            continue

        # Only create switches for illuminance sensor devices
        if is_illuminance_sensor(device.dev_type):
            new_switches.append(
                DaliCenterIlluminanceSensorEnableSwitch(device))
            added_devices.add(device.dev_id)

    if new_switches:
        async_add_entities(new_switches)


class DaliCenterIlluminanceSensorEnableSwitch(SwitchEntity):
    """Representation of an Illuminance Sensor Enable/Disable Switch."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_has_entity_name = True

    def __init__(self, device: Device) -> None:
        self._device = device
        self._name = "Sensor Enable"
        self._unique_id = f"{device.unique_id}_sensor_enable"
        self._device_id = device.unique_id
        self._available = device.status == "online"
        self._is_on: bool = True  # Default to enabled

        self._sync_sensor_state()

    def _sync_sensor_state(self) -> None:
        try:
            self._device.get_sensor_enabled()
        except Exception as e:  # pylint: disable=broad-exception-caught
            _LOGGER.debug(
                "Could not sync sensor state for device %s: %s",
                self._device_id, e
            )

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
    def is_on(self) -> bool:
        return self._is_on

    @property
    def icon(self) -> str:
        return "mdi:brightness-6"

    async def async_turn_on(self, **kwargs: Any) -> None:
        # pylint: disable=unused-argument
        try:
            self._device.set_sensor_enabled(True)
            _LOGGER.debug(
                "Enabled illuminance sensor for device %s (%s)",
                self._device.name, self._device_id
            )

            signal = f"dali_center_sensor_on_off_{self._device_id}"
            self.hass.add_job(
                async_dispatcher_send, self.hass, signal, True
            )

        except Exception as e:  # pylint: disable=broad-exception-caught
            _LOGGER.error(
                "Failed to enable illuminance sensor for device %s: %s",
                self._device_id, e
            )

    async def async_turn_off(self, **kwargs: Any) -> None:
        # pylint: disable=unused-argument
        try:
            self._device.set_sensor_enabled(False)
            _LOGGER.debug(
                "Disabled illuminance sensor for device %s (%s)",
                self._device.name, self._device_id
            )

            signal = f"dali_center_sensor_on_off_{self._device_id}"
            self.hass.add_job(
                async_dispatcher_send, self.hass, signal, False
            )

        except Exception as e:  # pylint: disable=broad-exception-caught
            _LOGGER.error(
                "Failed to disable illuminance sensor for device %s: %s",
                self._device_id, e
            )

    async def async_added_to_hass(self) -> None:
        signal = f"dali_center_update_available_{self._device_id}"
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, signal, self._handle_device_update_available
            )
        )

        # Listen for sensor on/off state updates
        signal = f"dali_center_sensor_on_off_{self._device_id}"
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, signal, self._handle_sensor_on_off_update
            )
        )

        # Sync initial state
        self._sync_sensor_state()

    def _handle_device_update_available(self, available: bool) -> None:
        self._available = available
        self.hass.loop.call_soon_threadsafe(
            self.schedule_update_ha_state
        )

    def _handle_sensor_on_off_update(self, on_off: bool) -> None:
        self._is_on = on_off
        _LOGGER.warning(
            "Illuminance sensor enable state for device %s updated to: %s",
            self._device_id, on_off
        )
        self.hass.loop.call_soon_threadsafe(
            self.schedule_update_ha_state
        )
