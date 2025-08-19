"""Platform for light integration."""
from __future__ import annotations

import logging
from typing import Any, Optional
import colorsys

from functools import cached_property
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.components.light import (
    ATTR_RGBW_COLOR,
    LightEntity,
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_HS_COLOR,
)

from homeassistant.components.light.const import ColorMode

from .const import DOMAIN, MANUFACTURER
from PySrDaliGateway import DaliGateway, Device, Group
from PySrDaliGateway.helper import is_light_device
from .types import DaliCenterConfigEntry

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DaliCenterConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    del hass  # Unused parameter
    gateway: DaliGateway = entry.runtime_data.gateway
    devices: list[Device] = [
        Device(gateway, device)
        for device in entry.data.get("devices", [])
    ]
    groups: list[Group] = [
        Group(gateway, group)
        for group in entry.data.get("groups", [])
    ]

    _LOGGER.info(
        "Setting up light platform: %d devices, %d groups",
        len(devices), len(groups)
    )

    added_entities: set[str] = set()
    new_lights: list[DaliCenterLight] = []
    for device in devices:
        if device.dev_id in added_entities:
            continue
        if is_light_device(device.dev_type):
            new_lights.append(DaliCenterLight(device))
            added_entities.add(device.dev_id)

    if new_lights:
        async_add_entities(new_lights)

    added_group_entities: set[str] = set()
    new_groups: list[DaliCenterLightGroup] = []
    for group in groups:
        group_id = str(group)
        if group_id in added_group_entities:
            continue
        new_groups.append(DaliCenterLightGroup(group))
        added_group_entities.add(group_id)

    if new_groups:
        async_add_entities(new_groups)


class DaliCenterLight(LightEntity):
    """Representation of a Dali Center Light."""

    _attr_has_entity_name = True

    def __init__(self, light: Device) -> None:
        super().__init__()
        self._light = light
        self._attr_name = "Light"
        self._attr_unique_id = light.unique_id
        self._attr_available = light.status == "online"
        self._attr_is_on: Optional[bool] = None
        self._attr_brightness: Optional[int] = None
        self._white_level: Optional[int] = None
        self._attr_color_mode: ColorMode | str | None = None
        self._attr_color_temp_kelvin: Optional[int] = None
        self._attr_hs_color: Optional[tuple[float, float]] = None
        self._attr_rgbw_color: Optional[tuple[int, int, int, int]] = None
        self._determine_features()

    def _determine_features(self) -> None:
        supported_modes: set[ColorMode] = set()
        color_mode = self._light.color_mode
        if color_mode == "color_temp":
            self._attr_color_mode = ColorMode.COLOR_TEMP
        elif color_mode == "hs":
            self._attr_color_mode = ColorMode.HS
        elif color_mode == "rgbw":
            self._attr_color_mode = ColorMode.RGBW
        else:
            self._attr_color_mode = ColorMode.BRIGHTNESS
        supported_modes.add(self._attr_color_mode)
        self._attr_supported_color_modes = supported_modes

    @cached_property
    def device_info(self) -> DeviceInfo | None:
        return DeviceInfo(
            identifiers={(DOMAIN, self._light.dev_id)},
            name=self._light.name,
            manufacturer=MANUFACTURER,
            model=f"Dali Light Type {self._light.dev_type}",
            via_device=(DOMAIN, self._light.gw_sn),
        )

    @property
    def min_color_temp_kelvin(self) -> int:
        return 1000

    @property
    def max_color_temp_kelvin(self) -> int:
        return 8000

    async def async_turn_on(self, **kwargs: Any) -> None:
        _LOGGER.debug(
            "Turning on light %s with kwargs: %s",
            self._attr_unique_id, kwargs
        )
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
        del kwargs  # Unused parameter
        self._light.turn_off()

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
        self._light.read_status()

    def _handle_device_update_available(self, available: bool) -> None:
        self._attr_available = available
        if not available:
            self._attr_is_on = False
            self._attr_brightness = None
            self._attr_color_temp_kelvin = None
        self.hass.loop.call_soon_threadsafe(self.schedule_update_ha_state)

    def _handle_device_update(
        self, property_list: list[dict[str, Any]]
    ) -> None:
        props: dict[int, Any] = {}
        for prop in property_list:
            prop_id = prop.get("id") or prop.get("dpid")
            value = prop.get("value")
            if prop_id is not None and value is not None:
                props[prop_id] = value

        if 20 in props:
            self._attr_is_on = props[20]

        if 21 in props:
            self._white_level = int(props[21])
            if self._attr_rgbw_color is not None:
                self._attr_rgbw_color = (
                    self._attr_rgbw_color[0],
                    self._attr_rgbw_color[1],
                    self._attr_rgbw_color[2],
                    self._white_level
                )

        if 22 in props:
            brightness_value = float(props[22])
            if brightness_value == 0 and self._attr_brightness is None:
                self._attr_brightness = 255
            else:
                self._attr_brightness = int(brightness_value / 1000 * 255)

        if 23 in props and self._attr_supported_color_modes \
                and ColorMode.COLOR_TEMP in self._attr_supported_color_modes:
            self._attr_color_temp_kelvin = int(props[23])

        if 24 in props and self._attr_supported_color_modes \
                and ColorMode.HS in self._attr_supported_color_modes:
            hsv = str(props[24])
            h = int(hsv[0:4], 16)
            s = int(hsv[4:8], 16) / 10
            self._attr_hs_color = (h, s)
            _LOGGER.warning("HS color: %s", self._attr_hs_color)

        if 24 in props and self._attr_supported_color_modes \
                and ColorMode.RGBW in self._attr_supported_color_modes:
            hsv_rgbw = str(props[24])
            h = int(hsv_rgbw[0:4], 16)
            s = int(hsv_rgbw[4:8], 16)
            v = int(hsv_rgbw[8:12], 16)
            h_norm = max(0, min(360, h)) / 360.0
            s_norm = max(0, min(1000, s)) / 1000.0
            v_norm = max(0, min(1000, v)) / 1000.0

            if v_norm == 0 and self._attr_rgbw_color is None:
                v_norm = 1

            rgb = colorsys.hsv_to_rgb(h_norm, s_norm, v_norm)
            w = self._white_level if self._white_level is not None else 0
            self._attr_rgbw_color = (
                int(rgb[0]*255), int(rgb[1]*255), int(rgb[2]*255), w
            )
            # _LOGGER.warning("RGBW color: %s", self._attr_rgbw_color)

        self.hass.loop.call_soon_threadsafe(self.schedule_update_ha_state)


