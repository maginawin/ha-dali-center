"""Platform for Dali Center event entities."""

from __future__ import annotations

from functools import cached_property
import logging
from typing import Any, TypedDict

from PySrDaliGateway import DaliGateway, Device
from PySrDaliGateway.const import BUTTON_EVENTS
from PySrDaliGateway.helper import is_panel_device

from homeassistant.components.event import EventDeviceClass, EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MANUFACTURER
from .types import DaliCenterConfigEntry

_LOGGER = logging.getLogger(__name__)


class PanelConfig(TypedDict):
    """Panel configuration type definition."""

    button_count: int
    events: list[str]


# Panel configurations based on device type (from specification table)
PANEL_CONFIGS: dict[str, PanelConfig] = {
    "0302": {  # 2-button panel
        "button_count": 2,
        "events": ["press", "hold", "double_press", "release"],
    },
    "0304": {  # 4-button panel
        "button_count": 4,
        "events": ["press", "hold", "double_press", "release"],
    },
    "0306": {  # 6-button panel
        "button_count": 6,
        "events": ["press", "hold", "double_press", "release"],
    },
    "0308": {  # 8-button panel
        "button_count": 8,
        "events": ["press", "hold", "double_press", "release"],
    },
    "0300": {  # rotary knob panel
        "button_count": 1,
        "events": ["press", "double_press", "rotate"],
    },
}


def _generate_event_types_for_panel(dev_type: str) -> list[str]:
    """Generate event types based on panel device type."""
    config = PANEL_CONFIGS.get(dev_type)
    if not config:
        return ["button_1_press", "button_1_double_press", "button_1_hold"]

    event_types: list[str] = []
    event_types.extend(
        f"button_{button_num}_{event}"
        for button_num in range(1, config["button_count"] + 1)
        for event in config["events"]
    )

    return event_types


async def async_setup_entry(
    _: HomeAssistant,
    entry: DaliCenterConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Dali Center event entities from config entry."""
    gateway: DaliGateway = entry.runtime_data.gateway
    devices: list[Device] = [
        Device(gateway, device) for device in entry.data.get("devices", [])
    ]

    _LOGGER.debug("Setting up event platform: %d devices", len(devices))

    new_events: list[EventEntity] = [
        DaliCenterPanelEvent(device)
        for device in devices
        if is_panel_device(device.dev_type)
    ]

    if new_events:
        async_add_entities(new_events)


class DaliCenterPanelEvent(EventEntity):
    """Representation of a Dali Center Panel Event Entity."""

    _attr_has_entity_name = True
    _attr_device_class = EventDeviceClass.BUTTON

    def __init__(self, device: Device) -> None:
        """Initialize the panel event entity."""
        self._device = device
        self._attr_name = "Panel Buttons"
        self._attr_unique_id = f"{device.dev_id}_panel_events"
        self._attr_icon = "mdi:gesture-tap-button"
        self._attr_available = device.status == "online"

        self._attr_event_types = _generate_event_types_for_panel(device.dev_type)

    @cached_property
    def device_info(self) -> DeviceInfo | None:
        """Return device info for the panel."""
        return {
            "identifiers": {(DOMAIN, self._device.dev_id)},
            "name": self._device.name,
            "manufacturer": MANUFACTURER,
            "model": f"Panel Type {self._device.dev_type}",
            "via_device": (DOMAIN, self._device.gw_sn),
        }

    async def async_added_to_hass(self) -> None:
        """Handle when entity is added to hass."""
        signal = f"dali_center_update_{self._device.dev_id}"
        self.async_on_remove(
            async_dispatcher_connect(self.hass, signal, self._handle_device_update)
        )

        signal = f"dali_center_update_available_{self._device.dev_id}"
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, signal, self._handle_device_update_available
            )
        )

        self._device.read_status()

    @callback
    def _handle_device_update_available(self, available: bool) -> None:
        self._attr_available = available
        self.async_write_ha_state()

    @callback
    def _handle_device_update(self, property_list: list[dict[str, Any]]) -> None:
        for prop in property_list:
            dpid = prop.get("dpid")
            key_no = prop.get("keyNo")
            value = prop.get("value")

            event_name = None
            event_type = BUTTON_EVENTS.get(dpid) if dpid is not None else None
            if event_type:
                event_name = f"button_{key_no}_{event_type}"

            if event_name is None:
                _LOGGER.debug(
                    "Unknown event for %s: dpid=%s, keyNo=%s, value=%s",
                    self.unique_id,
                    dpid,
                    key_no,
                    value,
                )
                continue

            _LOGGER.debug(
                "Panel event triggered: %s (device=%s, dpid=%s, value=%s)",
                event_name,
                self.unique_id,
                dpid,
                value,
            )

            # Fire the event on the HA event bus for device triggers
            event_data = {
                "entity_id": self.entity_id,
                "event_type": event_name,
            }

            if dpid == 4 and value is not None:
                event_data["rotate_value"] = value
                self._trigger_event(event_name, {"rotate_value": value})
            else:
                self._trigger_event(event_name)

            # Fire the event on HA event bus for device automation triggers
            self.hass.bus.async_fire(f"{DOMAIN}_event", event_data)

            self.async_write_ha_state()
