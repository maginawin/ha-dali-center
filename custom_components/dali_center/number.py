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
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, SIGNAL_ADD_ENTITIES
from .entity import DaliDeviceEntity
from .types import DaliCenterConfigEntry

DeviceParameterName = Literal[
    "fade_time",
    "fade_rate",
    "min_brightness",
    "max_brightness",
    "power_status",
    "system_failure_status",
    "cct_cool",
    "cct_warm",
]

PARALLEL_UPDATES = 1  # Serial control to prevent race conditions


def _create_number_entities(device: Device) -> list[NumberEntity]:
    """Create number entities for a light device based on its type."""
    entities: list[NumberEntity] = [
        DaliCenterFadeTimeNumber(device),
        DaliCenterFadeRateNumber(device),
        DaliCenterMinBrightnessNumber(device),
        DaliCenterMaxBrightnessNumber(device),
        DaliCenterPowerOnLevelNumber(device),
        DaliCenterSystemFailureLevelNumber(device),
    ]
    if device.dev_type == "0102":
        entities.append(DaliCenterCctCoolestNumber(device))
        entities.append(DaliCenterCctWarmestNumber(device))
    return entities


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

        numbers.extend(_create_number_entities(device))

    if numbers:
        async_add_entities(numbers)

    @callback
    def _async_add_new_numbers(new_devices: list[Device]) -> None:
        """Add new number entities discovered by bus scan."""
        new_numbers: list[NumberEntity] = []
        for device in new_devices:
            if not is_light_device(device.dev_type):
                continue
            new_numbers.extend(_create_number_entities(device))
        if new_numbers:
            async_add_entities(new_numbers)

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, f"{SIGNAL_ADD_ENTITIES}_{entry.entry_id}", _async_add_new_numbers
        )
    )


class DaliCenterDeviceParameterNumber(DaliDeviceEntity, NumberEntity):
    """Base number entity for device parameter configuration."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_step = 1

    def __init__(
        self,
        device: Device,
        parameter: DeviceParameterName,
        name: str,
        icon: str,
        *,
        min_value: int,
        max_value: int,
    ) -> None:
        """Initialize the device parameter number entity."""
        super().__init__(device)
        self._device = device
        self._parameter: DeviceParameterName = parameter
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
        self._attr_native_min_value = min_value
        self._attr_native_max_value = max_value

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
        params: DeviceParamType = {self._parameter: int_value}
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
            min_value=0,
            max_value=15,
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
            min_value=0,
            max_value=15,
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
            min_value=10,
            max_value=1000,
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
            min_value=10,
            max_value=1000,
        )


class DaliCenterPowerOnLevelNumber(DaliCenterDeviceParameterNumber):
    """Number entity for power on level configuration."""

    def __init__(self, device: Device) -> None:
        """Initialize power on level number entity."""
        super().__init__(
            device=device,
            parameter="power_status",
            name="Power On Level",
            icon="mdi:power-on",
            min_value=10,
            max_value=1000,
        )


class DaliCenterSystemFailureLevelNumber(DaliCenterDeviceParameterNumber):
    """Number entity for system failure level configuration."""

    def __init__(self, device: Device) -> None:
        """Initialize system failure level number entity."""
        super().__init__(
            device=device,
            parameter="system_failure_status",
            name="System Failure Level",
            icon="mdi:alert-outline",
            min_value=0,
            max_value=254,
        )


class DaliCenterCctCoolestNumber(DaliCenterDeviceParameterNumber):
    """Number entity for CCT coolest temperature configuration."""

    def __init__(self, device: Device) -> None:
        """Initialize CCT coolest number entity."""
        super().__init__(
            device=device,
            parameter="cct_cool",
            name="CCT Coolest",
            icon="mdi:thermometer-low",
            min_value=1000,
            max_value=10000,
        )


class DaliCenterCctWarmestNumber(DaliCenterDeviceParameterNumber):
    """Number entity for CCT warmest temperature configuration."""

    def __init__(self, device: Device) -> None:
        """Initialize CCT warmest number entity."""
        super().__init__(
            device=device,
            parameter="cct_warm",
            name="CCT Warmest",
            icon="mdi:thermometer-high",
            min_value=1000,
            max_value=10000,
        )
