"""Platform for Dali Center event entities."""

from __future__ import annotations

import logging

from PySrDaliGateway import CallbackEventType, DaliGateway, Panel
from PySrDaliGateway.helper import is_panel_device
from PySrDaliGateway.types import PanelEventType, PanelStatus

from homeassistant.components.event import EventDeviceClass, EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, MANUFACTURER
from .types import DaliCenterConfigEntry

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DaliCenterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Dali Center event entities from config entry."""
    gateway = entry.runtime_data.gateway
    panel_devices = [
        device
        for device in entry.runtime_data.devices
        if is_panel_device(device.dev_type)
    ]

    devices = [
        Panel(
            gateway,
            unique_id=device.unique_id,
            dev_id=device.dev_id,
            name=device.name,
            dev_type=device.dev_type,
            channel=device.channel,
            address=device.address,
            status=device.status,
            dev_sn=device.dev_sn,
            area_name=device.area_name,
            area_id=device.area_id,
            model=device.model,
            properties=device.properties,
        )
        for device in panel_devices
    ]

    async_add_entities(DaliCenterPanelEvent(device, gateway) for device in devices)


class DaliCenterPanelEvent(EventEntity):
    """Representation of a Dali Center Panel Event Entity."""

    _attr_has_entity_name = True
    _attr_device_class = EventDeviceClass.BUTTON
    _attr_name = "Panel Buttons"
    _attr_icon = "mdi:gesture-tap-button"

    def __init__(self, panel: Panel, gateway: DaliGateway) -> None:
        """Initialize the panel event entity."""

        self._panel = panel
        self._gateway = gateway
        self._attr_unique_id = f"{panel.dev_id}_panel_events"
        self._attr_available = panel.status == "online"

        self._attr_event_types = panel.get_available_event_types()
        self._attr_device_info = {
            "identifiers": {(DOMAIN, panel.dev_id)},
            "name": panel.name,
            "manufacturer": MANUFACTURER,
            "model": panel.model,
            "via_device": (DOMAIN, panel.gw_sn),
        }

    async def async_added_to_hass(self) -> None:
        """Handle when entity is added to hass."""
        await super().async_added_to_hass()

        self.async_on_remove(
            self._gateway.register_listener(
                CallbackEventType.PANEL_STATUS, self._handle_device_update
            )
        )

        self.async_on_remove(
            self._gateway.register_listener(
                CallbackEventType.ONLINE_STATUS,
                self._handle_availability,
            )
        )

        self._panel.read_status()

    @callback
    def _handle_device_update(self, dev_id: str, status: PanelStatus) -> None:
        if dev_id != self._panel.dev_id:
            return
        event_name = status["event_name"]
        event_type = status["event_type"]
        rotate_value = status["rotate_value"]

        _LOGGER.debug(
            "Panel event: %s (dev_id=%s)",
            event_name,
            self._panel.dev_id,
        )

        event_data: dict[str, str | int] = {
            "entity_id": self.entity_id,
            "event_type": event_name,
        }

        if event_type == PanelEventType.ROTATE and rotate_value is not None:
            event_data["rotate_value"] = rotate_value
            self._trigger_event(event_name, {"rotate_value": rotate_value})
        else:
            self._trigger_event(event_name)

        self.hass.bus.async_fire(f"{DOMAIN}_event", event_data)
        self.schedule_update_ha_state()

    @callback
    def _handle_availability(self, dev_id: str, available: bool) -> None:
        """Handle device-specific availability changes."""
        if dev_id not in (self._panel.dev_id, self._gateway.gw_sn):
            return

        self._attr_available = available
        self.schedule_update_ha_state()
