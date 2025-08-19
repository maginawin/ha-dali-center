"""Provides device triggers for Dali Center event entities."""

from __future__ import annotations

from typing import Any, cast
import voluptuous as vol

from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.components.homeassistant.triggers import event as event_trigger
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_ENTITY_ID,
    CONF_EVENT_DATA,
    CONF_PLATFORM,
    CONF_TYPE,
)

from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.entity import get_capability
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType
import logging

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(  # type: ignore[misc]
    {
        vol.Required(CONF_ENTITY_ID): cv.entity_id_or_uuid,
        vol.Required(CONF_TYPE): str,
    }
)


async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, Any]]:
    """List device triggers for event entities."""
    registry = er.async_get(hass)
    triggers: list[dict[str, Any]] = []

    # Find all event entities for this device from our domain
    entries = [
        entry
        for entry in er.async_entries_for_device(registry, device_id)
        if entry.domain == "event" and entry.platform == DOMAIN
    ]

    for entry in entries:
        event_types = get_capability(hass, entry.entity_id, "event_types")
        _LOGGER.debug(
            "Processing entry %s, entity_id=%s, event_types=%s",
            entry.id, entry.entity_id, event_types
        )

        if not event_types:
            _LOGGER.debug(
                "No event_types found for %s, skipping", entry.entity_id
            )
            continue

        for event_type in event_types:
            trigger: dict[str, Any] = {
                CONF_PLATFORM: "device",
                CONF_DEVICE_ID: device_id,
                CONF_DOMAIN: DOMAIN,
                CONF_ENTITY_ID: entry.entity_id,
                CONF_TYPE: event_type,
            }
            triggers.append(trigger)
            _LOGGER.debug("Created device trigger: %s", trigger)

    return triggers


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Attach a trigger."""
    # Use event trigger to listen for actual events, not state changes
    # This prevents triggering on entity reloads
    event_config: dict[str, Any] = {
        CONF_PLATFORM: "event",
        event_trigger.CONF_EVENT_TYPE: f"{DOMAIN}_event",
        CONF_EVENT_DATA: {
            "entity_id": config[CONF_ENTITY_ID],
            "event_type": config[CONF_TYPE],
        },
    }

    _LOGGER.debug(
        "Setting up device trigger: entity=%s, event_type=%s",
        config[CONF_ENTITY_ID], config[CONF_TYPE]
    )

    validated_config = cast(
        ConfigType, event_trigger.TRIGGER_SCHEMA(event_config))
    return await event_trigger.async_attach_trigger(
        hass, validated_config, action, trigger_info, platform_type="device"
    )


async def async_validate_trigger_config(
    _: HomeAssistant, config: ConfigType
) -> ConfigType:
    """Validate config."""
    return cast(ConfigType, TRIGGER_SCHEMA(config))
