"""Number platform for Dali Center device parameters."""

from __future__ import annotations

from typing import Literal

from PySrDaliGateway import CallbackEventType, Device
from PySrDaliGateway.helper import is_light_device
from PySrDaliGateway.types import DeviceParamType

from homeassistant.components.number import NumberEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .entity import DaliDeviceEntity
from .types import DaliCenterConfigEntry

PARALLEL_UPDATES = 1  # Serial control to prevent race conditions


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DaliCenterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Dali Center number entities from config entry."""
    devices = entry.runtime_data.devices

    numbers: list[NumberEntity] = []
    for device in devices:
        if not is_light_device(device.dev_type):
            continue

        numbers.append(DaliCenterFadeTimeNumber(device))
        numbers.append(DaliCenterFadeRateNumber(device))
        numbers.append(DaliCenterMinBrightnessNumber(device))
        numbers.append(DaliCenterMaxBrightnessNumber(device))

    if numbers:
        async_add_entities(numbers)


class DaliCenterDeviceParameterNumber(DaliDeviceEntity, NumberEntity):
    """Base number entity for device parameter configuration."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_step = 1

    def __init__(
        self,
        device: Device,
        parameter: Literal[
            "fade_time", "fade_rate", "min_brightness", "max_brightness"
        ],
        name: str,
        icon: str,
    ) -> None:
        """Initialize the device parameter number entity."""
        super().__init__(device)
        self._device = device
        self._parameter: Literal[
            "fade_time", "fade_rate", "min_brightness", "max_brightness"
        ] = parameter
        self._attr_name = name
        self._attr_icon = icon
        self._attr_unique_id = f"{device.unique_id}_{parameter}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.dev_id)},
        )
        self._attr_extra_state_attributes = {
            "gateway_sn": device.gw_sn,
            "address": device.address,
            "channel": device.channel,
            "device_type": device.dev_type,
            "device_model": device.model,
        }

        # Set parameter-specific min/max values
        if parameter in ("fade_time", "fade_rate"):
            self._attr_native_min_value = 0
            self._attr_native_max_value = 15
        else:  # brightness parameters (10-1000 represents 1%-100%)
            self._attr_native_min_value = 10
            self._attr_native_max_value = 1000

    async def async_added_to_hass(self) -> None:
        """Handle entity addition to Home Assistant."""
        await super().async_added_to_hass()

        self.async_on_remove(
            self._device.register_listener(
                CallbackEventType.DEV_PARAM, self._handle_device_parameters
            )
        )

        self._device.get_device_parameters()

    async def async_set_native_value(self, value: float) -> None:
        """Set the device parameter."""
        int_value = int(value)
        params: DeviceParamType = {}
        if self._parameter == "fade_time":
            params["fade_time"] = int_value
        elif self._parameter == "fade_rate":
            params["fade_rate"] = int_value
        elif self._parameter == "min_brightness":
            params["min_brightness"] = int_value
        else:
            params["max_brightness"] = int_value
        self._device.set_device_parameters(params)
        self._device.get_device_parameters()

    @callback
    def _handle_device_parameters(self, params: DeviceParamType) -> None:
        value = params.get(self._parameter)
        if value is None:
            return

        self._attr_native_value = value
        self.schedule_update_ha_state()


class DaliCenterFadeTimeNumber(DaliCenterDeviceParameterNumber):
    """Number entity for fade time configuration."""

    def __init__(self, device: Device) -> None:
        """Initialize fade time number entity."""
        super().__init__(
            device=device,
            parameter="fade_time",
            name="Fade Time",
            icon="mdi:timer-sand",
        )


class DaliCenterFadeRateNumber(DaliCenterDeviceParameterNumber):
    """Number entity for fade rate configuration."""

    def __init__(self, device: Device) -> None:
        """Initialize fade rate number entity."""
        super().__init__(
            device=device,
            parameter="fade_rate",
            name="Fade Rate",
            icon="mdi:speedometer",
        )


class DaliCenterMinBrightnessNumber(DaliCenterDeviceParameterNumber):
    """Number entity for minimum brightness configuration."""

    def __init__(self, device: Device) -> None:
        """Initialize minimum brightness number entity."""
        super().__init__(
            device=device,
            parameter="min_brightness",
            name="Minimum Brightness",
            icon="mdi:brightness-6",
        )


class DaliCenterMaxBrightnessNumber(DaliCenterDeviceParameterNumber):
    """Number entity for maximum brightness configuration."""

    def __init__(self, device: Device) -> None:
        """Initialize maximum brightness number entity."""
        super().__init__(
            device=device,
            parameter="max_brightness",
            name="Maximum Brightness",
            icon="mdi:brightness-7",
        )
