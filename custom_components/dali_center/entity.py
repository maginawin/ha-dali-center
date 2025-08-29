"""Base entity for DALI Center integration."""

from __future__ import annotations

import logging

from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)


class GatewayAvailabilityMixin(Entity):
    """Mixin to handle gateway availability for DALI entities."""

    def __init__(self, gw_sn: str) -> None:
        """Initialize the gateway availability mixin."""
        super().__init__()
        self._gw_sn = gw_sn
        self._gateway_available = True
        self._device_available = True  # Track device-specific availability

    async def async_added_to_hass(self) -> None:
        """Handle entity addition to Home Assistant."""
        await super().async_added_to_hass()

        # Listen for gateway availability changes
        gateway_signal = f"dali_center_update_available_{self._gw_sn}"
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, gateway_signal, self._handle_gateway_availability
            )
        )

    @callback
    def _handle_gateway_availability(self, available: bool) -> None:
        """Handle gateway availability changes."""
        _LOGGER.debug(
            "Gateway %s availability changed to %s for entity %s",
            self._gw_sn,
            available,
            getattr(self, "entity_id", "unknown"),
        )

        self._gateway_available = available
        self._update_entity_availability()

    @callback
    def _update_entity_availability(self) -> None:
        """Update entity availability based on gateway and device status."""
        old_available = getattr(self, "_attr_available", True)
        new_available = self._gateway_available and self._device_available

        if old_available != new_available:
            self._attr_available = new_available
            _LOGGER.debug(
                "Entity %s availability changed: %s (gateway: %s, device: %s)",
                getattr(self, "entity_id", "unknown"),
                new_available,
                self._gateway_available,
                self._device_available,
            )
            self.schedule_update_ha_state()

    @callback
    def _handle_device_availability(self, available: bool) -> None:
        """Handle device-specific availability changes."""
        _LOGGER.debug(
            "Device availability changed to %s for entity %s",
            available,
            getattr(self, "entity_id", "unknown"),
        )

        self._device_available = available
        self._update_entity_availability()

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._gateway_available and self._device_available
