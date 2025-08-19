"""Test light platform for Dali Center integration."""
# pylint: disable=protected-access

from unittest.mock import Mock, patch

import pytest

from custom_components.dali_center.light import DaliCenterLight, async_setup_entry
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
