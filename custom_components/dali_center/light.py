"""Platform for light integration."""

from __future__ import annotations

import logging
from typing import Any

from propcache.api import cached_property
from PySrDaliGateway import CallbackEventType, DaliGateway, Device, Group
from PySrDaliGateway.helper import is_light_device
from PySrDaliGateway.types import LightStatus

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_HS_COLOR,
    ATTR_RGBW_COLOR,
    LightEntity,
)
from homeassistant.components.light.const import ColorMode
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event

from .const import DOMAIN, MANUFACTURER
from .types import DaliCenterConfigEntry

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DaliCenterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Dali Center light entities from config entry."""
    gateway: DaliGateway = entry.runtime_data.gateway
    devices: list[Device] = entry.runtime_data.devices
    groups: list[Group] = entry.runtime_data.groups
    all_light: Device = Device(
        gateway,
        unique_id=f"{gateway.gw_sn}_all_lights",
        dev_id=gateway.gw_sn,
        name="All Lights",
        dev_type="FFFF",
        channel=0,
        address=1,
        status="online",
        dev_sn=gateway.gw_sn,
        area_name="",
        area_id="",
        model="All Lights Controller",
        properties=[],
    )

    _LOGGER.info(
        "Setting up light platform: %d devices, %d groups", len(devices), len(groups)
    )

    added_entities: set[str] = set()
    new_lights: list[DaliCenterLight] = []
    for device in devices:
        if device.dev_id in added_entities:
            continue
        if is_light_device(device.dev_type):
            new_lights.append(DaliCenterLight(device, gateway))
            added_entities.add(device.dev_id)

    if new_lights:
        async_add_entities(new_lights)

    added_group_entities: set[str] = set()
    new_groups: list[DaliCenterLightGroup] = []
    for group in groups:
        group_id = str(group)
        if group_id in added_group_entities:
            continue
        new_groups.append(DaliCenterLightGroup(group, gateway))
        added_group_entities.add(group_id)

    if new_groups:
        async_add_entities(new_groups)

    all_lights_entity = DaliCenterAllLights(all_light, gateway, entry)
    async_add_entities([all_lights_entity])


class DaliCenterLight(LightEntity):
    """Representation of a Dali Center Light."""

    _attr_has_entity_name = True
    _attr_is_on: bool | None = None
    _attr_brightness: int | None = None
    _white_level: int | None = None
    _attr_color_mode: ColorMode | str | None = None
    _attr_color_temp_kelvin: int | None = None
    _attr_hs_color: tuple[float, float] | None = None
    _attr_rgbw_color: tuple[int, int, int, int] | None = None
    _attr_max_color_temp_kelvin = 8000
    _attr_min_color_temp_kelvin = 1000

    def __init__(self, light: Device, gateway: DaliGateway) -> None:
        """Initialize the light entity."""

        self._light = light
        self._gateway = gateway
        self._attr_name = "Light"
        self._attr_unique_id = light.unique_id
        self._attr_available = light.status == "online"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, light.dev_id)},
            "name": light.name,
            "manufacturer": MANUFACTURER,
            "model": light.model,
            "via_device": (DOMAIN, light.gw_sn),
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

    @cached_property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the optional state attributes."""
        return {
            "address": self._light.address,
            "channel": self._light.channel,
            "device_type": self._light.dev_type,
            "device_model": self._light.model,
        }

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

        self.async_on_remove(
            self._gateway.register_listener(
                CallbackEventType.LIGHT_STATUS, self._handle_device_update
            )
        )

        self.async_on_remove(
            self._gateway.register_listener(
                CallbackEventType.ONLINE_STATUS, self._handle_availability
            )
        )

        self._light.read_status()

    @callback
    def _handle_device_update(self, dev_id: str, status: LightStatus) -> None:
        if dev_id != self._attr_unique_id:
            return

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

        self.async_write_ha_state()

    @callback
    def _handle_availability(self, dev_id: str, available: bool) -> None:
        """Handle device-specific availability changes."""
        if dev_id not in (self._light.dev_id, self._gateway.gw_sn):
            return

        self._attr_available = available
        self.schedule_update_ha_state()


