"""Platform for light integration."""
from __future__ import annotations

import logging
from typing import Any, Optional
import colorsys

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.components.light import (
    ATTR_RGBW_COLOR,
    LightEntity,
    ColorMode,
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_HS_COLOR,
)

from .const import DOMAIN
from PySrDaliGateway import DaliGateway, Device, Group
from PySrDaliGateway.helper import is_light_device

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    gateway: DaliGateway = hass.data[DOMAIN][entry.entry_id]
    devices: list[Device] = [
        Device(gateway, device)
        for device in entry.data.get("devices", [])
    ]
    groups: list[Group] = [
        Group(gateway, group)
        for group in entry.data.get("groups", [])
    ]

    _LOGGER.debug("Processing devices: %s", devices)
    _LOGGER.debug("Processing groups: %s", groups)

    added_entities = set()
    new_lights = []
    for device in devices:
        if device.dev_id in added_entities:
            continue
        if is_light_device(device.dev_type):
            new_lights.append(DaliCenterLight(device))
            added_entities.add(device.dev_id)

    if new_lights:
        async_add_entities(new_lights)

    added_entities = set()
    new_groups = []
    for group in groups:
        group_id = str(group)
        if group_id in added_entities:
            continue
        new_groups.append(DaliCenterLightGroup(group))
        added_entities.add(group_id)

    if new_groups:
        async_add_entities(new_groups)


