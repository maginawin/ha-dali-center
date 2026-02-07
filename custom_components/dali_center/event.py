"""Platform for Dali Center event entities."""

from __future__ import annotations

import logging

from PySrDaliGateway import CallbackEventType, Device, Panel
from PySrDaliGateway.helper import is_panel_device
from PySrDaliGateway.types import PanelEventType, PanelStatus

from homeassistant.components.event import EventDeviceClass, EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, MANUFACTURER, SIGNAL_ADD_ENTITIES
from .entity import DaliDeviceEntity
from .types import DaliCenterConfigEntry

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0  # Read-only event entities, no concurrency limit needed


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

    async_add_entities(DaliCenterPanelEvent(device) for device in devices)

    @callback
    def _async_add_new_panels(new_devices: list[Device]) -> None:
        """Add new panel event entities discovered by bus scan."""
        new_panels = [
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
            for device in new_devices
            if is_panel_device(device.dev_type)
        ]
        if new_panels:
            async_add_entities(DaliCenterPanelEvent(panel) for panel in new_panels)

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, f"{SIGNAL_ADD_ENTITIES}_{entry.entry_id}", _async_add_new_panels
        )
    )


class DaliCenterPanelEvent(DaliDeviceEntity, EventEntity):
    """Representation of a Dali Center Panel Event Entity."""

    _attr_device_class = EventDeviceClass.BUTTON
    _attr_name = "Panel Buttons"
    _attr_icon = "mdi:gesture-tap-button"

    def __init__(self, panel: Panel) -> None:
        """Initialize the panel event entity."""
        super().__init__(panel)
        self._panel = panel
        self._attr_unique_id = f"{panel.dev_id}_panel_events"

        self._attr_event_types = panel.get_available_event_types()
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, panel.dev_id)},
            name=panel.name,
            manufacturer=MANUFACTURER,
            model=panel.model,
            via_device=(DOMAIN, panel.gw_sn),
        )

    async def async_added_to_hass(self) -> None:
        """Handle when entity is added to hass."""
        await super().async_added_to_hass()

        self.async_on_remove(
            self._panel.register_listener(
                CallbackEventType.PANEL_STATUS, self._handle_device_update
            )
        )

        self._panel.read_status()

    @callback
    def _handle_device_update(self, status: PanelStatus) -> None:
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
