"""Test config flow for Dali Center integration."""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.core import HomeAssistant

from custom_components.dali_center.config_flow import (
    DaliCenterConfigFlow,
    EntityDiscoveryMixin,
    OPTIONS_SCHEMA
)
from custom_components.dali_center.const import DOMAIN
from tests.conftest import (
    MockDaliGateway,
    MockDaliGatewayDiscovery,
    MOCK_GATEWAY_SN,
    MOCK_GATEWAY_IP
)


class TestConfigFlowConstants:
    """Test config flow constants and schemas."""

    def test_options_schema_structure(self):
        """Test OPTIONS_SCHEMA structure."""
        # Test valid data
        valid_data = {
            "refresh_devices": True,
            "refresh_groups": False,
            "refresh_scenes": True
        }
        result = OPTIONS_SCHEMA(valid_data)
        assert result["refresh_devices"] is True
        assert result["refresh_groups"] is False
        assert result["refresh_scenes"] is True

    def test_options_schema_defaults(self):
        """Test OPTIONS_SCHEMA default values."""
        # Test empty data - should use defaults
        result = OPTIONS_SCHEMA({})
        assert result["refresh_devices"] is False
        assert result["refresh_groups"] is False
        assert result["refresh_scenes"] is False

    def test_options_schema_partial(self):
        """Test OPTIONS_SCHEMA with partial data."""
        partial_data = {"refresh_devices": True}
        result = OPTIONS_SCHEMA(partial_data)
        assert result["refresh_devices"] is True
        assert result["refresh_groups"] is False  # default
        assert result["refresh_scenes"] is False  # default


class TestEntityDiscoveryMixin:
    """Test EntityDiscoveryMixin functionality."""

    @pytest.fixture
    def mixin_instance(self):
        """Create EntityDiscoveryMixin instance for testing."""
        return EntityDiscoveryMixin()

    @pytest.mark.asyncio
    async def test_discover_entities_all_types(self, mixin_instance):
        """Test discovering all entity types."""
        mock_gateway = MockDaliGateway()

        # Mock the discovery methods that would be called
        with patch.object(
            mock_gateway, "discover_devices", new_callable=AsyncMock
        ) as mock_discover_devices, \
            patch.object(
            mock_gateway, "discover_groups", new_callable=AsyncMock
        ) as mock_discover_groups, \
            patch.object(
                mock_gateway, "discover_scenes", new_callable=AsyncMock
        ) as mock_discover_scenes:

            # Set up mock return values
            mock_discover_devices.return_value = mock_gateway.devices
            mock_discover_groups.return_value = mock_gateway.groups
            mock_discover_scenes.return_value = mock_gateway.scenes

            result = await mixin_instance._discover_entities(mock_gateway) # pylint: disable=protected-access

            # Verify all discovery methods were called
            mock_discover_devices.assert_called_once()
            mock_discover_groups.assert_called_once()
            mock_discover_scenes.assert_called_once()

            # Verify results
            assert "devices" in result
            assert "groups" in result
            assert "scenes" in result
            assert result["devices"] == mock_gateway.devices
            assert result["groups"] == mock_gateway.groups
            assert result["scenes"] == mock_gateway.scenes

    @pytest.mark.asyncio
    async def test_discover_entities_devices_only(self, mixin_instance):
        """Test discovering only devices."""
        mock_gateway = MockDaliGateway()

        with patch.object(
            mock_gateway, "discover_devices", new_callable=AsyncMock
        ) as mock_discover_devices, \
            patch.object(
                mock_gateway, "discover_groups", new_callable=AsyncMock
        ) as mock_discover_groups, \
            patch.object(
                mock_gateway, "discover_scenes", new_callable=AsyncMock
        ) as mock_discover_scenes:

            mock_discover_devices.return_value = mock_gateway.devices

            result = await mixin_instance._discover_entities(  # pylint: disable=protected-access
                mock_gateway,
                discover_devices=True,
                discover_groups=False,
                discover_scenes=False
            )

            # Verify only devices were discovered
            mock_discover_devices.assert_called_once()
            mock_discover_groups.assert_not_called()
            mock_discover_scenes.assert_not_called()

            # Verify results
            assert "devices" in result
            assert "groups" not in result
            assert "scenes" not in result
            assert result["devices"] == mock_gateway.devices


class TestDaliCenterConfigFlow:
    """Test DaliCenterConfigFlow main functionality."""

    @pytest.fixture
    def hass(self):
        """Create mock HomeAssistant instance."""
        hass = Mock(spec=HomeAssistant)
        # Mock config_entries
        mock_config_entries = Mock()
        mock_config_entries.async_entries.return_value = []
        hass.config_entries = mock_config_entries
        return hass

    def test_config_flow_initialization(self):
        """Test ConfigFlow initialization."""
        flow = DaliCenterConfigFlow()
        assert flow.VERSION == 1
        assert flow.MINOR_VERSION == 1
        assert hasattr(flow, "async_step_user")
        assert hasattr(flow, "async_step_discovery")
        assert hasattr(flow, "async_step_configure_entities")

    def test_config_flow_domain(self):
        """Test ConfigFlow has correct domain."""
        # This tests the domain constant is properly used
        assert DOMAIN == "dali_center"

    @pytest.mark.asyncio
    async def test_async_step_user_initial_form(self, hass):
        """Test user step shows initial form."""
        flow = DaliCenterConfigFlow()
        flow.hass = hass

        # First call should show form with instructions
        result = await flow.async_step_user()

        # Should show form with instructions
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"
        assert "description_placeholders" in result
        assert "message" in result["description_placeholders"]

    @pytest.mark.asyncio
    async def test_async_step_user_proceed_to_discovery(self, hass):
        """Test user step proceeds to discovery when user submits."""
        flow = DaliCenterConfigFlow()
        flow.hass = hass

        # Mock discovery to return gateway list
        gateway_data = [{
            "sn": MOCK_GATEWAY_SN,
            "ip": MOCK_GATEWAY_IP,
            "name": "Test Gateway"
        }]

        with patch.object(
            MockDaliGatewayDiscovery,
            "discover",
            new_callable=AsyncMock
        ) as mock_discover:
            mock_discover.return_value = gateway_data

            # Submit form data to trigger discovery step
            result = await flow.async_step_user(user_input={})

            # Should proceed to discovery step
            assert result["type"] == FlowResultType.FORM
            assert result["step_id"] == "discovery"

    @pytest.mark.asyncio
    async def test_async_step_discovery_no_gateways_found(self, hass):
        """Test discovery step when no gateways are found."""
        flow = DaliCenterConfigFlow()
        flow.hass = hass

        discovery_instance = MockDaliGatewayDiscovery()
        with patch(
            "custom_components.dali_center.config_flow.DaliGatewayDiscovery",
            return_value=discovery_instance
        ), \
            patch.object(
                discovery_instance,
                "discover_gateways",
                new_callable=AsyncMock
            ) as mock_discover_gateways:

            mock_discover_gateways.return_value = []

            result = await flow.async_step_discovery()

            # Should show form indicating no gateways found
            assert result["type"] == FlowResultType.FORM
            assert result["step_id"] == "discovery"
            # When no gateways found, it should show error
            assert "errors" in result
            assert result["errors"]["base"] == "no_devices_found"
            assert "description_placeholders" in result