class DaliCenterLightGroup(LightEntity):
    """Representation of a Dali Center Light Group."""

    def __init__(self, group: Group) -> None:
        self._group = group
        self._attr_name = f"{group.name}"
        self._attr_unique_id = f"{group.group_id}"
        self._attr_available = True
        self._attr_icon = "mdi:lightbulb-group"
        self._attr_is_on: Optional[bool] = False
        self._attr_brightness: Optional[int] = 0
        self._attr_color_mode = ColorMode.RGBW
        self._attr_color_temp_kelvin: Optional[int] = 1000
        self._attr_hs_color: Optional[tuple[float, float]] = None
        self._attr_rgbw_color: Optional[tuple[int, int, int, int]] = None
        self._attr_supported_color_modes = {
            ColorMode.COLOR_TEMP,
            ColorMode.RGBW
        }

    @cached_property
    def device_info(self) -> DeviceInfo | None:
        return DeviceInfo(
            identifiers={(DOMAIN, self._group.gw_sn)},
        )

    @property
    def min_color_temp_kelvin(self) -> int:
        return 1000

    @property
    def max_color_temp_kelvin(self) -> int:
        return 8000

    async def async_turn_on(self, **kwargs: Any) -> None:
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        color_temp_kelvin = kwargs.get(ATTR_COLOR_TEMP_KELVIN)
        rgbw_color = kwargs.get(ATTR_RGBW_COLOR)

        self._group.turn_on(
            brightness=brightness,
            color_temp_kelvin=color_temp_kelvin,
            rgbw_color=rgbw_color
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

        self.hass.loop.call_soon_threadsafe(
            self.schedule_update_ha_state
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        del kwargs  # Unused parameter
        self._group.turn_off()
        self._attr_is_on = False
        self.hass.loop.call_soon_threadsafe(
            self.schedule_update_ha_state
        )
