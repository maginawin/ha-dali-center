"""Support for Dali Center Scene Buttons."""

from functools import cached_property
import logging

from PySrDaliGateway import DaliGateway, Scene

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .entity import GatewayAvailabilityMixin
from .types import DaliCenterConfigEntry

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    _: HomeAssistant,
    entry: DaliCenterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Dali Center button entities from config entry."""
    added_scenes: set[int] = set()
    gateway: DaliGateway = entry.runtime_data.gateway

    scenes: list[Scene] = [
        Scene(gateway, scene) for scene in entry.data.get("scenes", [])
    ]
    _LOGGER.debug("Setting up button platform: %d scenes", len(scenes))

    new_entities: list[ButtonEntity] = []

    for scene in scenes:
        if scene.scene_id in added_scenes:
            continue

        new_entities.append(DaliCenterSceneButton(scene))
        added_scenes.add(scene.scene_id)

    if new_entities:
        async_add_entities(new_entities)


class DaliCenterSceneButton(GatewayAvailabilityMixin, ButtonEntity):
    """Representation of a Dali Center Scene Button."""

    def __init__(self, scene: Scene) -> None:
        """Initialize the scene button."""
        GatewayAvailabilityMixin.__init__(self, scene.gw_sn)
        ButtonEntity.__init__(self)

        self._scene = scene
        self._attr_name = f"{scene.name}"
        self._attr_unique_id = scene.unique_id

    @cached_property
    def device_info(self) -> DeviceInfo:
        """Return device info for the scene button."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._scene.gw_sn)},
        )

    async def async_press(self) -> None:
        """Handle button press to activate scene."""
        _LOGGER.debug("Activating scene %s", self._scene.scene_id)
        self._scene.activate()
