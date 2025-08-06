"""Test config flow for Dali Center integration."""
# pylint: disable=protected-access

import pytest
from unittest.mock import AsyncMock, Mock, patch

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.entity_registry import RegistryEntry

from PySrDaliGateway.exceptions import DaliGatewayError

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

# Module path constants to avoid repetition
CFM = "custom_components.dali_center.config_flow"
ENTITY_HELPER_BASE = (
    "custom_components.dali_center.config_flow_helpers.entity_helpers"
)
UI_HELPER_BASE = (
    "custom_components.dali_center.config_flow_helpers.ui_helpers"
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

    @pytest.mark.asyncio
    async def test_async_step_discovery_failure(self, hass):
        """Test discovery step when discovery fails."""
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

            mock_discover_gateways.side_effect = DaliGatewayError(
                "Discovery failed")

            result = await flow.async_step_discovery()

            # Should show form indicating discovery failed
            assert result["type"] == FlowResultType.FORM
            assert result["step_id"] == "discovery"
            assert "errors" in result
            assert result["errors"]["base"] == "discovery_failed"
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

    @pytest.mark.asyncio
    async def test_async_step_discovery_gateway_connection_failure(
            self, config_flow):
        """Test discovery step with gateway connection failure."""
        mock_gateways = [{"gw_sn": MOCK_GATEWAY_SN,
                          "ip": MOCK_GATEWAY_IP, "name": "Test Gateway"}]
        config_flow._gateways = mock_gateways

        with patch(f"{CFM}.DaliGateway") as mock_gateway_class:
            mock_gateway = MockDaliGateway()
            mock_gateway.connect = AsyncMock(
                side_effect=DaliGatewayError("Connection failed")
            )
            mock_gateway_class.return_value = mock_gateway

            result = await config_flow.async_step_discovery({
                "selected_gateway": MOCK_GATEWAY_SN
            })

            assert result["type"] == FlowResultType.FORM
            assert result["step_id"] == "discovery"
            assert "errors" in result
            assert result["errors"]["base"] == "cannot_connect"

    @pytest.mark.asyncio
    async def test_async_step_discovery_invalid_gateway(
            self, config_flow):
        """Test discovery step with invalid gateway selection."""
        mock_gateways = [{"gw_sn": MOCK_GATEWAY_SN,
                          "ip": MOCK_GATEWAY_IP, "name": "Test Gateway"}]
        config_flow._gateways = mock_gateways

        result = await config_flow.async_step_discovery({
            "selected_gateway": "INVALID_SN"
        })

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "discovery"
        assert "errors" in result
        assert result["errors"]["base"] == "device_not_found"

    @pytest.mark.asyncio
    async def test_async_step_discovery_retry_request(
            self, config_flow):
        """Test discovery step with retry request (no selected_gateway)."""
        config_flow._gateways = ["some_existing_gateways"]

        # Mock config_entries to return empty list
        # (no existing configured gateways)
        config_flow.hass.config_entries.async_entries.return_value = []

        # Mock discovery for retry
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

            mock_discover_gateways.return_value = [{
                "gw_sn": "NEW_GATEWAY",
                "ip": "192.168.1.200",
                "name": "New Gateway"
            }]

            # Pass discovery_info without selected_gateway to trigger retry
            result = await config_flow.async_step_discovery({})

            # Should clear gateways and retry discovery
            assert config_flow._gateways == [{
                "gw_sn": "NEW_GATEWAY",
                "ip": "192.168.1.200",
                "name": "New Gateway"
            }]
            assert result["type"] == FlowResultType.FORM
            assert result["step_id"] == "discovery"

    @pytest.mark.asyncio
    async def test_async_step_configure_entities_no_selected_gateway(
            self, config_flow):
        """Test configure entities step without selected gateway."""
        config_flow._selected_gateway = None

        result = await config_flow.async_step_configure_entities()

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "no_gateway_selected"

    @pytest.mark.asyncio
    async def test_async_step_configure_entities_discovery_failure(
            self, config_flow):
        """Test configure entities step with entity discovery failure."""
        config_flow._selected_gateway = MockDaliGateway()
        config_flow._config_data = {"sn": MOCK_GATEWAY_SN}

        discover_entities_path = (
            f"{ENTITY_HELPER_BASE}.EntityDiscoveryHelper.discover_entities"
        )
        with patch(
            discover_entities_path, new_callable=AsyncMock
        ) as mock_discover:
            mock_discover.side_effect = Exception("Discovery failed")

            result = await config_flow.async_step_configure_entities()

            assert result["type"] == FlowResultType.FORM
            assert result["step_id"] == "configure_entities"
            assert "errors" in result
            assert result["errors"]["base"] == "cannot_connect"

    @pytest.mark.asyncio
    async def test_async_step_configure_entities_disconnect_failure(
            self, config_flow):
        """Test configure entities step with disconnect failure."""
        mock_gateway = MockDaliGateway()
        mock_gateway.disconnect = AsyncMock(
            side_effect=DaliGatewayError("Disconnect failed")
        )
        config_flow._selected_gateway = mock_gateway
        config_flow._config_data = {"sn": MOCK_GATEWAY_SN}

        discover_entities_path = (
            f"{ENTITY_HELPER_BASE}.EntityDiscoveryHelper.discover_entities"
        )
        with patch(
            discover_entities_path, new_callable=AsyncMock
        ) as mock_discover:
            mock_discover.return_value = {
                "devices": [], "groups": [], "scenes": []}

            result = await config_flow.async_step_configure_entities()

            assert result["type"] == FlowResultType.FORM
            assert result["step_id"] == "configure_entities"
            assert "errors" in result
            assert result["errors"]["base"] == "cannot_disconnect"

    @pytest.mark.asyncio
    async def test_async_step_configure_entities_general_disconnect_failure(
            self, config_flow):
        """Test configure entities step with general disconnect exception."""
        mock_gateway = MockDaliGateway()
        mock_gateway.disconnect = AsyncMock(
            side_effect=Exception("General disconnect error")
        )
        config_flow._selected_gateway = mock_gateway
        config_flow._config_data = {"sn": MOCK_GATEWAY_SN}

        discover_entities_path = (
            f"{ENTITY_HELPER_BASE}.EntityDiscoveryHelper.discover_entities"
        )
        with patch(
            discover_entities_path, new_callable=AsyncMock
        ) as mock_discover:
            mock_discover.return_value = {
                "devices": [], "groups": [], "scenes": []}

            result = await config_flow.async_step_configure_entities()

            assert result["type"] == FlowResultType.FORM
            assert result["step_id"] == "configure_entities"
            assert "errors" in result
            assert result["errors"]["base"] == "cannot_disconnect"

    @pytest.mark.asyncio
    async def test_async_step_configure_entities_no_entities_found(
            self, config_flow):
        """Test configure entities step when no entities are found."""
        config_flow._selected_gateway = MockDaliGateway()
        config_flow._config_data = {"sn": MOCK_GATEWAY_SN}
        config_flow._discovered_entities = {
            "devices": [], "groups": [], "scenes": []}

        discover_entities_path = (
            f"{ENTITY_HELPER_BASE}.EntityDiscoveryHelper.discover_entities"
        )
        prepare_schema_path = (
            f"{ENTITY_HELPER_BASE}.EntityDiscoveryHelper."
            "prepare_entity_selection_schema"
        )
        with patch(
            discover_entities_path, new_callable=AsyncMock
        ) as mock_discover, \
            patch(prepare_schema_path) as mock_schema:

            mock_discover.return_value = {
                "devices": [], "groups": [], "scenes": []}
            mock_schema_obj = Mock()
            mock_schema_obj.schema = {}
            mock_schema.return_value = mock_schema_obj

            result = await config_flow.async_step_configure_entities()

            assert result["type"] == FlowResultType.ABORT
            assert result["reason"] == "no_entities_found"

    @pytest.mark.asyncio
    async def test_async_step_configure_entities_success_with_user_input(
            self, config_flow):
        """Test configure entities step with successful user input."""
        config_flow._selected_gateway = MockDaliGateway()
        config_flow._config_data = {"sn": MOCK_GATEWAY_SN, "gateway": {}}
        config_flow._discovered_entities = {
            "devices": [{"sn": "dev1", "name": "Device 1"}],
            "groups": [],
            "scenes": []
        }

        user_input = {"device_dev1": True}

        filter_entities_path = (
            f"{ENTITY_HELPER_BASE}.EntityDiscoveryHelper."
            "filter_selected_entities"
        )
        with patch(filter_entities_path) as mock_filter:
            mock_filter.return_value = {"devices": [
                {"sn": "dev1", "name": "Device 1"}]}

            result = await config_flow.async_step_configure_entities(
                user_input
            )

            assert result["type"] == FlowResultType.CREATE_ENTRY
            assert "devices" in config_flow._config_data


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


class TestOptionsFlowHandlerComprehensive:
    """Comprehensive tests for OptionsFlowHandler to improve coverage."""

    @pytest.fixture
    def mock_config_entry_with_runtime(self):
        """Create mock config entry with runtime_data."""
        config_entry = ConfigEntry(
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
        # Mock runtime_data
        config_entry.runtime_data = Mock()
        config_entry.runtime_data.gateway = MockDaliGateway()
        return config_entry

    @pytest.fixture
    def options_flow_with_runtime(self, mock_config_entry_with_runtime):
        """Create OptionsFlowHandler instance with runtime data."""
        flow = OptionsFlowHandler(mock_config_entry_with_runtime)
        mock_hass = Mock(spec=HomeAssistant)

        # Mock config_entries and device/entity registries
        mock_config_entries = Mock()
        mock_config_entries.async_unload = AsyncMock(return_value=True)
        mock_config_entries.async_setup = AsyncMock(return_value=True)
        mock_config_entries.async_update_entry = Mock()
        mock_hass.config_entries = mock_config_entries

        flow.hass = mock_hass
        return flow

    @pytest.mark.asyncio
    async def test_async_step_init_show_form(self, options_flow_with_runtime):
        """Test async_step_init shows form when no user_input."""
        result = await options_flow_with_runtime.async_step_init()

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "init"
        assert "data_schema" in result

    @pytest.mark.asyncio
    async def test_async_step_init_with_gateway_ip_refresh(
            self, options_flow_with_runtime
    ):
        """Test async_step_init with gateway IP refresh enabled."""
        user_input = {
            "refresh_devices": False,
            "refresh_groups": False,
            "refresh_scenes": False,
            "refresh_gateway_ip": True
        }

        with patch.object(
            options_flow_with_runtime, "async_step_refresh_gateway_ip"
        ) as mock_refresh_ip:
            mock_refresh_ip.return_value = {"type": FlowResultType.FORM}

            await options_flow_with_runtime.async_step_init(user_input)

            mock_refresh_ip.assert_called_once()
            assert options_flow_with_runtime._refresh_gateway_ip is True

    @pytest.mark.asyncio
    async def test_async_step_init_without_gateway_ip_refresh(
            self, options_flow_with_runtime
    ):
        """Test async_step_init without gateway IP refresh."""
        user_input = {
            "refresh_devices": True,
            "refresh_groups": True,
            "refresh_scenes": True,
            "refresh_gateway_ip": False
        }

        with patch.object(
            options_flow_with_runtime, "async_step_refresh"
        ) as mock_refresh:
            mock_refresh.return_value = {"type": FlowResultType.FORM}

            await options_flow_with_runtime.async_step_init(user_input)

            mock_refresh.assert_called_once()
            assert options_flow_with_runtime._refresh_devices is True
            assert options_flow_with_runtime._refresh_groups is True
            assert options_flow_with_runtime._refresh_scenes is True

    @pytest.mark.asyncio
    async def test_async_step_refresh_no_runtime_data(self):
        """Test async_step_refresh when no runtime_data available."""
        # Create config entry without runtime_data
        config_entry = ConfigEntry(
            version=1,
            minor_version=1,
            domain=DOMAIN,
            title="Test Gateway",
            data={"sn": MOCK_GATEWAY_SN},
            source="user",
            entry_id="test_entry_id",
            unique_id=MOCK_GATEWAY_SN,
            options={},
            discovery_keys={},
            subentries_data=None,
        )
        # Set runtime_data to None to simulate no runtime data
        config_entry.runtime_data = None

        flow = OptionsFlowHandler(config_entry)
        flow.hass = Mock(spec=HomeAssistant)

        result = await flow.async_step_refresh()

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "gateway_not_found"

    @pytest.mark.asyncio
    async def test_async_step_refresh_discovery_error(
            self, options_flow_with_runtime
    ):
        """Test async_step_refresh when entity discovery fails."""
        discover_entities_path = (
            f"{ENTITY_HELPER_BASE}.EntityDiscoveryHelper.discover_entities"
        )
        with patch(
            discover_entities_path, new_callable=AsyncMock
        ) as mock_discover:
            mock_discover.side_effect = Exception("Discovery failed")

            result = await options_flow_with_runtime.async_step_refresh()

            assert result["type"] == FlowResultType.FORM
            assert result["step_id"] == "refresh"
            assert "errors" in result
            assert result["errors"]["base"] == "cannot_connect"

    @pytest.mark.asyncio
    async def test_async_step_select_entities_success(
            self, options_flow_with_runtime
    ):
        """Test async_step_select_entities with successful entity selection."""
        options_flow_with_runtime._discovered_entities = {
            "devices": [{"sn": "new_dev", "name": "New Device"}],
            "groups": [],
            "scenes": []
        }

        user_input = {"device_new_dev": True}

        # Setup patch paths
        filter_entities_path = (
            f"{ENTITY_HELPER_BASE}.EntityDiscoveryHelper."
            "filter_selected_entities"
        )
        calc_diff_path = (
            f"{UI_HELPER_BASE}.UIFormattingHelper."
            "calculate_entity_differences"
        )
        device_reg_path = "homeassistant.helpers.device_registry.async_get"
        entity_reg_path = "homeassistant.helpers.entity_registry.async_get"
        with patch(filter_entities_path) as mock_filter, \
            patch(calc_diff_path) as mock_diff, \
            patch(device_reg_path) as mock_device_reg, \
            patch(entity_reg_path) as mock_entity_reg, \
            patch.object(
                options_flow_with_runtime, "_reload_with_delay"
            ) as mock_reload, \
            patch.object(
                options_flow_with_runtime, "async_step_refresh_result"
            ) as mock_refresh_result:

            # Setup mocks
            mock_filter.return_value = {"devices": [
                {"sn": "new_dev", "name": "New Device"}]}
            mock_diff.return_value = {
                "devices_added": [{"name": "New Device"}]}

            # Mock device and entity registries
            mock_device_registry = Mock()
            mock_entity_registry = Mock()
            mock_device_reg.return_value = mock_device_registry
            mock_entity_reg.return_value = mock_entity_registry

            mock_device_registry.async_remove_device = Mock()
            mock_entity_registry.async_remove = Mock()

            # Mock entries for removal
            device_entry = Mock(spec=DeviceEntry)
            device_entry.id = "device_id"
            device_entry.name = "Test Device"

            entity_entry = Mock(spec=RegistryEntry)
            entity_entry.entity_id = "light.test_light"

            device_entries_path = (
                "homeassistant.helpers.device_registry."
                "async_entries_for_config_entry"
            )
            entity_entries_path = (
                "homeassistant.helpers.entity_registry."
                "async_entries_for_config_entry"
            )
            with patch(device_entries_path, return_value=[device_entry]), \
                patch(entity_entries_path, return_value=[entity_entry]):

                mock_reload.return_value = True
                mock_refresh_result.return_value = {
                    "type": FlowResultType.CREATE_ENTRY}

                await options_flow_with_runtime.async_step_select_entities(
                    user_input
                )

                # Verify device and entity removal was called
                mock_device_registry.async_remove_device.assert_called_with(
                    "device_id"
                )
                mock_entity_registry.async_remove.assert_called_with(
                    "light.test_light"
                )
                mock_reload.assert_called_once()
                mock_refresh_result.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_step_select_entities_show_form(
            self, options_flow_with_runtime
    ):
        """Test async_step_select_entities shows form when no user_input."""
        options_flow_with_runtime._discovered_entities = {
            "devices": [{"sn": "dev1", "name": "Device 1"}],
            "groups": [{"sn": "group1", "name": "Group 1"}],
            "scenes": [{"sn": "scene1", "name": "Scene 1"}]
        }

        prepare_schema_path = (
            f"{ENTITY_HELPER_BASE}.EntityDiscoveryHelper."
            "prepare_entity_selection_schema"
        )
        format_summary_path = (
            f"{UI_HELPER_BASE}.UIFormattingHelper."
            "format_discovery_summary"
        )
        with patch(prepare_schema_path) as mock_schema, \
            patch(format_summary_path) as mock_summary:

            mock_schema_obj = Mock()
            mock_schema.return_value = mock_schema_obj
            mock_summary.return_value = "Discovery summary"

            result = await (
                options_flow_with_runtime.async_step_select_entities()
            )

            assert result["type"] == FlowResultType.FORM
            assert result["step_id"] == "select_entities"
            assert "data_schema" in result
            assert "description_placeholders" in result
            assert "diff_summary" in result["description_placeholders"]

    @pytest.mark.asyncio
    async def test_async_step_refresh_result_show_form(
            self, options_flow_with_runtime
    ):
        """Test async_step_refresh_result shows form when no user_input."""
        options_flow_with_runtime._refresh_results = {
            "devices_added": [{"name": "New Device"}]
        }

        format_results_path = (
            f"{UI_HELPER_BASE}.UIFormattingHelper."
            "format_refresh_results"
        )
        with patch(format_results_path) as mock_format:
            mock_format.return_value = "Refresh results message"

            result = await options_flow_with_runtime.async_step_refresh_result()

            assert result["type"] == FlowResultType.FORM
            assert result["step_id"] == "refresh_result"
            assert "description_placeholders" in result
            assert "result_message" in result["description_placeholders"]

    @pytest.mark.asyncio
    async def test_async_step_refresh_gateway_ip_no_gateways_found(
            self, options_flow_with_runtime
    ):
        """Test async_step_refresh_gateway_ip when no gateways found."""
        with patch(
            f"{CFM}.DaliGatewayDiscovery"
        ) as mock_discovery_class:
            mock_discovery = MockDaliGatewayDiscovery()
            mock_discovery.discover_gateways = AsyncMock(return_value=[])
            mock_discovery_class.return_value = mock_discovery

            result = await (
                options_flow_with_runtime.async_step_refresh_gateway_ip()
            )

            assert result["type"] == FlowResultType.FORM
            assert result["step_id"] == "refresh_gateway_ip"
            assert "errors" in result
            assert result["errors"]["base"] == "gateway_not_found"

    @pytest.mark.asyncio
    async def test_async_step_refresh_gateway_ip_reload_failure(
            self, options_flow_with_runtime
    ):
        """Test async_step_refresh_gateway_ip when reload fails."""
        with patch(
            f"{CFM}.DaliGatewayDiscovery"
        ) as mock_discovery_class, \
            patch.object(
                options_flow_with_runtime, "_reload_with_delay"
        ) as mock_reload:

            mock_discovery = MockDaliGatewayDiscovery()
            mock_gateway_data = [{
                "gw_sn": MOCK_GATEWAY_SN, "gw_ip": "192.168.1.200"
            }]
            mock_discovery.discover_gateways = AsyncMock(
                return_value=mock_gateway_data
            )
            mock_discovery_class.return_value = mock_discovery
            mock_reload.return_value = False

            result = await (
                options_flow_with_runtime.async_step_refresh_gateway_ip()
            )

            assert result["type"] == FlowResultType.FORM
            assert result["step_id"] == "refresh_gateway_ip"
            assert "errors" in result
            assert result["errors"]["base"] == "cannot_connect"

    @pytest.mark.asyncio
    async def test_async_step_refresh_gateway_ip_success_with_entity_refresh(
            self, options_flow_with_runtime
    ):
        """Test async_step_refresh_gateway_ip success with entity refresh."""
        options_flow_with_runtime._refresh_devices = True
        options_flow_with_runtime._refresh_groups = True

        with patch(
            f"{CFM}.DaliGatewayDiscovery"
        ) as mock_discovery_class, \
            patch.object(
                options_flow_with_runtime, "_reload_with_delay"
        ) as mock_reload, \
            patch.object(
                options_flow_with_runtime, "async_step_refresh"
        ) as mock_refresh:

            mock_discovery = MockDaliGatewayDiscovery()
            mock_gateway_data = [{
                "gw_sn": MOCK_GATEWAY_SN, "gw_ip": "192.168.1.200"
            }]
            mock_discovery.discover_gateways = AsyncMock(
                return_value=mock_gateway_data
            )
            mock_discovery_class.return_value = mock_discovery
            mock_reload.return_value = True
            mock_refresh.return_value = {"type": FlowResultType.FORM}

            await (
                options_flow_with_runtime.async_step_refresh_gateway_ip()
            )

            mock_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_step_refresh_gateway_ip_success_without_entity_refresh(
            self, options_flow_with_runtime
    ):
        """Test async_step_refresh_gateway_ip success without entity refresh."""
        options_flow_with_runtime._refresh_devices = False
        options_flow_with_runtime._refresh_groups = False
        options_flow_with_runtime._refresh_scenes = False

        with patch(
            f"{CFM}.DaliGatewayDiscovery"
        ) as mock_discovery_class, \
            patch.object(
                options_flow_with_runtime, "_reload_with_delay"
        ) as mock_reload:

            mock_discovery = MockDaliGatewayDiscovery()
            mock_gateway_data = [{
                "gw_sn": MOCK_GATEWAY_SN, "gw_ip": "192.168.1.200"
            }]
            mock_discovery.discover_gateways = AsyncMock(
                return_value=mock_gateway_data
            )
            mock_discovery_class.return_value = mock_discovery
            mock_reload.return_value = True

            result = await (
                options_flow_with_runtime.async_step_refresh_gateway_ip()
            )

            assert result["type"] == FlowResultType.FORM
            assert result["step_id"] == "refresh_gateway_ip_result"
            assert "description_placeholders" in result
            assert "gateway_sn" in result["description_placeholders"]
            assert "new_ip" in result["description_placeholders"]

    @pytest.mark.asyncio
    async def test_async_step_refresh_gateway_ip_exception(
            self, options_flow_with_runtime
    ):
        """Test async_step_refresh_gateway_ip when exception occurs."""
        with patch(
            f"{CFM}.DaliGatewayDiscovery"
        ) as mock_discovery_class:
            mock_discovery_class.side_effect = Exception("Network error")

            result = await (
                options_flow_with_runtime.async_step_refresh_gateway_ip()
            )

            assert result["type"] == FlowResultType.FORM
            assert result["step_id"] == "refresh_gateway_ip"
            assert "errors" in result
            assert result["errors"]["base"] == "cannot_connect"

    @pytest.mark.asyncio
    async def test_async_step_refresh_gateway_ip_result_show_form(
            self, options_flow_with_runtime
    ):
        """Test async_step_refresh_gateway_ip_result shows form."""
        result = await (
            options_flow_with_runtime.async_step_refresh_gateway_ip_result()
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "refresh_gateway_ip_result"
        assert "data_schema" in result

    @pytest.mark.asyncio
    async def test_async_step_refresh_gateway_ip_result_create_entry(
            self, options_flow_with_runtime
    ):
        """Test async_step_refresh_gateway_ip_result creates entry."""
        result = await (
            options_flow_with_runtime.async_step_refresh_gateway_ip_result({})
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY

    @pytest.mark.asyncio
    async def test_reload_with_delay_success(self, options_flow_with_runtime):
        """Test _reload_with_delay method success."""
        result = await options_flow_with_runtime._reload_with_delay()

        assert result is True
        (
            options_flow_with_runtime.hass.config_entries.async_unload
            .assert_called_once()
        )
        (
            options_flow_with_runtime.hass.config_entries.async_setup
            .assert_called_once()
        )

    @pytest.mark.asyncio
    async def test_reload_with_delay_unload_failure(
            self, options_flow_with_runtime
    ):
        """Test _reload_with_delay method when unload fails."""
        options_flow_with_runtime.hass.config_entries.async_unload = AsyncMock(
            side_effect=Exception("Unload failed")
        )

        result = await options_flow_with_runtime._reload_with_delay()

        assert result is False

    @pytest.mark.asyncio
    async def test_reload_with_delay_setup_failure(
            self, options_flow_with_runtime
    ):
        """Test _reload_with_delay method when setup fails."""
        options_flow_with_runtime.hass.config_entries.async_setup = AsyncMock(
            return_value=False)

        result = await options_flow_with_runtime._reload_with_delay()

        assert result is False

    def test_options_schema_with_gateway_ip_refresh(self):
        """Test OPTIONS_SCHEMA with gateway IP refresh option."""
        data = {
            "refresh_devices": True,
            "refresh_groups": False,
            "refresh_scenes": True,
            "refresh_gateway_ip": True
        }
        result = OPTIONS_SCHEMA(data)
        assert result["refresh_gateway_ip"] is True

    def test_async_get_options_flow_static_method(self):
        """Test async_get_options_flow static method."""
        config_entry = ConfigEntry(
            version=1,
            minor_version=1,
            domain=DOMAIN,
            title="Test Gateway",
            data={"sn": MOCK_GATEWAY_SN},
            source="user",
            entry_id="test_entry_id",
            unique_id=MOCK_GATEWAY_SN,
            options={},
            discovery_keys={},
            subentries_data=None,
        )

        options_flow = DaliCenterConfigFlow.async_get_options_flow(
            config_entry)

        assert isinstance(options_flow, OptionsFlowHandler)
        assert options_flow._config_entry == config_entry
