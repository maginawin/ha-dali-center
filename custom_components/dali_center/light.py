"""Platform for light integration."""

from __future__ import annotations

import colorsys
import logging
from typing import Any

from propcache.api import cached_property
from PySrDaliGateway import DaliGateway, Device, Group
from PySrDaliGateway.helper import is_light_device

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_HS_COLOR,
    ATTR_RGBW_COLOR,
    LightEntity,
)
from homeassistant.components.light.const import ColorMode
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, MANUFACTURER
from .entity import GatewayAvailabilityMixin
from .types import DaliCenterConfigEntry

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DaliCenterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Dali Center light entities from config entry."""
    del hass  # Unused parameter
    gateway: DaliGateway = entry.runtime_data.gateway
    devices: list[Device] = [
        Device(gateway, device) for device in entry.data.get("devices", [])
    ]
    groups: list[Group] = [
        Group(gateway, group) for group in entry.data.get("groups", [])
    ]

    _LOGGER.info(
        "Setting up light platform: %d devices, %d groups", len(devices), len(groups)
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

    # Add All Lights control entity
    all_lights_entity = DaliCenterAllLights(gateway)
    async_add_entities([all_lights_entity])
    _LOGGER.info("Added All Lights control entity")


class DaliCenterLight(GatewayAvailabilityMixin, LightEntity):
    """Representation of a Dali Center Light."""

    _attr_has_entity_name = True

    def __init__(self, light: Device) -> None:
        """Initialize the light entity."""
        GatewayAvailabilityMixin.__init__(self, light.gw_sn)
        LightEntity.__init__(self)

        self._light = light
        self._attr_name = "Light"
        self._attr_unique_id = light.unique_id
        self._attr_available = light.status == "online"
        self._attr_is_on: bool | None = None
        self._attr_brightness: int | None = None
        self._white_level: int | None = None
        self._attr_color_mode: ColorMode | str | None = None
        self._attr_color_temp_kelvin: int | None = None
        self._attr_hs_color: tuple[float, float] | None = None
        self._attr_rgbw_color: tuple[int, int, int, int] | None = None
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
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._light.dev_id)},
            name=self._light.name,
            manufacturer=MANUFACTURER,
            model=f"Dali Light Type {self._light.dev_type}",
            via_device=(DOMAIN, self._light.gw_sn),
        )

    @property
    def min_color_temp_kelvin(self) -> int:
        """Return minimum color temperature in Kelvin."""
        return 1000

    @property
    def max_color_temp_kelvin(self) -> int:
        """Return maximum color temperature in Kelvin."""
        return 8000

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        _LOGGER.debug(
            "Turning on light %s with kwargs: %s", self._attr_unique_id, kwargs
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
        """Turn off the light."""
        del kwargs  # Unused parameter
        self._light.turn_off()

    async def async_added_to_hass(self) -> None:
        """Handle entity addition to Home Assistant."""
        await super().async_added_to_hass()

        # Handle device-specific updates
        signal = f"dali_center_update_{self._attr_unique_id}"
        self.async_on_remove(
            async_dispatcher_connect(self.hass, signal, self._handle_device_update)
        )

        # Handle device-specific availability
        signal = f"dali_center_update_available_{self._attr_unique_id}"
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, signal, self._handle_device_availability
            )
        )

        self._light.read_status()

    def _handle_device_update(self, property_list: list[dict[str, Any]]) -> None:
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
                    self._white_level,
                )

        if 22 in props:
            brightness_value = float(props[22])
            if brightness_value == 0 and self._attr_brightness is None:
                self._attr_brightness = 255
            else:
                self._attr_brightness = int(brightness_value / 1000 * 255)

        if (
            23 in props
            and self._attr_supported_color_modes
            and ColorMode.COLOR_TEMP in self._attr_supported_color_modes
        ):
            self._attr_color_temp_kelvin = int(props[23])

        if (
            24 in props
            and self._attr_supported_color_modes
            and ColorMode.HS in self._attr_supported_color_modes
        ):
            hsv = str(props[24])
            h = int(hsv[0:4], 16)
            s = int(hsv[4:8], 16) / 10
            self._attr_hs_color = (h, s)
            _LOGGER.warning("HS color: %s", self._attr_hs_color)

        if (
            24 in props
            and self._attr_supported_color_modes
            and ColorMode.RGBW in self._attr_supported_color_modes
        ):
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
                int(rgb[0] * 255),
                int(rgb[1] * 255),
                int(rgb[2] * 255),
                w,
            )
            # _LOGGER.warning("RGBW color: %s", self._attr_rgbw_color)

        self.hass.loop.call_soon_threadsafe(self.schedule_update_ha_state)


class DaliCenterLightGroup(GatewayAvailabilityMixin, LightEntity):
    """Representation of a Dali Center Light Group."""

    def __init__(self, group: Group) -> None:
        """Initialize the light group."""
        GatewayAvailabilityMixin.__init__(self, group.gw_sn)
        LightEntity.__init__(self)

        self._group = group
        self._attr_name = f"{group.name}"
        self._attr_unique_id = f"{group.unique_id}"
        self._attr_available = True
        self._attr_icon = "mdi:lightbulb-group"
        self._attr_is_on: bool | None = False
        self._attr_brightness: int | None = 0
        self._attr_color_mode = ColorMode.RGBW
        self._attr_color_temp_kelvin: int | None = 1000
        self._attr_hs_color: tuple[float, float] | None = None
        self._attr_rgbw_color: tuple[int, int, int, int] | None = None
        self._attr_supported_color_modes = {ColorMode.COLOR_TEMP, ColorMode.RGBW}

    @cached_property
    def device_info(self) -> DeviceInfo | None:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._group.gw_sn)},
        )

    @property
    def min_color_temp_kelvin(self) -> int:
        """Return minimum color temperature in Kelvin."""
        return 1000

    @property
    def max_color_temp_kelvin(self) -> int:
        """Return maximum color temperature in Kelvin."""
        return 8000

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

        self.hass.loop.call_soon_threadsafe(self.schedule_update_ha_state)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light group."""
        del kwargs  # Unused parameter
        self._group.turn_off()
        self._attr_is_on = False
        self.hass.loop.call_soon_threadsafe(self.schedule_update_ha_state)


