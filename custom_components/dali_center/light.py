"""Platform for light integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING, Any, cast

from propcache.api import cached_property
from PySrDaliGateway import AllLightsController, CallbackEventType, Device, Group
from PySrDaliGateway.helper import is_light_device
from PySrDaliGateway.types import LightStatus

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_HS_COLOR,
    ATTR_RGBW_COLOR,
    ATTR_SUPPORTED_COLOR_MODES,
    LightEntity,
    filter_supported_color_modes,
)
from homeassistant.components.light.const import ColorMode
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event

from .const import DOMAIN, MANUFACTURER
from .entity import DaliCenterEntity, DaliDeviceEntity
from .types import DaliCenterConfigEntry

if TYPE_CHECKING:
    from homeassistant.core import State

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1  # Serial control to prevent device overload


@dataclass
class AggregatedLightState:
    """Aggregated state from multiple light entities."""

    is_on: bool
    brightness: int
    color_temp_kelvin: int | None
    rgbw_color: tuple[int, int, int, int] | None
    color_mode: ColorMode | None


def calculate_aggregated_light_state(
    entity_ids: list[str],
    states_getter: Any,
    supported_color_modes: set[ColorMode] | set[str] | None,
) -> AggregatedLightState:
    """Calculate aggregated state from multiple light entities.

    This is a shared helper for DaliCenterLightGroup and DaliCenterAllLights
    to avoid code duplication.
    """
    on_lights: list[State] = []
    total_brightness = 0
    total_color_temp = 0
    rgbw_colors: list[tuple[int, int, int, int]] = []

    for entity_id in entity_ids:
        state = states_getter(entity_id)
        if state is None or state.state != "on":
            continue

        on_lights.append(state)
        if brightness := state.attributes.get(ATTR_BRIGHTNESS):
            total_brightness += brightness
        if color_temp := state.attributes.get(ATTR_COLOR_TEMP_KELVIN):
            total_color_temp += color_temp
        if color := state.attributes.get(ATTR_RGBW_COLOR):
            rgbw_colors.append(color)

    is_on = bool(on_lights)
    if not on_lights:
        return AggregatedLightState(
            is_on=False,
            brightness=0,
            color_temp_kelvin=None,
            rgbw_color=None,
            color_mode=None,
        )

    light_count = len(on_lights)
    brightness = total_brightness // light_count if total_brightness > 0 else 0

    # Determine color mode based on available data and supported modes
    color_temp_kelvin: int | None = None
    rgbw_color: tuple[int, int, int, int] | None = None
    color_mode: ColorMode | None = None

    if (
        total_color_temp > 0
        and supported_color_modes
        and ColorMode.COLOR_TEMP in supported_color_modes
    ):
        color_temp_kelvin = total_color_temp // light_count
        color_mode = ColorMode.COLOR_TEMP
    elif (
        rgbw_colors
        and supported_color_modes
        and ColorMode.RGBW in supported_color_modes
    ):
        color_count = len(rgbw_colors)
        rgbw_color = (
            sum(c[0] for c in rgbw_colors) // color_count,
            sum(c[1] for c in rgbw_colors) // color_count,
            sum(c[2] for c in rgbw_colors) // color_count,
            sum(c[3] for c in rgbw_colors) // color_count,
        )
        color_mode = ColorMode.RGBW
    elif supported_color_modes and ColorMode.BRIGHTNESS in supported_color_modes:
        color_mode = ColorMode.BRIGHTNESS
    elif supported_color_modes:
        color_mode = ColorMode(next(iter(supported_color_modes)))

    return AggregatedLightState(
        is_on=is_on,
        brightness=brightness,
        color_temp_kelvin=color_temp_kelvin,
        rgbw_color=rgbw_color,
        color_mode=color_mode,
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DaliCenterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Dali Center light entities from config entry."""
    gateway = entry.runtime_data.gateway
    devices = entry.runtime_data.devices
    groups = entry.runtime_data.groups

    async_add_entities(
        DaliCenterLight(device)
        for device in devices
        if is_light_device(device.dev_type)
    )

    async_add_entities(DaliCenterLightGroup(group) for group in groups)

    async_add_entities(
        [DaliCenterAllLights(AllLightsController(gateway, devices), entry.entry_id)]
    )


