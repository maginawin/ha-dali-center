"""Test config flow for Dali Center integration."""
# pylint: disable=protected-access

import pytest
from unittest.mock import AsyncMock, Mock, patch
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from custom_components.dali_center.config_flow import (
    OptionsFlowHandler,
    DaliCenterConfigFlow,
    OPTIONS_SCHEMA
)
from custom_components.dali_center.const import DOMAIN
from tests.conftest import (
    MockDaliGateway,
    MockDaliGatewayDiscovery,
    MOCK_GATEWAY_SN,
    MOCK_GATEWAY_IP
)

# Module path constant to avoid repetition
CFM = "custom_components.dali_center.config_flow"


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
            f"{CFM}.DaliGatewayDiscovery",
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


class TestDaliCenterConfigFlowComplete:
    """Test additional DaliCenterConfigFlow functionality."""

    @pytest.fixture
    def mock_hass(self):
        """Create mock HomeAssistant instance."""
        return Mock(spec=HomeAssistant)

    @pytest.fixture
    def config_flow(self, mock_hass):
        """Create DaliCenterConfigFlow instance."""
        flow = DaliCenterConfigFlow()
        flow.hass = mock_hass
        return flow

    @pytest.mark.asyncio
    async def test_async_step_discovery_with_selected_gateway_success(
            self, config_flow):
        """Test discovery step with successful gateway selection."""
        mock_gateways = [{"gw_sn": MOCK_GATEWAY_SN,
                          "ip": MOCK_GATEWAY_IP, "name": "Test Gateway"}]
        config_flow._gateways = mock_gateways

        with patch(f"{CFM}.DaliGateway") as mock_gateway_class:
            mock_gateway = MockDaliGateway()
            mock_gateway.connect = AsyncMock()
            mock_gateway_class.return_value = mock_gateway

            with patch.object(
                config_flow, "async_step_configure_entities"
            ) as mock_configure:
                mock_configure.return_value = {
                    "type": FlowResultType.CREATE_ENTRY}

                await config_flow.async_step_discovery({
                    "selected_gateway": MOCK_GATEWAY_SN
                })

                mock_configure.assert_called_once()
                assert config_flow._selected_gateway is not None


class TestOptionsFlowHandlerComplete:
    """Test additional OptionsFlowHandler functionality."""

    @pytest.fixture
    def mock_config_entry(self):
        """Create mock config entry."""
        return ConfigEntry(
            version=1,
            minor_version=1,
            domain=DOMAIN,
            title="Test Gateway",
            data={
                "sn": MOCK_GATEWAY_SN,
                "gateway": {"gw_sn": MOCK_GATEWAY_SN, "ip": MOCK_GATEWAY_IP},
                "devices": [{"sn": "dev1", "name": "Device 1"}],
                "groups": [],
                "scenes": []
            },
            source="user",
            entry_id="test_entry_id",
            unique_id=MOCK_GATEWAY_SN,
            options={},
            discovery_keys={},
            subentries_data=None,
        )

    @pytest.fixture
    def options_flow(self, mock_config_entry):
        """Create OptionsFlowHandler instance."""
        flow = OptionsFlowHandler(mock_config_entry)
        flow.hass = Mock(spec=HomeAssistant)
        return flow

    @pytest.mark.asyncio
    async def test_async_step_refresh_result_with_changes(self, options_flow):
        """Test refresh result step with entity changes."""
        options_flow._refresh_results = {
            "devices_added": [{"name": "New Device"}],
            "devices_removed": [],
            "groups_added": [],
            "groups_removed": [],
            "scenes_added": [],
            "scenes_removed": []
        }

        with patch.object(options_flow, "async_create_entry") as mock_create:
            mock_create.return_value = {"type": FlowResultType.CREATE_ENTRY}

            # Pass user_input to trigger the create_entry call
            await options_flow.async_step_refresh_result(user_input={})

            mock_create.assert_called_once()
