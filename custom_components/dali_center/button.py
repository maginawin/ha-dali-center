"""Support for Dali Center Gateway Control Buttons."""

import logging

from propcache.api import cached_property
from PySrDaliGateway import DaliGateway

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .entity import GatewayAvailabilityMixin
from .helper import gateway_to_dict
from .types import DaliCenterConfigEntry

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    _: HomeAssistant,
    entry: DaliCenterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Dali Center button entities from config entry."""
    gateway: DaliGateway = entry.runtime_data.gateway

    _LOGGER.debug("Setting up button platform for gateway %s", gateway.gw_sn)

    async_add_entities([DaliCenterGatewayRestartButton(gateway)])


class DaliCenterGatewayRestartButton(GatewayAvailabilityMixin, ButtonEntity):
    """Representation of a Dali Center Gateway Restart Button."""

    def __init__(self, gateway: DaliGateway) -> None:
        """Initialize the gateway restart button."""
        GatewayAvailabilityMixin.__init__(self, gateway.gw_sn, gateway_to_dict(gateway))
        ButtonEntity.__init__(self)

        self._gateway_obj = gateway
        self._attr_name = f"{gateway.name} Restart"
        self._attr_unique_id = f"{gateway.gw_sn}_restart"
        self._attr_icon = "mdi:restart"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @cached_property
    def device_info(self) -> DeviceInfo:
        """Return device info for the gateway restart button."""
        return {
            "identifiers": {(DOMAIN, self._gateway_obj.gw_sn)},
        }

    async def async_press(self) -> None:
        """Handle button press to restart gateway."""
        _LOGGER.info("Restarting gateway %s", self._gateway_obj.gw_sn)
        self._gateway_obj.restart_gateway()