class DaliCenterAllLights(GatewayAvailabilityMixin, LightEntity):
    """Gateway-level all lights control via broadcast commands."""

    _attr_has_entity_name = True

    def __init__(self, gateway: DaliGateway) -> None:
        """Initialize the all lights control."""
        GatewayAvailabilityMixin.__init__(self, gateway.gw_sn)
        LightEntity.__init__(self)

        self._gateway = gateway
        self._attr_name = "All Lights"
        self._attr_unique_id = f"{gateway.gw_sn}_all_lights"
        self._attr_available = True
        self._attr_icon = "mdi:lightbulb-group-outline"

        # State management (local simulation since broadcast has no feedback)
        self._attr_is_on: bool | None = False
        self._attr_brightness: int | None = None
        self._white_level: int | None = None
        self._attr_color_temp_kelvin: int | None = None
        self._attr_hs_color: tuple[float, float] | None = None
        self._attr_rgbw_color: tuple[int, int, int, int] | None = None

        # Color mode support (matching Group capabilities)
        self._attr_color_mode = ColorMode.RGBW
        self._attr_supported_color_modes = {
            ColorMode.BRIGHTNESS,
            ColorMode.COLOR_TEMP,
            ColorMode.RGBW,
        }

    @cached_property
    def device_info(self) -> DeviceInfo | None:
        """Return device information - associate with gateway."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._gateway.gw_sn)},
        )

    @property
    def min_color_temp_kelvin(self) -> int:
        """Return minimum color temperature in Kelvin."""
        return 1000

    @property
    def max_color_temp_kelvin(self) -> int:
        """Return maximum color temperature in Kelvin."""
        return 8000

    def _rgbw_to_hsv_string(self, rgb: tuple[int, int, int]) -> str:
        """Convert RGB to HSV string format for DALI commands."""
        # Convert RGB (0-255) to HSV
        r, g, b = rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0
        h, s, v = colorsys.rgb_to_hsv(r, g, b)

        # Convert to DALI format ranges
        h_dali = int(h * 360 * 16)  # 0-360 degrees * 16
        s_dali = int(s * 1000)  # 0-1000
        v_dali = int(v * 1000)  # 0-1000

        # Format as 12-character hex string
        return f"{h_dali:04x}{s_dali:04x}{v_dali:04x}"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on all lights with comprehensive parameter support."""
        _LOGGER.debug("All lights turn_on with kwargs: %s", kwargs)

        brightness = kwargs.get(ATTR_BRIGHTNESS)
        color_temp_kelvin = kwargs.get(ATTR_COLOR_TEMP_KELVIN)
        rgbw_color = kwargs.get(ATTR_RGBW_COLOR)
        hs_color = kwargs.get(ATTR_HS_COLOR)

        # Build command data array
        command_data: list[dict[str, Any]] = []

        # Main power on (DPID 20)
        command_data.append({"dpid": 20, "dataType": "bool", "value": True})

        # Brightness control (DPID 22)
        if brightness is not None:
            command_data.append({"dpid": 22, "dataType": "uint16", "value": brightness})
            self._attr_brightness = brightness

        # Color temperature control (DPID 23)
        if color_temp_kelvin is not None:
            command_data.append(
                {"dpid": 23, "dataType": "uint16", "value": color_temp_kelvin}
            )
            self._attr_color_temp_kelvin = color_temp_kelvin
            self._attr_color_mode = ColorMode.COLOR_TEMP

        # RGBW color control (DPID 24 + 21)
        if rgbw_color is not None:
            # Convert RGBW to HSV string format
            hsv_string = self._rgbw_to_hsv_string(rgbw_color[:3])  # RGB part
            command_data.append({"dpid": 24, "dataType": "string", "value": hsv_string})

            # White channel (DPID 21)
            white_level = int(rgbw_color[3]) if len(rgbw_color) > 3 else 0
            if white_level > 0:
                command_data.append(
                    {"dpid": 21, "dataType": "uint8", "value": white_level}
                )

            self._attr_rgbw_color = rgbw_color
            self._attr_color_mode = ColorMode.RGBW

        # HS color control converted to RGBW
        if hs_color is not None and rgbw_color is None:
            # Convert HS to RGB
            rgb = colorsys.hsv_to_rgb(hs_color[0] / 360, hs_color[1] / 100, 1.0)
            rgbw = (int(rgb[0] * 255), int(rgb[1] * 255), int(rgb[2] * 255), 0)

            hsv_string = self._rgbw_to_hsv_string(rgbw[:3])
            command_data.append({"dpid": 24, "dataType": "string", "value": hsv_string})

            self._attr_hs_color = hs_color
            self._attr_color_mode = ColorMode.HS

        # Send broadcast command
        try:
            self._gateway.command_write_dev("FFFF", 0, 1, command_data)
            self._attr_is_on = True
            self.schedule_update_ha_state()
            _LOGGER.debug("All lights broadcast turn_on command sent successfully")
        except Exception:
            _LOGGER.exception("Failed to send all lights turn_on command")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off all lights via broadcast."""
        del kwargs  # Unused parameter

        try:
            self._gateway.command_write_dev(
                "FFFF", 0, 1, [{"dpid": 20, "dataType": "bool", "value": False}]
            )
            self._attr_is_on = False
            self.schedule_update_ha_state()
            _LOGGER.debug("All lights broadcast turn_off command sent successfully")
        except Exception:
            _LOGGER.exception("Failed to send all lights turn_off command")