class DaliCenterLight(DaliDeviceEntity, LightEntity):
    """Representation of a Dali Center Light."""

    _attr_is_on: bool | None = None
    _attr_brightness: int | None = None
    _white_level: int | None = None
    _attr_color_mode: ColorMode | str | None = None
    _attr_color_temp_kelvin: int | None = None
    _attr_hs_color: tuple[float, float] | None = None
    _attr_rgbw_color: tuple[int, int, int, int] | None = None
    _attr_max_color_temp_kelvin = 8000
    _attr_min_color_temp_kelvin = 1000

    def __init__(self, light: Device) -> None:
        """Initialize the light entity."""
        super().__init__(light)
        self._light = light
        self._attr_name = "Light"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, light.dev_id)},
            name=light.name,
            manufacturer=MANUFACTURER,
            model=light.model,
            via_device=(DOMAIN, light.gw_sn),
        )
        self._attr_extra_state_attributes = {
            "gateway_sn": light.gw_sn,
            "address": light.address,
            "channel": light.channel,
            "device_type": light.dev_type,
            "device_model": light.model,
        }

        self._determine_features()

    def _determine_features(self) -> None:
        supported_modes: set[ColorMode] = set()

        color_mode_mapping: dict[str, ColorMode] = {
            "color_temp": ColorMode.COLOR_TEMP,
            "hs": ColorMode.HS,
            "rgbw": ColorMode.RGBW,
        }

        color_mode = self._light.color_mode
        self._attr_color_mode = color_mode_mapping.get(color_mode, ColorMode.BRIGHTNESS)
        supported_modes.add(self._attr_color_mode)
        self._attr_supported_color_modes = supported_modes

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        color_temp_kelvin = kwargs.get(ATTR_COLOR_TEMP_KELVIN)
        hs_color = kwargs.get(ATTR_HS_COLOR)
        rgbw_color = kwargs.get(ATTR_RGBW_COLOR)
        self._light.turn_on(
            brightness=brightness,
            color_temp_kelvin=color_temp_kelvin,
            hs_color=hs_color,
            rgbw_color=rgbw_color,
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        self._light.turn_off()

    async def async_added_to_hass(self) -> None:
        """Handle entity addition to Home Assistant."""
        await super().async_added_to_hass()

        self.async_on_remove(
            self._light.register_listener(
                CallbackEventType.LIGHT_STATUS, self._handle_device_update
            )
        )

        self._light.read_status()

    @callback
    def _handle_device_update(self, status: LightStatus) -> None:
        if status.get("is_on") is not None:
            self._attr_is_on = status["is_on"]

        if status.get("brightness") is not None:
            self._attr_brightness = status["brightness"]

        if status.get("white_level") is not None:
            self._white_level = status["white_level"]
            if self._attr_rgbw_color is not None and self._white_level is not None:
                self._attr_rgbw_color = (
                    self._attr_rgbw_color[0],
                    self._attr_rgbw_color[1],
                    self._attr_rgbw_color[2],
                    self._white_level,
                )

        if (
            status.get("color_temp_kelvin") is not None
            and self._attr_supported_color_modes
            and ColorMode.COLOR_TEMP in self._attr_supported_color_modes
        ):
            self._attr_color_temp_kelvin = status["color_temp_kelvin"]

        if (
            status.get("hs_color") is not None
            and self._attr_supported_color_modes
            and ColorMode.HS in self._attr_supported_color_modes
        ):
            self._attr_hs_color = status["hs_color"]

        if (
            status.get("rgbw_color") is not None
            and self._attr_supported_color_modes
            and ColorMode.RGBW in self._attr_supported_color_modes
        ):
            self._attr_rgbw_color = status["rgbw_color"]

        self.schedule_update_ha_state()


class DaliCenterLightGroup(DaliCenterEntity, LightEntity):
    """Representation of a Dali Center Light Group."""

    _attr_icon = "mdi:lightbulb-group"
    _attr_min_color_temp_kelvin = 1000
    _attr_max_color_temp_kelvin = 8000
    _attr_is_on: bool | None = False
    _attr_brightness: int | None = 0
    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_color_temp_kelvin: int | None = 1000
    _attr_hs_color: tuple[float, float] | None = None
    _attr_rgbw_color: tuple[int, int, int, int] | None = None
    _attr_supported_color_modes: set[ColorMode] | set[str] | None = {
        ColorMode.BRIGHTNESS
    }

    def __init__(self, group: Group) -> None:
        """Initialize the light group."""
        super().__init__(group)
        self._group = group
        self._attr_name = f"{group.name}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, group.gw_sn)},
        )

    @cached_property
    def _group_entity_ids(self) -> list[str]:
        """Get list of entity IDs for devices in this group."""
        ent_reg = er.async_get(self.hass)
        return [
            entity_id
            for device in self._group.devices
            if (
                entity_id := ent_reg.async_get_entity_id(
                    "light", DOMAIN, device["unique_id"]
                )
            )
        ]

    @cached_property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the group state attributes."""
        return {
            "total_devices": len(self._group.devices),
            "lights": sorted(device["name"] for device in self._group.devices),
            "entity_id": self._group_entity_ids,
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light group."""
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        color_temp_kelvin = kwargs.get(ATTR_COLOR_TEMP_KELVIN)
        rgbw_color = kwargs.get(ATTR_RGBW_COLOR)

        self._group.turn_on(
            brightness=brightness,
            color_temp_kelvin=color_temp_kelvin,
            rgbw_color=rgbw_color,
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light group."""
        self._group.turn_off()

    async def async_added_to_hass(self) -> None:
        """Handle entity addition to Home Assistant."""
        await super().async_added_to_hass()
        await self._determine_supported_color_modes()
        await self._calculate_group_state()
        if self._group_entity_ids:
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass, self._group_entity_ids, self._handle_member_light_update
                )
            )

    async def _determine_supported_color_modes(self) -> None:
        """Determine supported color modes based on member lights capabilities."""
        supported_color_modes = {ColorMode.ONOFF}
        all_supported_modes: list[set[ColorMode]] = []

        for entity_id in self._group_entity_ids:
            if state := self.hass.states.get(entity_id):
                if modes := state.attributes.get(ATTR_SUPPORTED_COLOR_MODES):
                    all_supported_modes.append(set(modes))

        if all_supported_modes:
            # Merge all color modes and filter invalid combinations
            supported_color_modes = filter_supported_color_modes(
                cast("set[ColorMode]", set().union(*all_supported_modes))
            )

        self._attr_supported_color_modes = supported_color_modes

    async def _calculate_group_state(self) -> None:
        """Calculate group state based on member lights' actual states."""
        if not self._group_entity_ids:
            return

        state = calculate_aggregated_light_state(
            self._group_entity_ids,
            self.hass.states.get,
            self._attr_supported_color_modes,
        )

        self._attr_is_on = state.is_on
        self._attr_brightness = state.brightness
        if state.color_temp_kelvin is not None:
            self._attr_color_temp_kelvin = state.color_temp_kelvin
        if state.rgbw_color is not None:
            self._attr_rgbw_color = state.rgbw_color
        if state.color_mode is not None:
            self._attr_color_mode = state.color_mode

    @callback
    def _handle_member_light_update(self, event: Event[EventStateChangedData]) -> None:
        """Handle member light state change."""
        entity_id = event.data["entity_id"]
        if entity_id in self._group_entity_ids:
            self.hass.async_create_task(self._calculate_and_update_state())

    async def _calculate_and_update_state(self) -> None:
        """Calculate group state and schedule update."""
        await self._calculate_group_state()
        self.schedule_update_ha_state()


class DaliCenterAllLights(DaliDeviceEntity, LightEntity):
    """Gateway-level all lights control via broadcast commands."""

    _attr_name = "All Lights"
    _attr_icon = "mdi:lightbulb-group-outline"
    _attr_min_color_temp_kelvin = 1000
    _attr_max_color_temp_kelvin = 8000
    _attr_is_on: bool | None = False
    _attr_brightness: int | None = 0
    _attr_color_mode = ColorMode.RGBW
    _attr_color_temp_kelvin: int | None = 1000
    _attr_hs_color: tuple[float, float] | None = None
    _attr_rgbw_color: tuple[int, int, int, int] | None = None
    _attr_supported_color_modes: set[ColorMode] | set[str] | None = {
        ColorMode.BRIGHTNESS
    }
    _all_light_entity_ids: list[str] = []

    def __init__(self, controller: AllLightsController, config_entry_id: str) -> None:
        """Initialize the all lights control."""
        super().__init__(controller)
        self._controller = controller
        self._config_entry_id = config_entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, controller.gw_sn)},
        )
        self._attr_extra_state_attributes = {
            "gateway_sn": controller.gw_sn,
            "address": controller.address,
            "channel": controller.channel,
            "device_type": controller.dev_type,
            "device_model": controller.model,
            "is_all_lights": True,
            "entity_id": [],
            "total_lights": 0,
        }

    async def async_added_to_hass(self) -> None:
        """Handle entity addition to Home Assistant."""
        await super().async_added_to_hass()
        await self._discover_all_light_entities()
        await self._calculate_all_lights_state()

        if self._all_light_entity_ids:
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass, self._all_light_entity_ids, self._handle_light_update
                )
            )

    async def _discover_all_light_entities(self) -> None:
        """Discover all light entities in this config entry (gateway)."""
        ent_reg = er.async_get(self.hass)

        # Get device unique IDs for filtering
        device_unique_ids = {device.unique_id for device in self._controller.devices}

        # Use the standard Home Assistant helper to get entities for this config entry
        self._all_light_entity_ids = [
            entity_entry.entity_id
            for entity_entry in er.async_entries_for_config_entry(
                ent_reg, self._config_entry_id
            )
            if entity_entry.domain == "light"
            and entity_entry.unique_id in device_unique_ids
        ]

        self._attr_extra_state_attributes.update(
            {
                "entity_id": self._all_light_entity_ids,
                "total_lights": len(self._all_light_entity_ids),
            }
        )

        await self._determine_all_lights_color_modes()

    async def _determine_all_lights_color_modes(self) -> None:
        """Determine supported color modes based on all individual lights capabilities."""
        supported_color_modes = {ColorMode.ONOFF}
        all_supported_modes: list[set[ColorMode]] = []

        for entity_id in self._all_light_entity_ids:
            if state := self.hass.states.get(entity_id):
                if modes := state.attributes.get(ATTR_SUPPORTED_COLOR_MODES):
                    all_supported_modes.append(set(modes))

        if all_supported_modes:
            # Merge all color modes and filter invalid combinations
            supported_color_modes = filter_supported_color_modes(
                cast("set[ColorMode]", set().union(*all_supported_modes))
            )

        self._attr_supported_color_modes = supported_color_modes

        _LOGGER.debug(
            "All Lights %s determined supported color modes: %s",
            self._attr_unique_id,
            supported_color_modes,
        )

    async def _calculate_all_lights_state(self) -> None:
        """Calculate all lights state based on individual light states."""
        if not self._all_light_entity_ids:
            return

        state = calculate_aggregated_light_state(
            self._all_light_entity_ids,
            self.hass.states.get,
            self._attr_supported_color_modes,
        )

        self._attr_is_on = state.is_on
        self._attr_brightness = state.brightness
        if state.color_temp_kelvin is not None:
            self._attr_color_temp_kelvin = state.color_temp_kelvin
        if state.rgbw_color is not None:
            self._attr_rgbw_color = state.rgbw_color
        if state.color_mode is not None:
            self._attr_color_mode = state.color_mode

    @callback
    def _handle_light_update(self, event: Event[EventStateChangedData]) -> None:
        """Handle individual light state change."""
        entity_id = event.data["entity_id"]
        if entity_id in self._all_light_entity_ids:
            self.hass.async_create_task(self._calculate_and_update_all_lights())

    async def _calculate_and_update_all_lights(self) -> None:
        """Calculate all lights state and schedule update."""
        await self._calculate_all_lights_state()
        self.schedule_update_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on all lights."""
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        color_temp_kelvin = kwargs.get(ATTR_COLOR_TEMP_KELVIN)
        rgbw_color = kwargs.get(ATTR_RGBW_COLOR)

        self._controller.turn_on(
            brightness=brightness,
            color_temp_kelvin=color_temp_kelvin,
            rgbw_color=rgbw_color,
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off all lights."""
        self._controller.turn_off()
