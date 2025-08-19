"""Support for Dali Center Scene Buttons."""

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from PySrDaliGateway import DaliGateway, Scene
from .types import DaliCenterConfigEntry

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    _: HomeAssistant,
    entry: DaliCenterConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Dali Center button entities from config entry."""
    added_scenes: set[int] = set()
    gateway: DaliGateway = entry.runtime_data.gateway

    scenes: list[Scene] = [
        Scene(gateway, scene)
        for scene in entry.data.get("scenes", [])
    ]
    _LOGGER.debug(
        "Setting up button platform: %d scenes", len(scenes)
    )

    new_entities: list[ButtonEntity] = []

    for scene in scenes:
        if scene.scene_id in added_scenes:
            continue

        new_entities.append(DaliCenterSceneButton(scene))
        added_scenes.add(scene.scene_id)

    if new_entities:
        async_add_entities(new_entities)


class DaliCenterSceneButton(ButtonEntity):
    """Representation of a Dali Center Scene Button."""

    def __init__(self, scene: Scene) -> None:
        super().__init__()
        self._scene = scene
        _LOGGER.debug("Scene button: %s", scene)
        self._attr_name = f"{scene.name}"
        self._attr_unique_id = scene.unique_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._scene.gw_sn)},
        )

    async def async_press(self) -> None:
        _LOGGER.debug("Activating scene %s", self._scene.scene_id)
        self._scene.activate()
