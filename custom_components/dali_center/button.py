"""Support for Dali Center Gateway Control Buttons."""

import logging

from PySrDaliGateway import CallbackEventType, DaliGateway

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .types import DaliCenterConfigEntry

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    _: HomeAssistant,
    entry: DaliCenterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Dali Center button entities from config entry."""
    gateway = entry.runtime_data.gateway

    async_add_entities([DaliCenterGatewayRestartButton(gateway)])


class DaliCenterGatewayRestartButton(ButtonEntity):
    """Representation of a Dali Center Gateway Restart Button."""

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
                CallbackEventType.ONLINE_STATUS, self._handle_availability
            )
        )

    async def async_press(self) -> None:
        """Handle button press to restart gateway."""
        _LOGGER.info("Restarting gateway %s", self._gateway.gw_sn)
        self._gateway.restart_gateway()

    @callback
    def _handle_availability(self, dev_id: str, available: bool) -> None:
        """Handle device-specific availability changes."""
        if dev_id != self._gateway.gw_sn:
            return

        self._attr_available = available
        self.schedule_update_ha_state()