class DaliCenterLight(LightEntity):
    """Representation of a Dali Center Light."""

    _attr_has_entity_name = True

    def __init__(self, light: Device) -> None:
        self._light = light
        self._name = "Light"
        self._unique_id = light.unique_id
        self._available = light.status == "online"
        self._state: Optional[bool] = None
        self._brightness: Optional[int] = None
        self._white_level: Optional[int] = None
        self._color_mode: Optional[ColorMode] = None
        self._color_temp_kelvin: Optional[int] = None
        self._hs_color: Optional[tuple[float, float]] = None
        self._rgbw_color: Optional[tuple[int, int, int, int]] = None
        self._determine_features()

    def _determine_features(self) -> None:
        self._supported_color_modes = set()
        color_mode = self._light.color_mode
        if color_mode == "color_temp":
            self._color_mode = ColorMode.COLOR_TEMP
        elif color_mode == "hs":
            self._color_mode = ColorMode.HS
        elif color_mode == "rgbw":
            self._color_mode = ColorMode.RGBW
        else:
            self._color_mode = ColorMode.BRIGHTNESS
        self._supported_color_modes.add(self._color_mode)

    @property
    def name(self) -> str:
        return self._name

    @property
    def unique_id(self) -> str:
        return self._unique_id

    @property
    def device_info(self) -> DeviceInfo | None:
        return {
            "identifiers": {(DOMAIN, self._unique_id)},
            "name": self._light.name,
            "manufacturer": "Dali Center",
            "model": f"Dali Light Type {self._light.dev_type}",
            "via_device": (DOMAIN, self._light.gw_sn),
        }

    @property
    def available(self) -> bool:
        return self._available

    @property
    def min_color_temp_kelvin(self) -> int:
        return 1000

    @property
    def max_color_temp_kelvin(self) -> int:
        return 8000

    @property
    def is_on(self) -> bool | None:
        return self._state

    @property
    def brightness(self) -> int | None:
        return self._brightness

    @property
    def color_temp_kelvin(self) -> int | None:
        return self._color_temp_kelvin

    @property
    def color_mode(self) -> ColorMode | None:
        return self._color_mode

    @property
    def supported_color_modes(self) -> set[ColorMode]:
        return self._supported_color_modes

    @property
    def hs_color(self) -> tuple[float, float] | None:
        return self._hs_color

    @property
    def rgbw_color(self) -> tuple[int, int, int, int] | None:
        return self._rgbw_color

    async def async_turn_on(self, **kwargs: Any) -> None:
        _LOGGER.debug(
            "Turning on light %s with kwargs: %s",
            self._unique_id, kwargs
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
        # pylint: disable=unused-argument
        self._light.turn_off()

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
        self._light.read_status()

    def _handle_device_update_available(self, available: bool) -> None:
        self._available = available
        if not available:
            self._state = False
            self._brightness = None
            self._color_temp_kelvin = None
        self.hass.loop.call_soon_threadsafe(self.schedule_update_ha_state)

    def _handle_device_update(self, property_list: list) -> None:
        props = {}
        for prop in property_list:
            prop_id = prop.get("id") or prop.get("dpid")
            value = prop.get("value")
            if prop_id is not None and value is not None:
                props[prop_id] = value

        if 20 in props:
            self._state = props[20]

        if 21 in props:
            self._white_level = int(props[21])
            if self._rgbw_color is not None:
                self._rgbw_color = (
                    self._rgbw_color[0],
                    self._rgbw_color[1],
                    self._rgbw_color[2],
                    self._white_level
                )

        if 22 in props:
            brightness_value = props[22]
            if brightness_value == 0 and self._brightness is None:
                self._brightness = 255
            else:
                self._brightness = int(brightness_value / 1000 * 255)

        if 23 in props and ColorMode.COLOR_TEMP in self._supported_color_modes:
            self._color_temp_kelvin = props[23]

        if 24 in props and ColorMode.HS in self._supported_color_modes:
            hsv = props[24]
            h = int(hsv[0:4], 16)
            s = int(hsv[4:8], 16) / 10
            self._hs_color = (h, s)
            _LOGGER.warning("HS color: %s", self._hs_color)

        if 24 in props and ColorMode.RGBW in self._supported_color_modes:
            hsv = props[24]
            h = int(hsv[0:4], 16)
            s = int(hsv[4:8], 16)
            v = int(hsv[8:12], 16)
            h_norm = max(0, min(360, h)) / 360.0
            s_norm = max(0, min(1000, s)) / 1000.0
            v_norm = max(0, min(1000, v)) / 1000.0

            if v_norm == 0 and self._rgbw_color is None:
                v_norm = 1

            rgb = colorsys.hsv_to_rgb(h_norm, s_norm, v_norm)
            w = self._white_level if self._white_level is not None else 0
            self._rgbw_color = (
                int(rgb[0]*255), int(rgb[1]*255), int(rgb[2]*255), w
            )
            # _LOGGER.warning("RGBW color: %s", self._rgbw_color)

        self.hass.loop.call_soon_threadsafe(self.schedule_update_ha_state)


class DaliCenterLightGroup(LightEntity):
    """Representation of a Dali Center Light Group."""

    def __init__(self, group: Group) -> None:
        self._group = group
        self._name = f"{group.name}"
        self._unique_id = f"{group.group_id}"
        self._available = True
        self._state: Optional[bool] = False
        self._brightness: Optional[int] = 0
        self._color_mode = ColorMode.RGBW
        self._color_temp_kelvin: Optional[int] = 1000
        self._hs_color: Optional[tuple[float, float]] = None
        self._rgbw_color: Optional[tuple[int, int, int, int]] = None
        self._supported_color_modes = {
            ColorMode.COLOR_TEMP,
            ColorMode.RGBW
        }

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return the device info of the light group."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._group.gw_sn)},
        )

    @property
    def name(self) -> str:
        return self._name

    @property
    def unique_id(self) -> str:
        return self._unique_id

    @property
    def available(self) -> bool:
        return self._available

    @property
    def min_color_temp_kelvin(self) -> int:
        return 1000

    @property
    def max_color_temp_kelvin(self) -> int:
        return 8000

    @property
    def is_on(self) -> bool | None:
        return self._state

    @property
    def brightness(self) -> int | None:
        return self._brightness

    @property
    def color_temp_kelvin(self) -> int | None:
        return self._color_temp_kelvin

    @property
    def rgbw_color(self) -> tuple[int, int, int, int] | None:
        return self._rgbw_color

    @property
    def color_mode(self) -> ColorMode | None:
        return self._color_mode

    @property
    def supported_color_modes(self) -> set[ColorMode]:
        return self._supported_color_modes

    @property
    def icon(self) -> str:
        return "mdi:lightbulb-group"

    @property
    def hs_color(self) -> tuple[float, float] | None:
        return self._hs_color

    async def async_turn_on(self, **kwargs: Any) -> None:
        _LOGGER.debug(
            "Turning on light group %s with kwargs: %s", self._unique_id, kwargs
        )

        brightness = kwargs.get(ATTR_BRIGHTNESS)
        color_temp_kelvin = kwargs.get(ATTR_COLOR_TEMP_KELVIN)
        rgbw_color = kwargs.get(ATTR_RGBW_COLOR)

        self._group.turn_on(
            brightness=brightness,
            color_temp_kelvin=color_temp_kelvin,
            rgbw_color=rgbw_color
        )

        self._state = True
        if brightness is not None:
            self._brightness = brightness
        if rgbw_color is not None:
            self._color_mode = ColorMode.RGBW
            self._rgbw_color = rgbw_color
        if color_temp_kelvin is not None:
            self._color_mode = ColorMode.COLOR_TEMP
            self._color_temp_kelvin = color_temp_kelvin

        self.hass.loop.call_soon_threadsafe(
            self.schedule_update_ha_state
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        # pylint: disable=unused-argument
        self._group.turn_off()
        self._state = False
        self.hass.loop.call_soon_threadsafe(
            self.schedule_update_ha_state
        )
