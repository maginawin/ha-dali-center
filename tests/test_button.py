"""Test button platform for Dali Center integration."""
# pylint: disable=protected-access

import pytest
from unittest.mock import Mock, patch

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry

from custom_components.dali_center.button import (
    async_setup_entry,
    get_panel_button_count,
    DaliCenterSceneButton,
    DaliCenterPanelButton
)
from custom_components.dali_center.const import DOMAIN
from custom_components.dali_center.types import DaliCenterData
from tests.conftest import (
    MockDaliGateway,
    MockDevice,
    MockScene,
    MOCK_GATEWAY_SN
)


class TestGetPanelButtonCount:
    """Test the get_panel_button_count function."""

    def test_get_panel_button_count_2_buttons(self):
        """Test getting button count for 2-button panel."""
        result = get_panel_button_count("0302")
        assert result == 2

    def test_get_panel_button_count_4_buttons(self):
        """Test getting button count for 4-button panel."""
        result = get_panel_button_count("0304")
        assert result == 4

    def test_get_panel_button_count_6_buttons(self):
        """Test getting button count for 6-button panel."""
        result = get_panel_button_count("0306")
        assert result == 6

    def test_get_panel_button_count_8_buttons(self):
        """Test getting button count for 8-button panel."""
        result = get_panel_button_count("0308")
        assert result == 8

    def test_get_panel_button_count_unknown_default(self):
        """Test getting button count for unknown device type returns default."""
        result = get_panel_button_count("unknown")
        assert result == 4

    def test_get_panel_button_count_empty_string(self):
        """Test getting button count for empty string returns default."""
        result = get_panel_button_count("")
        assert result == 4


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
    async def test_async_setup_entry_with_panel_devices(
        self, mock_hass, mock_add_entities
    ):
        """Test setup with panel button devices."""
        config_entry = self.create_config_entry_with_data({
            "scenes": [],
            "devices": [
                {
                    "sn": "panel001", "name": "Panel 1",
                    "dev_type": "0304", "type": 2
                }
            ]
        })

        with patch(
            "custom_components.dali_center.button.is_panel_device",
            return_value=True
        ):
            await async_setup_entry(mock_hass, config_entry, mock_add_entities)

        mock_add_entities.assert_called_once()
        entities = mock_add_entities.call_args[0][0]
        # 0304 device type should create 4 buttons
        assert len(entities) == 4
        for entity in entities:
            assert isinstance(entity, DaliCenterPanelButton)

    @pytest.mark.asyncio
    async def test_async_setup_entry_mixed_entities(
        self, mock_hass, mock_add_entities
    ):
        """Test setup with both scenes and panel devices."""
        config_entry = self.create_config_entry_with_data({
            "scenes": [
                {"sn": "scene001", "name": "Scene 1", "type": 1},
                {"sn": "scene002", "name": "Scene 2", "type": 1}
            ],
            "devices": [
                {"sn": "panel001", "name": "Panel 1",
                    "dev_type": "0302", "type": 2}
            ]
        })

        with patch(
            "custom_components.dali_center.button.is_panel_device",
            return_value=True
        ):
            await async_setup_entry(mock_hass, config_entry, mock_add_entities)

        mock_add_entities.assert_called_once()
        entities = mock_add_entities.call_args[0][0]
        # 2 scenes + 2 panel buttons (0302 = 2 buttons)
        assert len(entities) == 4
        scene_buttons = [e for e in entities if isinstance(
            e, DaliCenterSceneButton)]
        panel_buttons = [e for e in entities if isinstance(
            e, DaliCenterPanelButton)]
        assert len(scene_buttons) == 2
        assert len(panel_buttons) == 2

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

    @pytest.mark.asyncio
    async def test_async_setup_entry_non_panel_devices_ignored(
        self, mock_hass, mock_add_entities
    ):
        """Test that non-panel devices are ignored."""
        config_entry = self.create_config_entry_with_data({
            "scenes": [],
            "devices": [
                {"sn": "light001", "name": "Light 1",
                    "dev_type": "0101", "type": 1}
            ]
        })

        with patch(
            "custom_components.dali_center.button.is_panel_device", 
            return_value=False
        ):
            await async_setup_entry(mock_hass, config_entry, mock_add_entities)

        mock_add_entities.assert_not_called()


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


class TestDaliCenterPanelButton:
    """Test the DaliCenterPanelButton class."""

    @pytest.fixture
    def mock_device(self):
        """Create mock panel device."""
        device = MockDevice()
        device.name = "Panel Device"
        device.unique_id = "gw123_panel001"
        device.dev_id = "panel001"
        device.press_button = Mock()
        return device

    @pytest.fixture
    def panel_button(self, mock_device):
        """Create panel button instance."""
        return DaliCenterPanelButton(mock_device, 1)

    def test_panel_button_name(self, panel_button, mock_device):
        """Test panel button name property."""
        expected_name = f"{mock_device.name} Button 1"
        assert panel_button.name == expected_name

    def test_panel_button_unique_id(self, panel_button, mock_device):
        """Test panel button unique_id property."""
        expected_id = f"{mock_device.unique_id}_btn_1"
        assert panel_button.unique_id == expected_id

    def test_panel_button_device_info(self, panel_button, mock_device):
        """Test panel button device_info property."""
        device_info = panel_button.device_info
        assert device_info is not None
        assert device_info["identifiers"] == {
            ("dali_center", mock_device.dev_id)}

    @pytest.mark.asyncio
    async def test_panel_button_async_press(self, panel_button, mock_device):
        """Test panel button press action."""
        await panel_button.async_press()
        mock_device.press_button.assert_called_once_with(1)

    def test_panel_button_different_button_ids(self, mock_device):
        """Test panel buttons with different button IDs."""
        button2 = DaliCenterPanelButton(mock_device, 2)
        button3 = DaliCenterPanelButton(mock_device, 3)

        assert "Button 2" in button2.name
        assert "Button 3" in button3.name
        assert button2.unique_id.endswith("_btn_2")
        assert button3.unique_id.endswith("_btn_3")
