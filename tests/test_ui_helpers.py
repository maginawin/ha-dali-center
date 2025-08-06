"""Test UI formatting and display helpers for config flow."""
# pylint: disable=protected-access

import pytest
from unittest.mock import patch

from custom_components.dali_center.config_flow_helpers.ui_helpers import (
    UIFormattingHelper
)

class TestUIFormattingHelper:
    """Test UIFormattingHelper class."""

    @pytest.fixture
    def mock_discovered_entities(self):
        """Create mock discovered entities for testing."""
        return {
            "devices": [
                {"sn": "dev1", "name": "Device 1"},
                {"sn": "dev2", "name": "Device 2"}
            ],
            "groups": [
                {"sn": "group1", "name": "Group 1"},
                {"sn": "group2", "name": "Group 2"},
                {"sn": "group3", "name": "Group 3"}
            ],
            "scenes": [
                {"sn": "scene1", "name": "Scene 1"}
            ]
        }

    @pytest.fixture
    def mock_refresh_results(self):
        """Create mock refresh results for testing."""
        return {
            "devices_count": 3,
            "devices_added": [
                {"name": "New Device", "unique_id": "new_dev_id"}
            ],
            "devices_removed": [
                {"name": "Old Device", "unique_id": "old_dev_id"}
            ],
            "groups_count": 2,
            "groups_added": [],
            "groups_removed": [
                {"name": "Removed Group", "channel": 1, "id": 1}
            ],
            "scenes_count": 1,
            "scenes_added": [
                {"name": "New Scene", "channel": 2, "id": 2}
            ],
            "scenes_removed": []
        }

    def test_format_discovery_summary_all_types(self, mock_discovered_entities):
        """Test format discovery summary with all entity types."""
        result = UIFormattingHelper.format_discovery_summary(
            mock_discovered_entities,
            refresh_devices=True,
            refresh_groups=True,
            refresh_scenes=True
        )

        assert "Discovered Devices: 2" in result
        assert "Discovered Groups: 3" in result
        assert "Discovered Scenes: 1" in result

    def test_format_discovery_summary_partial_refresh(
            self, mock_discovered_entities
    ):
        """Test format discovery summary with partial refresh enabled."""
        result = UIFormattingHelper.format_discovery_summary(
            mock_discovered_entities,
            refresh_devices=True,
            refresh_groups=False,
            refresh_scenes=True
        )

        assert "Discovered Devices: 2" in result
        assert "Groups" not in result
        assert "Discovered Scenes: 1" in result

    def test_format_discovery_summary_no_refresh(
            self, mock_discovered_entities
    ):
        """Test format discovery summary with no refresh enabled."""
        result = UIFormattingHelper.format_discovery_summary(
            mock_discovered_entities,
            refresh_devices=False,
            refresh_groups=False,
            refresh_scenes=False
        )

        assert result == "No entities discovered"

    def test_format_discovery_summary_missing_entity_types(
            self
    ):
        """Test format discovery summary with missing entity types."""
        incomplete_entities = {
            "devices": [{"sn": "dev1", "name": "Device 1"}]
            # Missing groups and scenes
        }

        result = UIFormattingHelper.format_discovery_summary(
            incomplete_entities,
            refresh_devices=True,
            refresh_groups=True,
            refresh_scenes=True
        )

        assert "Discovered Devices: 1" in result
        assert "Groups" not in result
        assert "Scenes" not in result

    def test_format_discovery_summary_empty_entities(self):
        """Test format discovery summary with empty entity lists."""
        empty_entities = {
            "devices": [],
            "groups": [],
            "scenes": []
        }

        result = UIFormattingHelper.format_discovery_summary(
            empty_entities,
            refresh_devices=True,
            refresh_groups=True,
            refresh_scenes=True
        )

        assert "Discovered Devices: 0" in result
        assert "Discovered Groups: 0" in result
        assert "Discovered Scenes: 0" in result

    def test_format_refresh_results_comprehensive(self, mock_refresh_results):
        """Test format refresh results with comprehensive data."""
        result = UIFormattingHelper.format_refresh_results(mock_refresh_results)

        assert "Total Devices: 3" in result
        assert "Added Devices (1):" in result
        assert "New Device" in result
        assert "Removed Devices (1):" in result
        assert "Old Device" in result

        assert "Total Groups: 2" in result
        assert "No groups added" in result
        assert "Removed Groups (1):" in result
        assert "Removed Group" in result

        assert "Total Scenes: 1" in result
        assert "Added Scenes (1):" in result
        assert "New Scene" in result
        assert "No scenes removed" in result

    def test_format_refresh_results_empty(self):
        """Test format refresh results with empty results."""
        result = UIFormattingHelper.format_refresh_results({})
        assert result == "No items refreshed"

    def test_format_refresh_results_none(self):
        """Test format refresh results with None input."""
        result = UIFormattingHelper.format_refresh_results(None)
        assert result == "No items refreshed"

    def test_format_refresh_results_minimal(self):
        """Test format refresh results with minimal data."""
        minimal_results = {
            "devices_count": 1,
            "devices_added": [],
            "devices_removed": []
        }

        result = UIFormattingHelper.format_refresh_results(minimal_results)

        assert "Total Devices: 1" in result
        assert "No devices added" in result
        assert "No devices removed" in result

    def test_format_refresh_results_groups_with_callable_formatter(self):
        """Test format refresh results for groups with callable formatter."""
        results_with_groups = {
            "groups_count": 1,
            "groups_added": [
                {"name": "Test Group", "channel": 5, "id": 10}
            ],
            "groups_removed": []
        }

        result = UIFormattingHelper.format_refresh_results(results_with_groups)

        assert "Total Groups: 1" in result
        assert "Added Groups (1):" in result
        assert "Test Group" in result
        assert "Channel: 5" in result
        assert "Group: 10" in result

    def test_format_refresh_results_scenes_with_callable_formatter(self):
        """Test format refresh results for scenes with callable formatter."""
        results_with_scenes = {
            "scenes_count": 1,
            "scenes_added": [
                {"name": "Test Scene", "channel": 3, "id": 7}
            ],
            "scenes_removed": []
        }

        result = UIFormattingHelper.format_refresh_results(results_with_scenes)

        assert "Total Scenes: 1" in result
        assert "Added Scenes (1):" in result
        assert "Test Scene" in result
        assert "Channel: 3" in result
        assert "Scene: 7" in result

    def test_format_added_removed_with_items(self):
        """Test _format_added_removed method with items."""
        results = {
            "devices_added": [
                {"name": "Device A", "unique_id": "dev_a"}
            ],
            "devices_removed": [
                {"name": "Device B", "unique_id": "dev_b"}
            ]
        }

        result = UIFormattingHelper._format_added_removed(
            results, "devices", "name", "unique_id"
        )

        assert "Added Devices (1):" in result
        assert "Device A" in result
        assert "ID: dev_a" in result
        assert "Removed Devices (1):" in result
        assert "Device B" in result
        assert "ID: dev_b" in result

    def test_format_added_removed_empty_items(self):
        """Test _format_added_removed method with empty items."""
        results = {
            "devices_added": [],
            "devices_removed": []
        }

        result = UIFormattingHelper._format_added_removed(
            results, "devices", "name", "unique_id"
        )

        assert "No devices added" in result
        assert "No devices removed" in result

    def test_format_added_removed_callable_formatter(
            self
    ):
        """Test _format_added_removed method with callable formatter."""
        results = {
            "groups_added": [
                {"name": "Group X", "channel": 2, "id": 5}
            ],
            "groups_removed": []
        }

        def format_group(group):
            return (
            f"Channel: {group.get("channel", "N/A")}, "
            f"Group: {group.get("id", "N/A")}"
        )

        result = UIFormattingHelper._format_added_removed(
            results, "groups", "name", format_group
        )

        assert "Added Groups (1):" in result
        assert "Group X" in result
        assert "Channel: 2" in result
        assert "Group: 5" in result

    def test_format_added_removed_missing_name(self):
        """Test _format_added_removed method when item has no name."""
        results = {
            "devices_added": [
                {"unique_id": "dev_no_name"}  # Missing name field
            ],
            "devices_removed": []
        }

        result = UIFormattingHelper._format_added_removed(
            results, "devices", "name", "unique_id"
        )

        assert "Added Devices (1):" in result
        assert "Unnamed" in result
        assert "ID: dev_no_name" in result

    def test_format_added_removed_missing_id(self):
        """Test _format_added_removed method when item has no ID."""
        results = {
            "devices_added": [
                {"name": "Device Missing ID"}  # Missing unique_id field
            ],
            "devices_removed": []
        }

        result = UIFormattingHelper._format_added_removed(
            results, "devices", "name", "unique_id"
        )

        assert "Added Devices (1):" in result
        assert "Device Missing ID" in result
        assert "ID: N/A" in result

    def test_calculate_entity_differences_devices(self):
        """Test calculate entity differences for devices."""
        selected = {
            "devices": [
                {"unique_id": "dev1", "name": "Device 1"},
                {"unique_id": "dev2", "name": "Device 2"}
            ]
        }
        current_data = {
            "devices": [
                {"unique_id": "dev1", "name": "Device 1"},
                {"unique_id": "dev3", "name": "Device 3"}
            ]
        }

        find_diff_path = (
            "custom_components.dali_center.config_flow_helpers"
            ".ui_helpers.find_set_differences"
        )
        with patch(find_diff_path) as mock_diff:
            mock_diff.return_value = (
                [{"unique_id": "dev2", "name": "Device 2"}],  # added
                [{"unique_id": "dev3", "name": "Device 3"}]   # removed
            )

            result = UIFormattingHelper.calculate_entity_differences(
                selected, current_data,
                refresh_devices=True,
                refresh_groups=False,
                refresh_scenes=False
            )

            assert "devices_added" in result
            assert "devices_removed" in result
            assert "devices_count" in result
            assert result["devices_count"] == 2
            mock_diff.assert_called_once_with(
                selected["devices"],
                current_data.get("devices", []),
                "unique_id"
            )

    def test_calculate_entity_differences_groups(self):
        """Test calculate entity differences for groups."""
        selected = {
            "groups": [
                {"unique_id": "group1", "name": "Group 1"},
                {"unique_id": "group2", "name": "Group 2"}
            ]
        }
        current_data = {
            "groups": [
                {"unique_id": "group1", "name": "Group 1"}
            ]
        }

        find_diff_path = (
            "custom_components.dali_center.config_flow_helpers"
            ".ui_helpers.find_set_differences"
        )
        with patch(find_diff_path) as mock_diff:
            mock_diff.return_value = (
                [{"unique_id": "group2", "name": "Group 2"}],  # added
                []  # removed
            )

            result = UIFormattingHelper.calculate_entity_differences(
                selected, current_data,
                refresh_devices=False,
                refresh_groups=True,
                refresh_scenes=False
            )

            assert "groups_added" in result
            assert "groups_removed" in result
            assert "groups_count" in result
            assert result["groups_count"] == 2

    def test_calculate_entity_differences_scenes(self):
        """Test calculate entity differences for scenes."""
        selected = {
            "scenes": [
                {"unique_id": "scene1", "name": "Scene 1"}
            ]
        }
        current_data = {
            "scenes": [
                {"unique_id": "scene1", "name": "Scene 1"},
                {"unique_id": "scene2", "name": "Scene 2"}
            ]
        }

        find_diff_path = (
            "custom_components.dali_center.config_flow_helpers"
            ".ui_helpers.find_set_differences"
        )
        with patch(find_diff_path) as mock_diff:
            mock_diff.return_value = (
                [],  # added
                [{"unique_id": "scene2", "name": "Scene 2"}]  # removed
            )

            result = UIFormattingHelper.calculate_entity_differences(
                selected, current_data,
                refresh_devices=False,
                refresh_groups=False,
                refresh_scenes=True
            )

            assert "scenes_added" in result
            assert "scenes_removed" in result
            assert "scenes_count" in result
            assert result["scenes_count"] == 1

    def test_calculate_entity_differences_no_refresh(self):
        """Test calculate entity differences when no refresh is enabled."""
        selected = {
            "devices": [{"unique_id": "dev1", "name": "Device 1"}],
            "groups": [{"unique_id": "group1", "name": "Group 1"}],
            "scenes": [{"unique_id": "scene1", "name": "Scene 1"}]
        }
        current_data = {}

        result = UIFormattingHelper.calculate_entity_differences(
            selected, current_data,
            refresh_devices=False,
            refresh_groups=False,
            refresh_scenes=False
        )

        assert not result

    def test_calc_entity_differences_missing_entities_in_selected(
            self
    ):
        """Test calc entity differences when entities missing in selected."""
        selected = {}  # No entities selected
        current_data = {
            "devices": [{"unique_id": "dev1", "name": "Device 1"}]
        }

        result = UIFormattingHelper.calculate_entity_differences(
            selected, current_data,
            refresh_devices=True,
            refresh_groups=True,
            refresh_scenes=True
        )

        assert not result  # No processing if entities not in selected

    def test_calc_entity_differences_missing_entities_in_current(
            self
    ):
        """Test calc entity differences when entities missing in current."""
        selected = {
            "devices": [{"unique_id": "dev1", "name": "Device 1"}]
        }
        current_data = {}  # No current data

        find_diff_path = (
            "custom_components.dali_center.config_flow_helpers"
            ".ui_helpers.find_set_differences"
        )
        with patch(find_diff_path) as mock_diff:
            mock_diff.return_value = (
                [{"unique_id": "dev1", "name": "Device 1"}],  # added
                []  # removed
            )

            result = UIFormattingHelper.calculate_entity_differences(
                selected, current_data,
                refresh_devices=True,
                refresh_groups=False,
                refresh_scenes=False
            )

            assert "devices_added" in result
            assert "devices_removed" in result
            assert "devices_count" in result
            mock_diff.assert_called_once_with(
                selected["devices"],
                [],  # Empty list when missing from current_data
                "unique_id"
            )

    def test_get_discovery_instructions(self):
        """Test get discovery instructions."""
        result = UIFormattingHelper.get_discovery_instructions()

        assert "## DALI Gateway Discovery" in result
        assert "Two-step process:" in result
        assert "Click SUBMIT" in result
        assert "RESET button" in result
        assert "3 minutes" in result

    def test_get_discovery_failed_message(self):
        """Test get discovery failed message."""
        result = UIFormattingHelper.get_discovery_failed_message()

        assert "## Discovery Failed" in result
        assert "timed out" in result
        assert "3 minutes" in result
        assert "Gateway is **powered**" in result
        assert "RESET button was pressed" in result
        assert "retry" in result

    def test_get_no_gateways_message(self):
        """Test get no gateways found message."""
        result = UIFormattingHelper.get_no_gateways_message()

        assert "## No Gateways Found" in result
        assert "Gateway is **powered**" in result
        assert "RESET button was pressed" in result
        assert "not already configured" in result
        assert "retry" in result

    def test_get_success_message(self):
        """Test get gateway selection success message."""
        result = UIFormattingHelper.get_success_message(3)

        assert "## Success!" in result
        assert "Found **3 gateway(s)**" in result
        assert "Select one to configure" in result

    def test_get_success_message_single_gateway(self):
        """Test get success message with single gateway."""
        result = UIFormattingHelper.get_success_message(1)

        assert "Found **1 gateway(s)**" in result

    def test_format_gateway_options(self):
        """Test format gateway selection options."""
        gateways = [
            {
                "gw_sn": "DALI123456",
                "name": "Gateway 1"
            },
            {
                "gw_sn": "DALI789012",
                "name": "Gateway 2"
            }
        ]

        result = UIFormattingHelper.format_gateway_options(gateways)

        assert isinstance(result, dict)
        assert "DALI123456" in result
        assert "DALI789012" in result
        assert result["DALI123456"] == "Gateway 1 (DALI123456)"
        assert result["DALI789012"] == "Gateway 2 (DALI789012)"

    def test_format_gateway_options_empty(self):
        """Test format gateway options with empty list."""
        result = UIFormattingHelper.format_gateway_options([])

        assert isinstance(result, dict)
        assert len(result) == 0

    def test_format_gateway_options_single(
            self
    ):
        """Test format gateway options with single gateway."""
        gateways = [
            {
                "gw_sn": "SINGLE123",
                "name": "Single Gateway"
            }
        ]

        result = UIFormattingHelper.format_gateway_options(gateways)

        assert len(result) == 1
        assert "SINGLE123" in result
        assert result["SINGLE123"] == "Single Gateway (SINGLE123)"
