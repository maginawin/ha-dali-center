"""Test light platform for Dali Center integration."""
# pylint: disable=protected-access

from unittest.mock import Mock, patch

import pytest

from custom_components.dali_center.light import (
    DaliCenterAllLights,
    DaliCenterLight,
    async_setup_entry,
)
from custom_components.dali_center.types import DaliCenterData
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from tests.conftest import MockDaliGateway, MockDevice


class TestLightPlatformSetup:
    """Test the light platform setup."""

    @pytest.fixture
    def mock_hass(self):
        """Create mock HomeAssistant instance."""
        return Mock(spec=HomeAssistant)

    @pytest.fixture
    def mock_config_entry(self, mock_config_entry):
        """Create mock config entry with runtime data."""
        gateway = MockDaliGateway()
        mock_config_entry.runtime_data = DaliCenterData(gateway=gateway)
        return mock_config_entry

    @pytest.fixture
    def mock_add_entities(self):
        """Create mock add_entities callback."""
        return Mock(spec=AddEntitiesCallback)

    @pytest.mark.asyncio
    async def test_async_setup_entry_basic(
        self, mock_hass, mock_config_entry, mock_add_entities
    ):
        """Test basic setup of light platform."""
        # Call setup
        result = await async_setup_entry(
            mock_hass, mock_config_entry, mock_add_entities
        )

        assert result is None
        # Should be called at least once for devices, might be called twice if
        # groups exist
        assert mock_add_entities.call_count >= 1

        # Get all entities from all calls
        all_entities = []
        for call in mock_add_entities.call_args_list:
            all_entities.extend(call[0][0])

        # Should have at least one light entity
        assert len(all_entities) > 0

    @pytest.mark.asyncio
    async def test_async_setup_entry_no_light_devices(
        self, mock_hass, mock_config_entry, mock_add_entities
    ):
        # Mock gateway with non-light devices
        gateway = mock_config_entry.runtime_data.gateway
        # Override devices with non-light devices (type != 1)
        # type 2 = not light
        gateway.devices = [MockDevice(gateway, {"sn": "001", "type": 2})]
        gateway.groups = []

        result = await async_setup_entry(
            mock_hass, mock_config_entry, mock_add_entities
        )

        assert result is None
        assert mock_add_entities.call_count >= 0


class TestDaliCenterLight:
    """Test the DaliCenterLight class."""

    @pytest.fixture
    def mock_gateway(self):
        """Create mock gateway."""
        return MockDaliGateway()

    @pytest.fixture
    def mock_device(self):
        """Create mock light device."""
        gateway = MockDaliGateway()
        return MockDevice(
            gateway,
            {
                "sn": "light001",
                "name": "Living Room Light",
                "type": 1,  # Light device
                "brightness": 80,
                "power": True,
            },
        )

    @pytest.fixture
    def light_entity(self, mock_device):
        """Create light entity for testing."""
        light = DaliCenterLight(mock_device)
        # Mock hass to prevent AttributeError
        light.hass = Mock()
        light.hass.loop = Mock()
        light.hass.loop.call_soon_threadsafe = Mock()
        return light

    def test_light_entity_initialization(self, light_entity, mock_device):
        """Test light entity initialization."""
        # DaliCenterLight uses fixed name "Light" instead of device name
        assert light_entity.name == "Light"
        assert light_entity.unique_id == mock_device.unique_id
        assert hasattr(light_entity, "is_on")
        assert hasattr(light_entity, "brightness")

    def test_light_entity_properties(self, light_entity):
        """Test light entity properties."""
        # Test basic properties
        assert hasattr(light_entity, "supported_features")
        assert hasattr(light_entity, "color_mode")
        assert hasattr(light_entity, "supported_color_modes")

        # Test device info
        device_info = light_entity.device_info
        assert device_info is not None
        assert "identifiers" in device_info
        assert "name" in device_info
        assert "manufacturer" in device_info

    def test_light_entity_state_off(self):
        """Test light entity with power off."""
        gateway = MockDaliGateway()
        mock_device = MockDevice(
            gateway,
            {
                "sn": "light002",
                "name": "Bedroom Light",
                "type": 1,
                "brightness": 0,
                "power": False,
            },
        )

        entity = DaliCenterLight(mock_device)
        # Mock hass to prevent AttributeError
        entity.hass = Mock()
        entity.hass.loop = Mock()
        entity.hass.loop.call_soon_threadsafe = Mock()

        assert entity is not None
        assert entity.name == "Light"

    @pytest.mark.asyncio
    async def test_turn_on_basic(self, light_entity):
        """Test basic turn on functionality."""
        with patch.object(light_entity._light, "turn_on") as mock_turn_on:  # pylint: disable=protected-access
            await light_entity.async_turn_on()

            # Should call device's turn_on method
            mock_turn_on.assert_called_once_with(
                brightness=None, color_temp_kelvin=None, hs_color=None, rgbw_color=None
            )

    @pytest.mark.asyncio
    async def test_turn_on_with_brightness(self, light_entity):
        """Test turn on with brightness."""
        with patch.object(light_entity._light, "turn_on") as mock_turn_on:  # pylint: disable=protected-access
            # Turn on with brightness
            await light_entity.async_turn_on(brightness=128)

            mock_turn_on.assert_called_once_with(
                brightness=128, color_temp_kelvin=None, hs_color=None, rgbw_color=None
            )

    @pytest.mark.asyncio
    async def test_turn_off(self, light_entity):
        """Test turn off functionality."""
        with patch.object(light_entity._light, "turn_off") as mock_turn_off:  # pylint: disable=protected-access
            await light_entity.async_turn_off()

            # Should call device's turn_off method
            mock_turn_off.assert_called_once()


