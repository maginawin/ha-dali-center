"""Test entity discovery and selection helpers for config flow."""

import pytest
from unittest.mock import AsyncMock
import voluptuous as vol

from custom_components.dali_center.config_flow_helpers.entity_helpers import (
    EntityDiscoveryHelper
)
from PySrDaliGateway.exceptions import DaliGatewayError
from tests.conftest import (
    MockDaliGateway,
    MOCK_GATEWAY_SN
)


class TestEntityDiscoveryHelper:
    """Test EntityDiscoveryHelper class."""

    @pytest.fixture
    def mock_gateway(self):
        """Create mock gateway for testing."""
        return MockDaliGateway()

    @pytest.fixture
    def mock_devices(self):
        """Create mock devices for testing."""
        return [
            {
                "sn": "dev1",
                "name": "Device 1",
                "unique_id": f"{MOCK_GATEWAY_SN}_dev1",
                "type": 1
            },
            {
                "sn": "dev2",
                "name": "Device 2",
                "unique_id": f"{MOCK_GATEWAY_SN}_dev2",
                "type": 1
            }
        ]

    @pytest.fixture
    def mock_groups(self):
        """Create mock groups for testing."""
        return [
            {
                "sn": "group1",
                "name": "Group 1",
                "unique_id": f"{MOCK_GATEWAY_SN}_group1",
                "channel": 1,
                "id": 1
            },
            {
                "sn": "group2",
                "name": "Group 2",
                "unique_id": f"{MOCK_GATEWAY_SN}_group2",
                "channel": 2,
                "id": 2
            }
        ]

    @pytest.fixture
    def mock_scenes(self):
        """Create mock scenes for testing."""
        return [
            {
                "sn": "scene1",
                "name": "Scene 1",
                "unique_id": f"{MOCK_GATEWAY_SN}_scene1",
                "channel": 1,
                "id": 1
            },
            {
                "sn": "scene2",
                "name": "Scene 2",
                "unique_id": f"{MOCK_GATEWAY_SN}_scene2",
                "channel": 2,
                "id": 2
            }
        ]

    @pytest.mark.asyncio
    async def test_discover_entities_success_all_types(
            self, mock_gateway, mock_devices, mock_groups, mock_scenes):
        """Test successful discovery of all entity types."""
        mock_gateway.discover_devices = AsyncMock(return_value=mock_devices)
        mock_gateway.discover_groups = AsyncMock(return_value=mock_groups)
        mock_gateway.discover_scenes = AsyncMock(return_value=mock_scenes)

        result = await EntityDiscoveryHelper.discover_entities(
            mock_gateway,
            discover_devices=True,
            discover_groups=True,
            discover_scenes=True
        )

        assert "devices" in result
        assert "groups" in result
        assert "scenes" in result
        assert len(result["devices"]) == 2
        assert len(result["groups"]) == 2
        assert len(result["scenes"]) == 2

        mock_gateway.discover_devices.assert_called_once()
        mock_gateway.discover_groups.assert_called_once()
        mock_gateway.discover_scenes.assert_called_once()

    @pytest.mark.asyncio
    async def test_discover_entities_selective_discovery(
            self, mock_gateway, mock_devices):
        """Test selective entity discovery (only devices)."""
        mock_gateway.discover_devices = AsyncMock(return_value=mock_devices)
        mock_gateway.discover_groups = AsyncMock()
        mock_gateway.discover_scenes = AsyncMock()

        result = await EntityDiscoveryHelper.discover_entities(
            mock_gateway,
            discover_devices=True,
            discover_groups=False,
            discover_scenes=False
        )

        assert "devices" in result
        assert "groups" not in result
        assert "scenes" not in result
        assert len(result["devices"]) == 2

        mock_gateway.discover_devices.assert_called_once()
        mock_gateway.discover_groups.assert_not_called()
        mock_gateway.discover_scenes.assert_not_called()

    @pytest.mark.asyncio
    async def test_discover_entities_device_dali_gateway_error(
            self, mock_gateway
    ):
        """Test device discovery with DaliGatewayError."""
        mock_gateway.discover_devices = AsyncMock(
            side_effect=DaliGatewayError("Connection failed")
        )
        mock_gateway.discover_groups = AsyncMock(return_value=[])
        mock_gateway.discover_scenes = AsyncMock(return_value=[])

        result = await EntityDiscoveryHelper.discover_entities(
            mock_gateway,
            discover_devices=True,
            discover_groups=True,
            discover_scenes=True
        )

        assert result["devices"] == []
        assert "groups" in result
        assert "scenes" in result

    @pytest.mark.asyncio
    async def test_discover_entities_device_general_exception(
            self, mock_gateway
    ):
        """Test device discovery with general exception."""
        mock_gateway.discover_devices = AsyncMock(
            side_effect=Exception("Unexpected error")
        )
        mock_gateway.discover_groups = AsyncMock(return_value=[])
        mock_gateway.discover_scenes = AsyncMock(return_value=[])

        result = await EntityDiscoveryHelper.discover_entities(
            mock_gateway,
            discover_devices=True,
            discover_groups=True,
            discover_scenes=True
        )

        assert result["devices"] == []
        assert "groups" in result
        assert "scenes" in result

    @pytest.mark.asyncio
    async def test_discover_entities_groups_exception(self, mock_gateway):
        """Test group discovery with exception."""
        mock_gateway.discover_devices = AsyncMock(return_value=[])
        mock_gateway.discover_groups = AsyncMock(
            side_effect=Exception("Group discovery failed")
        )
        mock_gateway.discover_scenes = AsyncMock(return_value=[])

        result = await EntityDiscoveryHelper.discover_entities(
            mock_gateway,
            discover_devices=True,
            discover_groups=True,
            discover_scenes=True
        )

        assert result["devices"] == []
        assert result["groups"] == []
        assert "scenes" in result

    @pytest.mark.asyncio
    async def test_discover_entities_scenes_exception(self, mock_gateway):
        """Test scene discovery with exception."""
        mock_gateway.discover_devices = AsyncMock(return_value=[])
        mock_gateway.discover_groups = AsyncMock(return_value=[])
        mock_gateway.discover_scenes = AsyncMock(
            side_effect=Exception("Scene discovery failed")
        )

        result = await EntityDiscoveryHelper.discover_entities(
            mock_gateway,
            discover_devices=True,
            discover_groups=True,
            discover_scenes=True
        )

        assert result["devices"] == []
        assert result["groups"] == []
        assert result["scenes"] == []

    def test_prepare_entity_selection_schema_initial_setup(
            self, mock_devices, mock_groups, mock_scenes
    ):
        """Test schema preparation for initial setup."""
        schema = EntityDiscoveryHelper.prepare_entity_selection_schema(
            devices=mock_devices,
            groups=mock_groups,
            scenes=mock_scenes,
            existing_selections=None,
            show_diff=False
        )

        assert isinstance(schema, vol.Schema)
        assert len(schema.schema) == 3  # devices, groups, scenes

    def test_prepare_entity_selection_schema_with_existing_selections(
            self, mock_devices, mock_groups, mock_scenes
    ):
        """Test schema preparation with existing selections."""
        existing_selections = {
            "devices": [mock_devices[0]],  # Only first device selected
            "groups": mock_groups,  # All groups selected
            "scenes": []  # No scenes selected
        }

        schema = EntityDiscoveryHelper.prepare_entity_selection_schema(
            devices=mock_devices,
            groups=mock_groups,
            scenes=mock_scenes,
            existing_selections=existing_selections,
            show_diff=True
        )

        assert isinstance(schema, vol.Schema)
        assert len(schema.schema) == 3

    def test_prepare_entity_selection_schema_show_diff_with_new_devices(
            self, mock_devices, mock_groups, mock_scenes
    ):
        """Test schema preparation showing diff with new devices."""
        existing_selections = {
            "devices": [mock_devices[0]],  # Only first device
            "groups": [],
            "scenes": []
        }

        schema = EntityDiscoveryHelper.prepare_entity_selection_schema(
            devices=mock_devices,  # Contains 2 devices
            groups=mock_groups,
            scenes=mock_scenes,
            existing_selections=existing_selections,
            show_diff=True
        )

        assert isinstance(schema, vol.Schema)

    def test_prepare_entity_selection_schema_show_diff_with_removed_devices(
            self, mock_devices, mock_groups, mock_scenes):
        """Test schema preparation showing diff with removed devices."""
        removed_device = {
            "sn": "removed_dev",
            "name": "Removed Device",
            "unique_id": f"{MOCK_GATEWAY_SN}_removed_dev",
            "type": 1
        }
        existing_selections = {
            # Includes removed device
            "devices": [mock_devices[0], removed_device],
            "groups": [],
            "scenes": []
        }

        schema = EntityDiscoveryHelper.prepare_entity_selection_schema(
            devices=[mock_devices[0]],  # Only first device exists now
            groups=mock_groups,
            scenes=mock_scenes,
            existing_selections=existing_selections,
            show_diff=True
        )

        assert isinstance(schema, vol.Schema)

    def test_prepare_entity_selection_schema_empty_entities(self):
        """Test schema preparation with empty entity lists."""
        schema = EntityDiscoveryHelper.prepare_entity_selection_schema(
            devices=[],
            groups=[],
            scenes=[],
            existing_selections=None,
            show_diff=False
        )

        assert isinstance(schema, vol.Schema)
        assert len(schema.schema) == 0  # No entities = no schema fields

    def test_prepare_entity_selection_schema_only_devices(self, mock_devices):
        """Test schema preparation with only devices."""
        schema = EntityDiscoveryHelper.prepare_entity_selection_schema(
            devices=mock_devices,
            groups=[],
            scenes=[],
            existing_selections=None,
            show_diff=False
        )

        assert isinstance(schema, vol.Schema)
        assert len(schema.schema) == 1  # Only devices field

    def test_prepare_entity_selection_schema_group_formatting(
            self, mock_groups
    ):
        """Test schema preparation with group formatting."""
        schema = EntityDiscoveryHelper.prepare_entity_selection_schema(
            devices=[],
            groups=mock_groups,
            scenes=[],
            existing_selections=None,
            show_diff=False
        )

        assert isinstance(schema, vol.Schema)
        assert len(schema.schema) == 1  # Only groups field

    def test_prepare_entity_selection_schema_scene_formatting(
            self, mock_scenes
    ):
        """Test schema preparation with scene formatting."""
        schema = EntityDiscoveryHelper.prepare_entity_selection_schema(
            devices=[],
            groups=[],
            scenes=mock_scenes,
            existing_selections=None,
            show_diff=False
        )

        assert isinstance(schema, vol.Schema)
        assert len(schema.schema) == 1  # Only scenes field

    def test_prepare_entity_selection_schema_removed_groups(
            self, mock_groups):
        """Test schema preparation with removed groups."""
        removed_group = {
            "sn": "removed_group",
            "name": "Removed Group",
            "unique_id": f"{MOCK_GATEWAY_SN}_removed_group",
            "channel": 3,
            "id": 3
        }
        existing_selections = {
            "devices": [],
            "groups": [mock_groups[0], removed_group],
            "scenes": []
        }

        schema = EntityDiscoveryHelper.prepare_entity_selection_schema(
            devices=[],
            groups=[mock_groups[0]],  # Only first group exists now
            scenes=[],
            existing_selections=existing_selections,
            show_diff=True
        )

        assert isinstance(schema, vol.Schema)

    def test_prepare_entity_selection_schema_removed_scenes(
            self, mock_scenes):
        """Test schema preparation with removed scenes."""
        removed_scene = {
            "sn": "removed_scene",
            "name": "Removed Scene",
            "unique_id": f"{MOCK_GATEWAY_SN}_removed_scene",
            "channel": 3,
            "id": 3
        }
        existing_selections = {
            "devices": [],
            "groups": [],
            "scenes": [mock_scenes[0], removed_scene]
        }

        schema = EntityDiscoveryHelper.prepare_entity_selection_schema(
            devices=[],
            groups=[],
            scenes=[mock_scenes[0]],  # Only first scene exists now
            existing_selections=existing_selections,
            show_diff=True
        )

        assert isinstance(schema, vol.Schema)

    def test_filter_selected_entities_all_types(
            self, mock_devices, mock_groups, mock_scenes):
        """Test filtering selected entities for all types."""
        user_input = {
            "devices": [mock_devices[0]["unique_id"]],
            "groups": [mock_groups[1]["unique_id"]],
            "scenes": [mock_scenes[0]["unique_id"]]
        }
        discovered_entities = {
            "devices": mock_devices,
            "groups": mock_groups,
            "scenes": mock_scenes
        }

        result = EntityDiscoveryHelper.filter_selected_entities(
            user_input, discovered_entities
        )

        assert "devices" in result
        assert "groups" in result
        assert "scenes" in result
        assert len(result["devices"]) == 1
        assert len(result["groups"]) == 1
        assert len(result["scenes"]) == 1
        assert result["devices"][0]["sn"] == "dev1"
        assert result["groups"][0]["sn"] == "group2"
        assert result["scenes"][0]["sn"] == "scene1"

    def test_filter_selected_entities_partial_selection(
            self, mock_devices, mock_groups):
        """Test filtering with partial entity selection."""
        user_input = {
            "devices": [
                mock_devices[0]["unique_id"], mock_devices[1]["unique_id"]
            ]
        }
        discovered_entities = {
            "devices": mock_devices,
            "groups": mock_groups,
            "scenes": []
        }

        result = EntityDiscoveryHelper.filter_selected_entities(
            user_input, discovered_entities
        )

        assert "devices" in result
        assert "groups" not in result
        assert "scenes" not in result
        assert len(result["devices"]) == 2

    def test_filter_selected_entities_no_match(
            self, mock_devices, mock_groups, mock_scenes):
        """Test filtering when no entities match selection."""
        user_input = {
            "devices": ["nonexistent_id"],
            "groups": ["nonexistent_group_id"],
            "scenes": ["nonexistent_scene_id"]
        }
        discovered_entities = {
            "devices": mock_devices,
            "groups": mock_groups,
            "scenes": mock_scenes
        }

        result = EntityDiscoveryHelper.filter_selected_entities(
            user_input, discovered_entities
        )

        assert result["devices"] == []
        assert result["groups"] == []
        assert result["scenes"] == []

    def test_filter_selected_entities_empty_input(
            self, mock_devices, mock_groups, mock_scenes):
        """Test filtering with empty user input."""
        user_input = {}
        discovered_entities = {
            "devices": mock_devices,
            "groups": mock_groups,
            "scenes": mock_scenes
        }

        result = EntityDiscoveryHelper.filter_selected_entities(
            user_input, discovered_entities
        )

        assert not result

    def test_filter_selected_entities_empty_discovered(self):
        """Test filtering with empty discovered entities."""
        user_input = {
            "devices": ["some_id"],
            "groups": ["some_group_id"],
            "scenes": ["some_scene_id"]
        }
        discovered_entities = {}

        result = EntityDiscoveryHelper.filter_selected_entities(
            user_input, discovered_entities
        )

        assert not result

    def test_filter_selected_entities_missing_entity_types(
            self, mock_devices
    ):
        user_input = {
            "devices": [mock_devices[0]["unique_id"]],
            "groups": ["some_group_id"],  # Not in discovered_entities
            "scenes": ["some_scene_id"]   # Not in discovered_entities
        }
        discovered_entities = {
            "devices": mock_devices
        }

        result = EntityDiscoveryHelper.filter_selected_entities(
            user_input, discovered_entities
        )

        assert "devices" in result
        assert "groups" not in result
        assert "scenes" not in result
        assert len(result["devices"]) == 1
