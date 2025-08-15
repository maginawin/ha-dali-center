"""Test button platform for Dali Center integration."""
# pylint: disable=protected-access

import pytest
from unittest.mock import Mock

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry

from custom_components.dali_center.button import (
    async_setup_entry,
    DaliCenterSceneButton
)
from custom_components.dali_center.const import DOMAIN
from custom_components.dali_center.types import DaliCenterData
from tests.conftest import (
    MockDaliGateway,
    MockScene,
    MOCK_GATEWAY_SN
)



class TestButtonPlatformSetup:
    """Test the button platform setup."""

    @pytest.fixture
    def mock_hass(self):
        """Create mock HomeAssistant instance."""
        return Mock(spec=HomeAssistant)

    def create_config_entry_with_data(self, data):
        """Create config entry with specific data."""
        gateway = MockDaliGateway()
        entry = ConfigEntry(
            version=1,
            minor_version=1,
            domain=DOMAIN,
            title="Test Gateway",
            data=data,
            source="user",
            entry_id="test_entry_id",
            unique_id=MOCK_GATEWAY_SN,
            options={},
            discovery_keys={},
            subentries_data=None,
        )
        entry.runtime_data = DaliCenterData(gateway=gateway)
        return entry

    @pytest.fixture
    def mock_add_entities(self):
        """Create mock add_entities callback."""
        return Mock(spec=AddEntitiesCallback)

    @pytest.mark.asyncio
    async def test_async_setup_entry_with_scenes(
        self, mock_hass, mock_add_entities
    ):
        """Test setup with scene buttons."""
        config_entry = self.create_config_entry_with_data({
            "scenes": [
                {"sn": "scene001", "name": "Living Room", "type": 1}
            ],
            "devices": []
        })

        await async_setup_entry(mock_hass, config_entry, mock_add_entities)

        mock_add_entities.assert_called_once()
        entities = mock_add_entities.call_args[0][0]
        assert len(entities) == 1
        assert isinstance(entities[0], DaliCenterSceneButton)

    @pytest.mark.asyncio
    async def test_async_setup_entry_with_non_scene_devices(
        self, mock_hass, mock_add_entities
    ):
        """Test setup with non-scene devices (ignored)."""
        config_entry = self.create_config_entry_with_data({
            "scenes": [],
            "devices": [
                {
                    "sn": "light001", "name": "Light 1",
                    "dev_type": "0101", "type": 1
                }
            ]
        })

        await async_setup_entry(mock_hass, config_entry, mock_add_entities)

        mock_add_entities.assert_not_called()

    @pytest.mark.asyncio
    async def test_async_setup_entry_multiple_scenes(
        self, mock_hass, mock_add_entities
    ):
        """Test setup with multiple scenes."""
        config_entry = self.create_config_entry_with_data({
            "scenes": [
                {"sn": "scene001", "name": "Scene 1", "type": 1},
                {"sn": "scene002", "name": "Scene 2", "type": 1}
            ],
            "devices": []
        })

        await async_setup_entry(mock_hass, config_entry, mock_add_entities)

        mock_add_entities.assert_called_once()
        entities = mock_add_entities.call_args[0][0]
        assert len(entities) == 2
        for entity in entities:
            assert isinstance(entity, DaliCenterSceneButton)

    @pytest.mark.asyncio
    async def test_async_setup_entry_no_entities(
        self, mock_hass, mock_add_entities
    ):
        """Test setup with no scenes or panel devices."""
        config_entry = self.create_config_entry_with_data({
            "scenes": [],
            "devices": []
        })

        await async_setup_entry(mock_hass, config_entry, mock_add_entities)

        mock_add_entities.assert_not_called()

    @pytest.mark.asyncio
    async def test_async_setup_entry_duplicate_scenes(
        self, mock_hass, mock_add_entities
    ):
        """Test setup handles duplicate scenes correctly."""
        config_entry = self.create_config_entry_with_data({
            "scenes": [
                {"sn": "scene001", "name": "Scene 1", "type": 1},
                # Same ID as previous scene
                {"sn": "scene001", "name": "Scene 1 Duplicate", "type": 1}
            ],
            "devices": []
        })

        await async_setup_entry(mock_hass, config_entry, mock_add_entities)

        mock_add_entities.assert_called_once()
        entities = mock_add_entities.call_args[0][0]
        # Should only create one entity for duplicate scene IDs
        assert len(entities) == 1



class TestDaliCenterSceneButton:
    """Test the DaliCenterSceneButton class."""

    @pytest.fixture
    def mock_scene(self):
        """Create mock scene."""
        scene = MockScene()
        scene.scene_id = "scene001"
        scene.name = "Living Room"
        scene.unique_id = "gw123_scene001"
        scene.gw_sn = MOCK_GATEWAY_SN
        scene.activate = Mock()
        return scene

    @pytest.fixture
    def scene_button(self, mock_scene):
        """Create scene button instance."""
        return DaliCenterSceneButton(mock_scene)

    def test_scene_button_name(self, scene_button, mock_scene):
        """Test scene button name property."""
        assert scene_button.name == mock_scene.name

    def test_scene_button_unique_id(self, scene_button, mock_scene):
        """Test scene button unique_id property."""
        assert scene_button.unique_id == mock_scene.unique_id

    def test_scene_button_device_info(self, scene_button, mock_scene):
        """Test scene button device_info property."""
        device_info = scene_button.device_info
        assert device_info is not None
        assert device_info["identifiers"] == {
            ("dali_center", mock_scene.gw_sn)}

    @pytest.mark.asyncio
    async def test_scene_button_async_press(self, scene_button, mock_scene):
        """Test scene button press action."""
        await scene_button.async_press()
        mock_scene.activate.assert_called_once()