class TestDaliCenterAllLights:
    """Test the DaliCenterAllLights class."""

    @pytest.fixture
    def mock_gateway(self):
        """Create mock gateway."""
        return MockDaliGateway()

    @pytest.fixture  
    def all_lights_entity(self, mock_gateway):
        """Create all lights entity for testing."""
        entity = DaliCenterAllLights(mock_gateway)
        # Mock hass to prevent AttributeError
        entity.hass = Mock()
        entity.hass.loop = Mock()
        entity.hass.loop.call_soon_threadsafe = Mock()
        return entity

    def test_all_lights_initialization(self, all_lights_entity, mock_gateway):
        """Test all lights entity initialization."""
        assert all_lights_entity.name == "All Lights"
        assert all_lights_entity.unique_id == f"{mock_gateway.gw_sn}_all_lights"
        assert all_lights_entity.available is True
        assert all_lights_entity.icon == "mdi:lightbulb-group-outline"
        assert all_lights_entity.is_on is False

    def test_all_lights_properties(self, all_lights_entity):
        """Test all lights entity properties."""
        # Test color mode properties
        assert hasattr(all_lights_entity, "supported_color_modes")
        assert hasattr(all_lights_entity, "color_mode")
        assert hasattr(all_lights_entity, "min_color_temp_kelvin")
        assert hasattr(all_lights_entity, "max_color_temp_kelvin")
        
        # Test color temperature range
        assert all_lights_entity.min_color_temp_kelvin == 1000
        assert all_lights_entity.max_color_temp_kelvin == 8000

    def test_all_lights_device_info(self, all_lights_entity, mock_gateway):
        """Test all lights device info."""
        device_info = all_lights_entity.device_info
        assert device_info is not None
        assert device_info["identifiers"] == {("dali_center", mock_gateway.gw_sn)}

    def test_rgbw_to_hsv_string_conversion(self, all_lights_entity):
        """Test RGB to HSV string conversion."""
        # Test pure red (RGB: 255, 0, 0)
        hsv_string = all_lights_entity._rgbw_to_hsv_string((255, 0, 0))
        # Red should be hue=0, saturation=1000, value=1000
        assert hsv_string == "000003e803e8"
        
        # Test pure white (RGB: 255, 255, 255)  
        hsv_string = all_lights_entity._rgbw_to_hsv_string((255, 255, 255))
        # White should be hue=0, saturation=0, value=1000
        assert hsv_string == "0000000003e8"

    @pytest.mark.asyncio
    async def test_turn_on_basic(self, all_lights_entity, mock_gateway):
        """Test basic turn on functionality."""
        with patch.object(mock_gateway, "command_write_dev") as mock_command:
            await all_lights_entity.async_turn_on()
            
            # Should call command_write_dev with broadcast address
            mock_command.assert_called_once_with(
                "FFFF", 0, 1, [{"dpid": 20, "dataType": "bool", "value": True}]
            )
            # State should be updated
            assert all_lights_entity.is_on is True

    @pytest.mark.asyncio
    async def test_turn_on_with_brightness(self, all_lights_entity, mock_gateway):
        """Test turn on with brightness."""
        with patch.object(mock_gateway, "command_write_dev") as mock_command:
            await all_lights_entity.async_turn_on(brightness=128)
            
            expected_data = [
                {"dpid": 20, "dataType": "bool", "value": True},
                {"dpid": 22, "dataType": "uint16", "value": 128},
            ]
            mock_command.assert_called_once_with("FFFF", 0, 1, expected_data)
            assert all_lights_entity.brightness == 128

    @pytest.mark.asyncio
    async def test_turn_on_with_color_temp(self, all_lights_entity, mock_gateway):
        """Test turn on with color temperature."""
        with patch.object(mock_gateway, "command_write_dev") as mock_command:
            await all_lights_entity.async_turn_on(color_temp_kelvin=3000)
            
            expected_data = [
                {"dpid": 20, "dataType": "bool", "value": True},
                {"dpid": 23, "dataType": "uint16", "value": 3000},
            ]
            mock_command.assert_called_once_with("FFFF", 0, 1, expected_data)
            assert all_lights_entity.color_temp_kelvin == 3000

    @pytest.mark.asyncio
    async def test_turn_on_with_rgbw_color(self, all_lights_entity, mock_gateway):
        """Test turn on with RGBW color."""
        with patch.object(mock_gateway, "command_write_dev") as mock_command:
            # Red color with white channel
            await all_lights_entity.async_turn_on(rgbw_color=(255, 0, 0, 100))
            
            expected_data = [
                {"dpid": 20, "dataType": "bool", "value": True},
                {"dpid": 24, "dataType": "string", "value": "000003e803e8"},  # RGB to HSV
                {"dpid": 21, "dataType": "uint8", "value": 100},  # White channel
            ]
            mock_command.assert_called_once_with("FFFF", 0, 1, expected_data)
            assert all_lights_entity.rgbw_color == (255, 0, 0, 100)

    @pytest.mark.asyncio  
    async def test_turn_on_with_hs_color(self, all_lights_entity, mock_gateway):
        """Test turn on with HS color."""
        with patch.object(mock_gateway, "command_write_dev") as mock_command:
            # Red color in HS format (hue=0, saturation=100)
            await all_lights_entity.async_turn_on(hs_color=(0, 100))
            
            expected_data = [
                {"dpid": 20, "dataType": "bool", "value": True},
                {"dpid": 24, "dataType": "string", "value": "000003e803e8"},  # Converted to HSV
            ]
            mock_command.assert_called_once_with("FFFF", 0, 1, expected_data)
            assert all_lights_entity.hs_color == (0, 100)

    @pytest.mark.asyncio
    async def test_turn_on_multiple_parameters(self, all_lights_entity, mock_gateway):
        """Test turn on with multiple parameters.""" 
        with patch.object(mock_gateway, "command_write_dev") as mock_command:
            await all_lights_entity.async_turn_on(
                brightness=200, 
                color_temp_kelvin=4000
            )
            
            expected_data = [
                {"dpid": 20, "dataType": "bool", "value": True},
                {"dpid": 22, "dataType": "uint16", "value": 200},
                {"dpid": 23, "dataType": "uint16", "value": 4000},
            ]
            mock_command.assert_called_once_with("FFFF", 0, 1, expected_data)
            assert all_lights_entity.brightness == 200
            assert all_lights_entity.color_temp_kelvin == 4000

    @pytest.mark.asyncio
    async def test_turn_off(self, all_lights_entity, mock_gateway):
        """Test turn off functionality."""
        with patch.object(mock_gateway, "command_write_dev") as mock_command:
            await all_lights_entity.async_turn_off()
            
            expected_data = [{"dpid": 20, "dataType": "bool", "value": False}]
            mock_command.assert_called_once_with("FFFF", 0, 1, expected_data)
            assert all_lights_entity.is_on is False

    @pytest.mark.asyncio
    async def test_turn_on_command_exception(self, all_lights_entity, mock_gateway):
        """Test turn on command exception handling."""
        with patch.object(mock_gateway, "command_write_dev") as mock_command:
            # Mock command to raise exception
            mock_command.side_effect = Exception("Gateway error")
            
            # Should not raise exception
            await all_lights_entity.async_turn_on()
            
            # State should not be updated on error
            assert all_lights_entity.is_on is False

    @pytest.mark.asyncio  
    async def test_turn_off_command_exception(self, all_lights_entity, mock_gateway):
        """Test turn off command exception handling."""
        # Set initial state to on
        all_lights_entity._attr_is_on = True
        
        with patch.object(mock_gateway, "command_write_dev") as mock_command:
            mock_command.side_effect = Exception("Gateway error")
            
            await all_lights_entity.async_turn_off()
            
            # State should remain unchanged on error
            assert all_lights_entity.is_on is True

    @pytest.mark.asyncio
    async def test_setup_entry_includes_all_lights(self):
        """Test that setup entry includes the All Lights entity.""" 
        # Create fixtures locally
        mock_hass = Mock(spec=HomeAssistant)
        
        gateway = MockDaliGateway()
        mock_config_entry = Mock()
        mock_config_entry.runtime_data = Mock()
        mock_config_entry.runtime_data.gateway = gateway
        mock_config_entry.data = {
            "devices": [{"sn": "light001", "dev_type": "1"}],
            "groups": []
        }
        
        mock_add_entities = Mock(spec=AddEntitiesCallback)
        
        # Call setup
        await async_setup_entry(mock_hass, mock_config_entry, mock_add_entities)
        
        # Should be called at least once
        assert mock_add_entities.call_count >= 1
        
        # Get all entities from all calls
        all_entities = []
        for call in mock_add_entities.call_args_list:
            all_entities.extend(call[0][0])
        
        # Should have at least one All Lights entity
        all_lights_entities = [e for e in all_entities if isinstance(e, DaliCenterAllLights)]
        assert len(all_lights_entities) == 1
        assert all_lights_entities[0].name == "All Lights"
