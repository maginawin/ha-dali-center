"""Support for Dali Center Gateway Control Buttons."""

from __future__ import annotations

import logging

from PySrDaliGateway import CallbackEventType, DaliGateway, Device
from PySrDaliGateway.helper import is_light_device

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, MANUFACTURER, SIGNAL_ADD_ENTITIES, SIGNAL_SCAN_STATE
from .entity import DaliDeviceEntity
from .types import DaliCenterConfigEntry

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1  # Serial button presses to prevent race conditions


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DaliCenterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Dali Center button entities from config entry."""
    gateway = entry.runtime_data.gateway
    devices = entry.runtime_data.devices

    buttons: list[ButtonEntity] = [
        DaliCenterGatewayRestartButton(gateway),
        DaliCenterScanBusButton(gateway, entry),
        DaliCenterStopScanButton(gateway, entry),
    ]

    buttons.extend(
        DaliCenterDeviceIdentifyButton(device)
        for device in devices
        if is_light_device(device.dev_type)
    )

    async_add_entities(buttons)

    @callback
    def _async_add_new_identify_buttons(new_devices: list[Device]) -> None:
        """Add new identify buttons discovered by bus scan."""
        new_buttons = [
            DaliCenterDeviceIdentifyButton(device)
            for device in new_devices
            if is_light_device(device.dev_type)
        ]
        if new_buttons:
            async_add_entities(new_buttons)

    entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            f"{SIGNAL_ADD_ENTITIES}_{entry.entry_id}",
            _async_add_new_identify_buttons,
        )
    )


class DaliCenterGatewayRestartButton(ButtonEntity):
    """Representation of a Dali Center Gateway Restart Button."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:restart"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, gateway: DaliGateway) -> None:
        """Initialize the gateway restart button."""

        self._gateway = gateway
        self._attr_name = f"{gateway.name} Restart"
        self._attr_unique_id = f"{gateway.gw_sn}_restart"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, gateway.gw_sn)},
        )

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added to hass."""

        self.async_on_remove(
            self._gateway.register_listener(
                CallbackEventType.ONLINE_STATUS,
                self._handle_availability,
                self._gateway.gw_sn,
            )
        )

    async def async_press(self) -> None:
        """Handle button press to restart gateway."""
        _LOGGER.info("Restarting gateway %s", self._gateway.gw_sn)
        self._gateway.restart_gateway()

    @callback
    def _handle_availability(self, available: bool) -> None:
        self._attr_available = available
        self.schedule_update_ha_state()


class DaliCenterDeviceIdentifyButton(DaliDeviceEntity, ButtonEntity):
    """Representation of a Dali Center Device Identify Button."""

    _attr_device_class = ButtonDeviceClass.IDENTIFY
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, device: Device) -> None:
        """Initialize the device identify button."""
        super().__init__(device)
        self._device = device
        self._attr_name = "Identify"
        self._attr_unique_id = f"{device.unique_id}_identify"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.dev_id)},
            name=device.name,
            manufacturer=MANUFACTURER,
            model=device.model,
            via_device=(DOMAIN, device.gw_sn),
        )

    async def async_press(self) -> None:
        """Handle button press to identify device."""
        _LOGGER.debug("Identifying device %s", self._device.dev_id)
        self._device.identify()


class DaliCenterScanBusButton(ButtonEntity):
    """Button to trigger a DALI bus scan on the gateway."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:magnify-scan"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, gateway: DaliGateway, entry: DaliCenterConfigEntry) -> None:
        """Initialize the scan bus button."""
        self._gateway = gateway
        self._entry = entry
        self._attr_name = "Scan Bus"
        self._attr_unique_id = f"{gateway.gw_sn}_scan_bus"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, gateway.gw_sn)},
        )

    @property
    def available(self) -> bool:
        """Scan button is unavailable while a scan is in progress."""
        return not self._gateway.bus_scanning

    async def async_added_to_hass(self) -> None:
        """Subscribe to scan state changes to update availability."""
        # Import here to avoid circular dependency at module level.
        from . import _async_do_bus_scan  # noqa: PLC0415

        self._do_bus_scan = _async_do_bus_scan

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{SIGNAL_SCAN_STATE}_{self._entry.entry_id}",
                self._handle_scan_state,
            )
        )

        self.async_on_remove(
            self._gateway.register_listener(
                CallbackEventType.ONLINE_STATUS,
                self._handle_availability,
                self._gateway.gw_sn,
            )
        )

    async def async_press(self) -> None:
        """Handle button press to start bus scan."""
        _LOGGER.info("Bus scan requested for gateway %s", self._gateway.gw_sn)
        # Run in background so the button press returns immediately.
        self.hass.async_create_task(self._do_bus_scan(self.hass, self._entry))

    @callback
    def _handle_scan_state(self, scanning: bool) -> None:
        """Update availability when scan state changes."""
        self.async_write_ha_state()

    @callback
    def _handle_availability(self, available: bool) -> None:
        self.async_write_ha_state()


class DaliCenterStopScanButton(ButtonEntity):
    """Button to stop an in-progress DALI bus scan."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:stop"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, gateway: DaliGateway, entry: DaliCenterConfigEntry) -> None:
        """Initialize the stop scan button."""
        self._gateway = gateway
        self._entry = entry
        self._attr_name = "Stop Scan"
        self._attr_unique_id = f"{gateway.gw_sn}_stop_scan"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, gateway.gw_sn)},
        )

    @property
    def available(self) -> bool:
        """Stop button is only available while a scan is in progress."""
        return self._gateway.bus_scanning

    async def async_added_to_hass(self) -> None:
        """Subscribe to scan state changes to update availability."""
        from . import _async_do_stop_scan  # noqa: PLC0415

        self._do_stop_scan = _async_do_stop_scan

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{SIGNAL_SCAN_STATE}_{self._entry.entry_id}",
                self._handle_scan_state,
            )
        )

        self.async_on_remove(
            self._gateway.register_listener(
                CallbackEventType.ONLINE_STATUS,
                self._handle_availability,
                self._gateway.gw_sn,
            )
        )

    async def async_press(self) -> None:
        """Handle button press to stop bus scan."""
        _LOGGER.info("Stop scan requested for gateway %s", self._gateway.gw_sn)
        await self._do_stop_scan(self.hass, self._entry)

    @callback
    def _handle_scan_state(self, scanning: bool) -> None:
        """Update availability when scan state changes."""
        self.async_write_ha_state()

    @callback
    def _handle_availability(self, available: bool) -> None:
        self.async_write_ha_state()