class DaliCenterLightGroup(LightEntity):
    """Representation of a Dali Center Light Group."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:lightbulb-group"
    _attr_min_color_temp_kelvin = 1000
    _attr_max_color_temp_kelvin = 8000
    _attr_available = True
    _attr_is_on: bool | None = False
    _attr_brightness: int | None = 0
    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_color_temp_kelvin: int | None = 1000
    _attr_hs_color: tuple[float, float] | None = None
    _attr_rgbw_color: tuple[int, int, int, int] | None = None
    _attr_supported_color_modes: set[ColorMode] | set[str] | None = {
        ColorMode.BRIGHTNESS
    }

    _group_lights: list[str] = []
    _group_entity_ids: list[str] = []
    _group_device_count = 0

    def __init__(self, group: Group, gateway: DaliGateway) -> None:
        """Initialize the light group."""

        self._group = group
        self._gateway = gateway
        self._attr_name = f"{group.name}"
        self._attr_unique_id = f"{group.unique_id}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, group.gw_sn)},
        }

    @callback
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

        self._attr_is_on = True
        if brightness is not None:
            self._attr_brightness = brightness
        if rgbw_color is not None:
            self._attr_color_mode = ColorMode.RGBW
            self._attr_rgbw_color = rgbw_color
        if color_temp_kelvin is not None:
            self._attr_color_mode = ColorMode.COLOR_TEMP
            self._attr_color_temp_kelvin = color_temp_kelvin

        self.schedule_update_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light group."""
        self._group.turn_off()
        self._attr_is_on = False
        self.hass.loop.call_soon_threadsafe(self.schedule_update_ha_state)

    async def async_added_to_hass(self) -> None:
        """Handle entity addition to Home Assistant."""
        await super().async_added_to_hass()
        await self._async_update_group_devices()
        await self._calculate_group_state()
        self.async_write_ha_state()
        if self._group_entity_ids:
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass, self._group_entity_ids, self._handle_member_light_update
                )
            )

    async def _async_update_group_devices(self) -> None:
        """Update the list of devices in this group."""

        group_info = await self._gateway.read_group(
            self._group.group_id, self._group.channel
        )
        ent_reg = er.async_get(self.hass)

        light_names: list[str] = []
        light_entities: list[str] = []

        for device_info in group_info["devices"]:
            light_names.append(device_info["name"])

            if device_unique_id := device_info["unique_id"]:
                if entity_id := ent_reg.async_get_entity_id(
                    "light", DOMAIN, device_unique_id
                ):
                    light_entities.append(entity_id)

        self._group_lights = sorted(light_names)
        self._group_entity_ids = sorted(light_entities)
        self._group_device_count = len(group_info["devices"])

        await self._determine_supported_color_modes()

    async def _determine_supported_color_modes(self) -> None:
        """Determine supported color modes based on member lights capabilities."""
        if not self._group_entity_ids:
            self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
            return

        # Collect supported modes from all member lights
        supported_modes: set[ColorMode] = set()

        for entity_id in self._group_entity_ids:
            state = self.hass.states.get(entity_id)
            if not state:
                continue

            # Get supported color modes from the light entity
            entity_modes = state.attributes.get("supported_color_modes", [])
            if entity_modes:
                supported_modes.update(entity_modes)

        # If no specific modes found, default to brightness
        if not supported_modes:
            supported_modes = {ColorMode.BRIGHTNESS}

        self._attr_supported_color_modes = supported_modes

    async def _calculate_group_state(self) -> None:
        """Calculate group state based on member lights' actual states."""
        if not self._group_entity_ids:
            return

        on_lights: list[Any] = []
        total_brightness = 0
        total_color_temp = 0
        rgbw_colors: list[tuple[int, int, int, int]] = []

        for entity_id in self._group_entity_ids:
            if not (state := self.hass.states.get(entity_id)) or state.state != "on":
                continue

            on_lights.append(state)
            if brightness := state.attributes.get(ATTR_BRIGHTNESS):
                total_brightness += brightness
            if color_temp := state.attributes.get(ATTR_COLOR_TEMP_KELVIN):
                total_color_temp += color_temp
            if rgbw_color := state.attributes.get(ATTR_RGBW_COLOR):
                rgbw_colors.append(rgbw_color)

        self._attr_is_on = bool(on_lights)

        if not on_lights:
            self._attr_brightness = 0
            return

        light_count = len(on_lights)
        self._attr_brightness = (
            total_brightness // light_count if total_brightness > 0 else 0
        )

        if total_color_temp > 0:
            self._attr_color_temp_kelvin = total_color_temp // light_count
            self._attr_color_mode = ColorMode.COLOR_TEMP
        elif rgbw_colors:
            color_count = len(rgbw_colors)
            self._attr_rgbw_color = (
                sum(c[0] for c in rgbw_colors) // color_count,
                sum(c[1] for c in rgbw_colors) // color_count,
                sum(c[2] for c in rgbw_colors) // color_count,
                sum(c[3] for c in rgbw_colors) // color_count,
            )
            self._attr_color_mode = ColorMode.RGBW
        else:
            self._attr_color_mode = ColorMode.BRIGHTNESS

    @callback
    def _handle_member_light_update(self, event: Event[EventStateChangedData]) -> None:
        """Handle member light state change."""
        entity_id = event.data["entity_id"]
        if entity_id in self._group_entity_ids:
            # Schedule state recalculation
            self.hass.async_create_task(self._async_update_group_state())

    async def _async_update_group_state(self) -> None:
        """Update group state and notify Home Assistant."""
        await self._calculate_group_state()
        self.async_write_ha_state()

    @cached_property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the optional state attributes."""

        return {
            "is_dali_group": True,
            "group_id": self._group.group_id,
            "channel": self._group.channel,
            "total_devices": self._group_device_count,
            "lights": self._group_lights,
            "entity_id": self._group_entity_ids,
            "group_name": self._group.name,
        }


class DaliCenterAllLights(LightEntity):
    """Gateway-level all lights control via broadcast commands."""

    _attr_has_entity_name = True
    _attr_name = "All Lights"
    _attr_icon = "mdi:lightbulb-group-outline"
    _attr_min_color_temp_kelvin = 1000
    _attr_max_color_temp_kelvin = 8000

    def __init__(
        self, light: Device, gateway: DaliGateway, config_entry: DaliCenterConfigEntry
    ) -> None:
        """Initialize the all lights control."""

        self._light = light
        self._gateway = gateway
        self._config_entry = config_entry
        self._attr_unique_id = light.unique_id
        self._attr_available = True
        self._attr_is_on: bool | None = False
        self._attr_brightness: int | None = 0
        self._attr_color_mode = ColorMode.RGBW
        self._attr_color_temp_kelvin: int | None = 1000
        self._attr_hs_color: tuple[float, float] | None = None
        self._attr_rgbw_color: tuple[int, int, int, int] | None = None
        self._attr_supported_color_modes: set[ColorMode] | set[str] | None = {
            ColorMode.BRIGHTNESS
        }

        self._all_light_entities: list[str] = []
        self._attr_device_info = {
            "identifiers": {(DOMAIN, light.gw_sn)},
        }

    async def async_added_to_hass(self) -> None:
        """Handle entity addition to Home Assistant."""
        await super().async_added_to_hass()
        await self._discover_all_light_entities()
        await self._calculate_all_lights_state()
        self.async_write_ha_state()

        # Subscribe to state changes of all light entities
        if self._all_light_entities:
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass, self._all_light_entities, self._handle_light_update
                )
            )

    async def _discover_all_light_entities(self) -> None:
        """Discover all light entities in this config entry (gateway)."""
        ent_reg = er.async_get(self.hass)

        # We'll match against the devices discovered from the gateway
        device_unique_ids = {
            device.unique_id for device in self._config_entry.runtime_data.devices
        }

        self._all_light_entities = [
            entity_entry.entity_id
            for entity_entry in ent_reg.entities.values()
            if (
                entity_entry.config_entry_id == self._config_entry.entry_id
                and entity_entry.domain == "light"
                and entity_entry.unique_id in device_unique_ids
            )  # Only individual device lights
        ]

        # Determine supported color modes based on individual lights
        await self._determine_all_lights_color_modes()

    async def _determine_all_lights_color_modes(self) -> None:
        """Determine supported color modes based on all individual lights capabilities."""
        if not self._all_light_entities:
            self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
            return

        # Collect supported modes from all member lights
        supported_modes: set[ColorMode] = set()

        for entity_id in self._all_light_entities:
            state = self.hass.states.get(entity_id)
            if not state:
                continue

            # Get supported color modes from the light entity
            entity_modes = state.attributes.get("supported_color_modes", [])
            if entity_modes:
                supported_modes.update(entity_modes)

        # If no specific modes found, default to brightness
        if not supported_modes:
            supported_modes = {ColorMode.BRIGHTNESS}

        self._attr_supported_color_modes = supported_modes

        _LOGGER.debug(
            "All Lights %s determined supported color modes: %s",
            self._attr_unique_id,
            supported_modes,
        )

    async def _calculate_all_lights_state(self) -> None:
        """Calculate all lights state based on individual light states."""
        if not self._all_light_entities:
            return

        on_lights: list[Any] = []
        total_brightness = 0
        total_color_temp = 0
        rgbw_colors: list[tuple[int, int, int, int]] = []

        for entity_id in self._all_light_entities:
            if not (state := self.hass.states.get(entity_id)) or state.state != "on":
                continue

            on_lights.append(state)
            if brightness := state.attributes.get(ATTR_BRIGHTNESS):
                total_brightness += brightness
            if color_temp := state.attributes.get(ATTR_COLOR_TEMP_KELVIN):
                total_color_temp += color_temp
            if rgbw_color := state.attributes.get(ATTR_RGBW_COLOR):
                rgbw_colors.append(rgbw_color)

        self._attr_is_on = bool(on_lights)

        if not on_lights:
            self._attr_brightness = 0
            return

        light_count = len(on_lights)
        self._attr_brightness = (
            total_brightness // light_count if total_brightness > 0 else 0
        )

        if total_color_temp > 0:
            self._attr_color_temp_kelvin = total_color_temp // light_count
            self._attr_color_mode = ColorMode.COLOR_TEMP
        elif rgbw_colors:
            color_count = len(rgbw_colors)
            self._attr_rgbw_color = (
                sum(c[0] for c in rgbw_colors) // color_count,
                sum(c[1] for c in rgbw_colors) // color_count,
                sum(c[2] for c in rgbw_colors) // color_count,
                sum(c[3] for c in rgbw_colors) // color_count,
            )
            self._attr_color_mode = ColorMode.RGBW
        else:
            self._attr_color_mode = ColorMode.BRIGHTNESS

    @callback
    def _handle_light_update(self, event: Event[EventStateChangedData]) -> None:
        """Handle individual light state change."""
        entity_id = event.data["entity_id"]
        if entity_id in self._all_light_entities:
            self.hass.async_create_task(self._async_update_all_lights_state())

    async def _async_update_all_lights_state(self) -> None:
        """Update all lights state and notify Home Assistant."""
        await self._calculate_all_lights_state()
        self.async_write_ha_state()

    @cached_property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the optional state attributes."""
        return {
            "address": self._light.address,
            "channel": self._light.channel,
            "device_type": self._light.dev_type,
            "device_model": self._light.model,
            "is_all_lights": True,
            "entity_id": self._all_light_entities,
            "total_lights": len(self._all_light_entities),
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on all lights."""
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        color_temp_kelvin = kwargs.get(ATTR_COLOR_TEMP_KELVIN)
        rgbw_color = kwargs.get(ATTR_RGBW_COLOR)

        self._light.turn_on(
            brightness=brightness,
            color_temp_kelvin=color_temp_kelvin,
            rgbw_color=rgbw_color,
        )

        self._attr_is_on = True
        if brightness is not None:
            self._attr_brightness = brightness
        if rgbw_color is not None:
            self._attr_color_mode = ColorMode.RGBW
            self._attr_rgbw_color = rgbw_color
        if color_temp_kelvin is not None:
            self._attr_color_mode = ColorMode.COLOR_TEMP
            self._attr_color_temp_kelvin = color_temp_kelvin

        self.hass.loop.call_soon_threadsafe(self.schedule_update_ha_state)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off all lights."""
        self._light.turn_off()
        self._attr_is_on = False
        self.hass.loop.call_soon_threadsafe(self.schedule_update_ha_state)
