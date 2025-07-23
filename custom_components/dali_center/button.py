"""Support for Dali Center Scene Buttons."""

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from PySrDaliGateway import DaliGateway, Scene, Device
from PySrDaliGateway.helper import is_panel_device
from .types import DaliCenterConfigEntry

_LOGGER = logging.getLogger(__name__)


def get_panel_button_count(dev_type: str) -> int:
    """Get button count for panel device type."""
    button_count_map = {
        "0302": 2,
        "0304": 4,
        "0306": 6,
        "0308": 8,
    }
    return button_count_map.get(dev_type, 4)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DaliCenterConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Dali Center button entities from config entry."""
    added_scenes = set()
    added_panel_buttons = set()
    gateway: DaliGateway = entry.runtime_data.gateway

    scenes: list[Scene] = [
        Scene(gateway, scene)
        for scene in entry.data.get("scenes", [])
    ]
    devices = entry.data.get("devices", [])
    _LOGGER.info(
        "Setting up button platform: %d scenes, %d devices",
        len(scenes), len(devices)
    )

    new_entities: list[ButtonEntity] = []

    for scene in scenes:
        if scene.scene_id in added_scenes:
            continue

        new_entities.append(DaliCenterSceneButton(scene))
        added_scenes.add(scene.scene_id)

    for device_data in devices:
        if is_panel_device(device_data.get("dev_type", "")):
            device = Device(gateway, device_data)
            button_count = get_panel_button_count(device.dev_type)
            _LOGGER.warning("Processing device: %s", device_data)

            for button_id in range(1, button_count + 1):
                button_unique_id = f"{device.unique_id}_btn_{button_id}"
                if button_unique_id not in added_panel_buttons:
                    new_entities.append(
                        DaliCenterPanelButton(device, button_id)
                    )
                    added_panel_buttons.add(button_unique_id)

    if new_entities:
        async_add_entities(new_entities)


class DaliCenterSceneButton(ButtonEntity):
    """Representation of a Dali Center Scene Button."""

    def __init__(self, scene: Scene) -> None:
        self._scene = scene
        _LOGGER.debug("Scene button: %s", scene)
        self._name = f"{scene.name}"
        self._unique_id = scene.unique_id

    @property
    def name(self) -> str:
        return self._name

    @property
    def unique_id(self) -> str:
        return self._unique_id

    @property
    def device_info(self) -> DeviceInfo | None:
        return DeviceInfo(
            identifiers={(DOMAIN, self._scene.gw_sn)},
        )

    async def async_press(self) -> None:
        _LOGGER.debug("Activating scene %s", self._scene.scene_id)
        self._scene.activate()


class DaliCenterPanelButton(ButtonEntity):
    """Representation of a Dali Center Panel Button."""

    def __init__(self, device: Device, button_id: int) -> None:
        self._device = device
        self._button_id = button_id
        self._unique_id = f"{device.unique_id}_btn_{button_id}"
        self._name = f"{device.name} Button {button_id}"
        _LOGGER.debug("Panel button: %s", self._name)

    @property
    def name(self) -> str:
        return self._name

    @property
    def unique_id(self) -> str:
        return self._unique_id

    @property
    def device_info(self) -> DeviceInfo | None:
        return DeviceInfo(
            identifiers={(DOMAIN, self._device.dev_id)},
        )

    async def async_press(self) -> None:
        _LOGGER.debug("Pressing panel button %s", self._name)
        self._device.press_button(self._button_id)
