"""Support for DALI Center Scene entities."""

import logging
from typing import Any

from propcache.api import cached_property
from PySrDaliGateway import DaliGateway, Scene
from PySrDaliGateway.helper import gen_device_unique_id, gen_group_unique_id

from homeassistant.components.scene import Scene as SceneEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .entity import GatewayAvailabilityMixin
from .helper import gateway_to_dict
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
        Scene(gateway, **scene) for scene in entry.data.get("scenes", [])
    ]

    _LOGGER.debug("Setting up scene platform with %d scenes", len(scenes))

    scene_entities: list[DaliCenterScene] = []
    for scene in scenes:
        try:
            scene_details = await gateway.read_scene(
                scene.scene_id, getattr(scene, "channel", 0)
            )
            _LOGGER.debug(
                "Loaded scene details for %s: %d devices",
                scene.name,
                len(scene_details.get("devices", [])),
            )

            scene_entities.append(
                DaliCenterScene(scene, gateway_to_dict(gateway), scene_details)
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
        self, scene: Scene, gateway: dict[str, Any], scene_details: dict[str, Any]
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
        ent_reg = er.async_get(self.hass)
        mapped_entities: list[str] = []

        for device in self._scene_details["devices"]:
            # Use SDK helper to generate correct unique_id
            if device["dev_type"] == "0401":
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

            if entity_id:
                mapped_entities.append(entity_id)

        return {
            "scene_id": self._scene.scene_id,
            "area_id": self._scene_details["area_id"],
            "channel": self._scene_details["channel"],
            "entity_id": mapped_entities,
        }

    async def async_activate(self, **kwargs: Any) -> None:
        """Activate the DALI scene."""
        _LOGGER.debug("Activating scene: %s", self._attr_name)
        await self.hass.async_add_executor_job(self._scene.activate)
