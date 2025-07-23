"""Platform for Dali Center event entities."""
from __future__ import annotations

import logging
from homeassistant.components.event import (
    EventDeviceClass,
    EventEntity,
    EventEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN, MANUFACTURER
from PySrDaliGateway import DaliGateway, Device
from PySrDaliGateway.helper import is_panel_device
from PySrDaliGateway.const import BUTTON_EVENTS
from .types import DaliCenterConfigEntry

_LOGGER = logging.getLogger(__name__)

PANEL_EVENT_DESCRIPTION = EventEntityDescription(
    key="panel_buttons",
    translation_key="panel_buttons",
    event_types=[
        "button_1_single_click", "button_1_double_click", "button_1_long_press",
        "button_2_single_click", "button_2_double_click", "button_2_long_press",
        "button_3_single_click", "button_3_double_click", "button_3_long_press",
        "button_4_single_click", "button_4_double_click", "button_4_long_press",
        "button_5_single_click", "button_5_double_click", "button_5_long_press",
        "button_6_single_click", "button_6_double_click", "button_6_long_press",
        "button_7_single_click", "button_7_double_click", "button_7_long_press",
        "button_8_single_click", "button_8_double_click", "button_8_long_press",
        "button_1_rotate", "button_2_rotate", "button_3_rotate",
        "button_4_rotate", "button_5_rotate", "button_6_rotate",
        "button_7_rotate", "button_8_rotate",
    ],
    device_class=EventDeviceClass.BUTTON,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DaliCenterConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Dali Center event entities from config entry."""
    # pylint: disable=unused-argument
    gateway: DaliGateway = entry.runtime_data.gateway
    devices: list[Device] = [
        Device(gateway, device)
        for device in entry.data.get("devices", [])
    ]

    _LOGGER.info("Setting up event platform: %d devices", len(devices))

    new_events: list[EventEntity] = []
    for device in devices:
        if is_panel_device(device.dev_type):
            new_events.append(DaliCenterPanelEvent(device))

    if new_events:
        async_add_entities(new_events)


class DaliCenterPanelEvent(EventEntity):
    """Representation of a Dali Center Panel Event Entity."""

    entity_description = PANEL_EVENT_DESCRIPTION
    _attr_has_entity_name = True

    def __init__(self, device: Device) -> None:
        """Initialize the panel event entity."""
        self._device = device
        self._attr_name = "Panel Buttons"
        self._attr_unique_id = f"{device.unique_id}_panel_events"
        self._device_id = device.unique_id
        self._available = device.status == "online"

    @property
    def icon(self) -> str:
        return "mdi:gesture-tap-button"

    @property
    def device_info(self) -> DeviceInfo | None:
        return {
            "identifiers": {(DOMAIN, self._device_id)},
            "name": self._device.name,
            "manufacturer": MANUFACTURER,
            "model": f"Panel Type {self._device.dev_type}",
            "via_device": (DOMAIN, self._device.gw_sn),
        }

    @property
    def available(self) -> bool:
        return self._available

    async def async_added_to_hass(self) -> None:
        """Call when entity is added to hass."""
        signal = f"dali_center_update_{self._device_id}"
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, signal, self._handle_device_update
            )
        )

        signal = f"dali_center_update_available_{self._device_id}"
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, signal, self._handle_device_update_available
            )
        )

        self._device.read_status()

    @callback
    def _handle_device_update_available(self, available: bool) -> None:
        """Handle device availability updates."""
        self._available = available
        self.async_write_ha_state()

    @callback
    def _handle_device_update(self, property_list: list) -> None:
        """Handle device property updates and trigger events."""
        for prop in property_list:
            dpid = prop.get("dpid")
            key_no = prop.get("keyNo")
            value = prop.get("value")

            event_name = None
            event_type = BUTTON_EVENTS.get(dpid, None)
            if event_type:
                event_name = f"button_{key_no}_{event_type}"

            if event_name is None:
                _LOGGER.warning(
                    "%s %s unknown event value: %s (dpid: %s)",
                    self.name, self.unique_id, event_name, dpid
                )
                continue

            _LOGGER.debug(
                "%s %s triggering event: %s (dpid: %s, value: %s)",
                self.name, self.unique_id,
                event_name, dpid, value
            )

            if dpid == 4:
                self._trigger_event(event_name, {"rotate_value": value})
            else:
                self._trigger_event(event_name)
