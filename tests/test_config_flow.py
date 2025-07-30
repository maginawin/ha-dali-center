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
    EntityDiscoveryMixin,
    OPTIONS_SCHEMA
)
from custom_components.dali_center.const import DOMAIN
from custom_components.dali_center.config_flow import dr, er
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

            result = await mixin_instance._discover_entities(mock_gateway)  # pylint: disable=protected-access

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

    @pytest.mark.asyncio
    async def test_async_step_configure_entities_with_user_input(
            self, config_flow):
        """Test configure entities with user selection."""
        mock_gateway = MockDaliGateway()
        config_flow._selected_gateway = mock_gateway
        config_flow._discovered_entities = {
            "devices": [{"sn": "dev1", "name": "Device 1"}],
            "groups": [],
            "scenes": []
        }

        user_input = {"devices": ["dev1"]}

        with patch.object(
            config_flow, "_filter_selected_entities"
        ) as mock_filter:
            mock_filter.return_value = {"devices": [
                {"sn": "dev1", "name": "Device 1"}]}

            with patch.object(config_flow, "async_create_entry") as mock_create:
                mock_create.return_value = {
                    "type": FlowResultType.CREATE_ENTRY}

                await config_flow.async_step_configure_entities(user_input)

                mock_create.assert_called_once()

    def test_prepare_entity_selection_schema_with_devices(self, config_flow):
        """Test preparing entity selection schema with devices."""
        devices = [
            {"sn": "dev1", "name": "Device 1",
                "dev_type": "light", "unique_id": "gw123_dev1"},
            {"sn": "dev2", "name": "Device 2",
                "dev_type": "sensor", "unique_id": "gw123_dev2"}
        ]
        groups = []
        scenes = []

        schema = config_flow._prepare_entity_selection_schema(
            devices, groups, scenes)

        assert schema is not None

    def test_prepare_entity_selection_schema_with_groups(self, config_flow):
        """Test preparing entity selection schema with groups."""
        devices = []
        groups = [
            {"sn": "grp1", "name": "Group 1",
                "unique_id": "gw123_grp1", "channel": 1, "id": 1},
            {"sn": "grp2", "name": "Group 2",
                "unique_id": "gw123_grp2", "channel": 1, "id": 2}
        ]
        scenes = []

        schema = config_flow._prepare_entity_selection_schema(
            devices, groups, scenes)

        assert schema is not None

    def test_prepare_entity_selection_schema_with_scenes(self, config_flow):
        """Test preparing entity selection schema with scenes."""
        devices = []
        groups = []
        scenes = [
            {"sn": "scn1", "name": "Scene 1",
                "unique_id": "gw123_scn1", "channel": 1, "id": 1},
            {"sn": "scn2", "name": "Scene 2",
                "unique_id": "gw123_scn2", "channel": 1, "id": 2}
        ]

        schema = config_flow._prepare_entity_selection_schema(
            devices, groups, scenes)

        assert schema is not None

    def test_filter_selected_entities_all_types(self, config_flow):
        """Test filtering selected entities for all types."""
        user_input = {
            "devices": ["gw123_dev1"],
            "groups": ["gw123_grp1"],
            "scenes": ["gw123_scn1"]
        }
        discovered_entities = {
            "devices": [
                {"sn": "dev1", "name": "Device 1", "unique_id": "gw123_dev1"}
            ],
            "groups": [
                {"sn": "grp1", "name": "Group 1", "unique_id": "gw123_grp1"}
            ],
            "scenes": [
                {"sn": "scn1", "name": "Scene 1", "unique_id": "gw123_scn1"}
            ]
        }

        result = config_flow._filter_selected_entities(
            user_input, discovered_entities)

        assert len(result["devices"]) == 1
        assert len(result["groups"]) == 1
        assert len(result["scenes"]) == 1


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
    async def test_async_step_refresh_with_entity_discovery(self, options_flow):
        """Test refresh step with entity discovery."""
        options_flow._refresh_devices = True

        # Mock runtime_data to avoid gateway_not_found abort
        mock_runtime_data = Mock()
        mock_gateway = MockDaliGateway()
        mock_runtime_data.gateway = mock_gateway
        options_flow._config_entry.runtime_data = mock_runtime_data

        with patch.object(options_flow, "_discover_entities") as mock_discover:
            mock_discover.return_value = {
                "devices": [{"sn": "dev2", "name": "Device 2"}],
                "groups": [],
                "scenes": []
            }

            with patch.object(
                options_flow, "async_step_select_entities"
            ) as mock_select:
                mock_select.return_value = {"type": FlowResultType.FORM}

                await options_flow.async_step_refresh()

                mock_select.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_step_select_entities_with_user_input(
            self, options_flow):
        """Test select entities step with user selection."""
        options_flow._discovered_entities = {
            "devices": [
                {"sn": "dev1", "name": "Device 1", "unique_id": "gw123_dev1"}
            ],
            "groups": [],
            "scenes": []
        }

        user_input = {"devices": ["gw123_dev1"]}

        with patch.object(
            options_flow, "_filter_selected_entities"
        ) as mock_filter:
            mock_filter.return_value = {"devices": [
                {"sn": "dev1", "name": "Device 1", "unique_id": "gw123_dev1"}]}

            with patch.object(
                options_flow, "async_step_refresh_result"
            ) as mock_result:
                mock_result.return_value = {
                    "type": FlowResultType.CREATE_ENTRY}

                # Mock the necessary registry operations
                with patch(f"{CFM}.dr.async_get") as mock_dr, \
                        patch(f"{CFM}.er.async_get") as mock_er:
                    mock_device_reg = Mock()
                    mock_entity_reg = Mock()
                    mock_dr.return_value = mock_device_reg
                    mock_er.return_value = mock_entity_reg
                    mock_device_reg.async_remove_device = Mock()
                    mock_entity_reg.async_remove = Mock()

                    # Mock registry entries
                    with patch.object(
                        dr, "async_entries_for_config_entry", return_value=[]
                    ), patch.object(
                        er, "async_entries_for_config_entry", return_value=[]
                    ):

                        # Mock hass.config_entries.async_update_entry to avoid
                        # the data modification error
                        options_flow.hass.config_entries.async_update_entry = (
                            Mock()
                        )

                        # Mock hass.async_create_task for the reload task
                        options_flow.hass.async_create_task = Mock()

                        await options_flow.async_step_select_entities(
                            user_input
                        )

                        mock_result.assert_called_once()

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

    def test_calculate_entity_differences_added_devices(self, options_flow):
        """Test calculating entity differences with added devices."""
        # Set refresh flag to enable devices processing
        options_flow._refresh_devices = True

        selected = {
            "devices": [
                {"sn": "dev1", "name": "Device 1", "unique_id": "gw123_dev1"},
                {"sn": "dev2", "name": "Device 2", "unique_id": "gw123_dev2"}
            ],
            "groups": [],
            "scenes": []
        }
        current_data = {
            "devices": [
                {"sn": "dev1", "name": "Device 1", "unique_id": "gw123_dev1"}
            ],
            "groups": [],
            "scenes": []
        }

        options_flow._calculate_entity_differences(selected, current_data)

        assert len(options_flow._refresh_results["devices_added"]) == 1
        assert options_flow._refresh_results["devices_added"][0]["sn"] == "dev2"

    def test_calculate_entity_differences_removed_devices(self, options_flow):
        """Test calculating entity differences with removed devices."""
        # Set refresh flag to enable devices processing
        options_flow._refresh_devices = True

        selected = {
            "devices": [],
            "groups": [],
            "scenes": []
        }
        current_data = {
            "devices": [
                {"sn": "dev1", "name": "Device 1", "unique_id": "gw123_dev1"}
            ],
            "groups": [],
            "scenes": []
        }

        options_flow._calculate_entity_differences(selected, current_data)

        assert len(options_flow._refresh_results["devices_removed"]) == 1
        assert (
            options_flow._refresh_results["devices_removed"][0]["sn"] == "dev1"
        )
