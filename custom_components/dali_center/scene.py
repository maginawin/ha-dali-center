"""Support for DALI Center Scene entities."""

import logging
from typing import Any

from propcache.api import cached_property
from PySrDaliGateway import DaliGateway, DaliGatewayType, Scene, SceneType
from PySrDaliGateway.helper import gen_device_unique_id, gen_group_unique_id

from homeassistant.components.scene import Scene as SceneEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .entity import GatewayAvailabilityMixin
from .types import DaliCenterConfigEntry

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DaliCenterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up DALI Center scene entities from config entry."""
    gateway: DaliGateway = entry.runtime_data.gateway

    scenes: list[Scene] = [
        Scene(gateway, scene) for scene in entry.data.get("scenes", [])
    ]

    _LOGGER.debug("Setting up scene platform with %d scenes", len(scenes))

    # Pre-load scene details for all scenes
    scene_entities: list[DaliCenterScene] = []
    for scene in scenes:
        try:
            # Load scene details during setup
            scene_details = await gateway.read_scene(
                scene.scene_id, getattr(scene, "channel", 0)
            )
            _LOGGER.debug(
                "Loaded scene details for %s: %d devices",
                scene.name,
                len(scene_details.get("devices", [])),
            )

            scene_entities.append(
                DaliCenterScene(scene, gateway.to_dict(), scene_details)
            )
        except (OSError, ValueError, KeyError):
            _LOGGER.exception(
                "Failed to read scene details for %s, skipping scene",
                scene.name,
            )

    if scene_entities:
        async_add_entities(scene_entities)


class DaliCenterScene(GatewayAvailabilityMixin, SceneEntity):
    """Representation of a DALI Center Scene."""

    def __init__(
        self, scene: Scene, gateway: DaliGatewayType, scene_details: SceneType
    ) -> None:
        """Initialize the DALI scene."""
        GatewayAvailabilityMixin.__init__(self, scene.gw_sn, gateway)
        SceneEntity.__init__(self)

        self._scene = scene
        self._attr_name = scene.name
        self._attr_unique_id = scene.unique_id
        self._scene_details = scene_details

    @cached_property
    def device_info(self) -> DeviceInfo:
        """Return device info for the scene."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._scene.gw_sn)},
        )

    @cached_property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return scene device information as extra state attributes."""
        # Get entity registry to map device unique_ids to actual entity_ids
        ent_reg = er.async_get(self.hass)

        # Build entity states map in HA standard format
        entity_states: dict[str, dict[str, Any]] = {}
        mapped_entities: list[str] = []
        raw_devices: list[dict[str, Any]] = []

        for device in self._scene_details["devices"]:
            # Use SDK helper to generate correct unique_id
            if device["dev_type"] == "0401":
                # It's a group
                device_unique_id = gen_group_unique_id(
                    device["address"],
                    device["channel"],
                    self._scene.gw_sn,
                )
            else:
                device_unique_id = gen_device_unique_id(
                    device["dev_type"],
                    device["channel"],
                    device["address"],
                    self._scene.gw_sn,
                )
            entity_id = ent_reg.async_get_entity_id("light", DOMAIN, device_unique_id)

            device_state: dict[str, Any] = {}
            if light_property := device["property"]:
                # Map to HA light state format
                if light_property["is_on"] is not None:
                    device_state["state"] = "on" if light_property["is_on"] else "off"
                if light_property["brightness"] is not None:
                    device_state["brightness"] = light_property["brightness"]
                if light_property["color_temp_kelvin"] is not None:
                    device_state["color_temp_kelvin"] = light_property[
                        "color_temp_kelvin"
                    ]
                if light_property["white_level"] is not None:
                    device_state["white_level"] = light_property["white_level"]

            # If we found a real entity_id, use it
            if entity_id:
                mapped_entities.append(entity_id)
                if device_state:
                    entity_states[entity_id] = device_state

            # Keep raw device info for debugging
            raw_devices.append(
                {
                    "address": device["address"],
                    "channel": device["channel"],
                    "device_type": device["dev_type"],
                    "device_unique_id": device_unique_id,
                    "entity_id": entity_id,
                    "mapped": entity_id is not None,
                }
            )

        return {
            "scene_id": self._scene.scene_id,
            "area_id": self._scene_details["area_id"],
            "channel": self._scene_details["channel"],
            "entity_states": entity_states,
            "entity_id": mapped_entities,
            "device_count": len(raw_devices),
            "devices": raw_devices,
        }

    async def async_activate(self, **kwargs: Any) -> None:
        """Activate the DALI scene."""
        _LOGGER.debug("Activating scene: %s", self._attr_name)
        await self.hass.async_add_executor_job(self._scene.activate)
