"""Support for Dali Center Gateway Control Buttons."""

import logging

from PySrDaliGateway import CallbackEventType, DaliGateway, Device
from PySrDaliGateway.helper import is_light_device

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, MANUFACTURER
from .types import DaliCenterConfigEntry

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    _: HomeAssistant,
    entry: DaliCenterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Dali Center button entities from config entry."""
    gateway = entry.runtime_data.gateway
    devices = entry.runtime_data.devices

    # Gateway buttons
    buttons: list[ButtonEntity] = [
        DaliCenterGatewayIdentifyButton(gateway),
        DaliCenterGatewayRestartButton(gateway),
    ]

    # Device identify buttons
    buttons.extend(
        DaliCenterDeviceIdentifyButton(device)
        for device in devices
        if is_light_device(device.dev_type)
    )

    async_add_entities(buttons)


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
        self._attr_device_info = {
            "identifiers": {(DOMAIN, gateway.gw_sn)},
        }

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


class DaliCenterGatewayIdentifyButton(ButtonEntity):
    """Representation of a Dali Center Gateway Identify Button."""

    _attr_has_entity_name = True
    _attr_device_class = ButtonDeviceClass.IDENTIFY
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, gateway: DaliGateway) -> None:
        """Initialize the gateway identify button."""

        self._gateway = gateway
        self._attr_name = "Identify"
        self._attr_unique_id = f"{gateway.gw_sn}_identify"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, gateway.gw_sn)},
        }

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
        """Handle button press to identify gateway."""
        _LOGGER.debug("Identifying gateway %s", self._gateway.gw_sn)
        self._gateway.identify_gateway()

    @callback
    def _handle_availability(self, available: bool) -> None:
        self._attr_available = available
        self.schedule_update_ha_state()


class DaliCenterDeviceIdentifyButton(ButtonEntity):
    """Representation of a Dali Center Device Identify Button."""

    _attr_has_entity_name = True
    _attr_device_class = ButtonDeviceClass.IDENTIFY
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, device: Device) -> None:
        """Initialize the device identify button."""

        self._device = device
        self._attr_name = "Identify"
        self._attr_unique_id = f"{device.unique_id}_identify"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device.dev_id)},
            "name": device.name,
            "manufacturer": MANUFACTURER,
            "model": device.model,
            "via_device": (DOMAIN, device.gw_sn),
        }

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added to hass."""

        self.async_on_remove(
            self._device.register_listener(
                CallbackEventType.ONLINE_STATUS, self._handle_availability
            )
        )

    async def async_press(self) -> None:
        """Handle button press to identify device."""
        _LOGGER.debug("Identifying device %s", self._device.dev_id)
        self._device.identify()

    @callback
    def _handle_availability(self, available: bool) -> None:
        self._attr_available = available
        self.schedule_update_ha_state()
