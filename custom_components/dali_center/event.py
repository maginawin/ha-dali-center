"""Platform for Dali Center event entities."""

from __future__ import annotations

import logging

from propcache.api import cached_property
from PySrDaliGateway import DaliGateway, DaliGatewayType, Panel
from PySrDaliGateway.helper import is_panel_device
from PySrDaliGateway.types import PanelEventType, PanelStatus

from homeassistant.components.event import EventDeviceClass, EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
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
    """Set up Dali Center event entities from config entry."""
    gateway: DaliGateway = entry.runtime_data.gateway
    devices: list[Panel] = [
        Panel(gateway, device)
        for device in entry.data.get("devices", [])
        if is_panel_device(device.get("dev_type"))
    ]

    def _on_panel_status(dev_id: str, status: PanelStatus) -> None:
        signal = f"dali_center_update_{dev_id}"
        hass.add_job(async_dispatcher_send, hass, signal, status)

    gateway.on_panel_status = _on_panel_status

    _LOGGER.debug("Setting up event platform: %d devices", len(devices))

    new_events: list[EventEntity] = [
        DaliCenterPanelEvent(device, gateway.to_dict()) for device in devices
    ]

    if new_events:
        async_add_entities(new_events)


class DaliCenterPanelEvent(GatewayAvailabilityMixin, EventEntity):
    """Representation of a Dali Center Panel Event Entity."""

    _attr_has_entity_name = True
    _attr_device_class = EventDeviceClass.BUTTON

    def __init__(self, panel: Panel, gateway: DaliGatewayType) -> None:
        """Initialize the panel event entity."""
        GatewayAvailabilityMixin.__init__(self, panel.gw_sn, gateway)
        EventEntity.__init__(self)

        self._panel = panel
        self._attr_name = "Panel Buttons"
        self._attr_unique_id = f"{panel.dev_id}_panel_events"
        self._attr_icon = "mdi:gesture-tap-button"
        self._attr_available = panel.status == "online"

        self._attr_event_types = panel.get_available_event_types()

    @cached_property
    def device_info(self) -> DeviceInfo:
        """Return device info for the panel."""
        return {
            "identifiers": {(DOMAIN, self._panel.dev_id)},
            "name": self._panel.name,
            "manufacturer": MANUFACTURER,
            "model": self._panel.model,
            "via_device": (DOMAIN, self._panel.gw_sn),
        }

    async def async_added_to_hass(self) -> None:
        """Handle when entity is added to hass."""
        await super().async_added_to_hass()

        signal = f"dali_center_update_{self._panel.dev_id}"
        self.async_on_remove(
            async_dispatcher_connect(self.hass, signal, self._handle_device_update)
        )

        signal = f"dali_center_update_available_{self._panel.dev_id}"
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, signal, self._handle_device_availability
            )
        )

        self._panel.read_status()

    @callback
    def _handle_device_update(self, status: PanelStatus) -> None:
        key_no = status["key_no"]
        value = status["rotate_value"]

        event_name = status["event_name"]
        event_type = status["event_type"]

        _LOGGER.debug(
            "Panel event triggered: dev_id=%s, key_no=%d, event=%s, type=%s, value=%s",
            self._panel.dev_id,
            key_no,
            event_name,
            event_type,
            value,
        )

        event_data: dict[str, str | int] = {
            "entity_id": self.entity_id,
            "event_type": event_name,
        }

        if event_type == PanelEventType.ROTATE and value is not None:
            event_data["rotate_value"] = value
            self._trigger_event(event_name, {"rotate_value": value})
        else:
            self._trigger_event(event_name)

        self.hass.bus.async_fire(f"{DOMAIN}_event", event_data)
        self.async_write_ha_state()
