"""Test device trigger for Dali Center event entities (standalone)."""
# pylint: disable=protected-access

from unittest.mock import Mock, patch

import pytest

from custom_components.dali_center.const import DOMAIN
from custom_components.dali_center.device_trigger import (
    TRIGGER_SCHEMA,
    async_get_triggers,
    async_validate_trigger_config,
)
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_ENTITY_ID,
    CONF_PLATFORM,
    CONF_TYPE,
)
from homeassistant.core import HomeAssistant

CFM = "custom_components.dali_center.device_trigger"


class TestDeviceTriggerStandalone:
    """Test device trigger functionality without global fixtures."""

    @pytest.fixture
    def mock_hass(self):
        """Create mock HomeAssistant instance."""
        mock = Mock(spec=HomeAssistant)
        mock.states = Mock()
        return mock

    @pytest.fixture
    def mock_registry(self):
        """Create mock entity registry."""
        registry = Mock()
        return registry

    @pytest.fixture
    def mock_entry(self):
        """Create mock registry entry."""
        entry = Mock()
        entry.entity_id = "event.test_panel_buttons"
        entry.domain = "event"
        entry.platform = DOMAIN
        entry.id = "test_entry_id"
        return entry

    @pytest.mark.asyncio
    async def test_async_get_triggers_no_entries(self, mock_hass, mock_registry):
        """Test getting triggers when no entries exist."""
        with (
            patch(f"{CFM}.er.async_get", return_value=mock_registry),
            patch(f"{CFM}.er.async_entries_for_device", return_value=[]),
        ):
            triggers = await async_get_triggers(mock_hass, "test_device_id")

        assert triggers == []

    @pytest.mark.asyncio
    async def test_async_get_triggers_with_event_types(
        self, mock_hass, mock_registry, mock_entry
    ):
        """Test getting triggers when entity has event_types."""
        event_types = ["button_1_single_click", "button_1_double_click"]

        with (
            patch(f"{CFM}.er.async_get", return_value=mock_registry),
            patch(f"{CFM}.er.async_entries_for_device", return_value=[mock_entry]),
        ):
            with patch(f"{CFM}.get_capability", return_value=event_types):
                triggers = await async_get_triggers(mock_hass, "test_device_id")

        assert len(triggers) == 2

        expected_trigger_1 = {
            CONF_PLATFORM: "device",
            CONF_DEVICE_ID: "test_device_id",
            CONF_DOMAIN: DOMAIN,
            CONF_ENTITY_ID: mock_entry.entity_id,
            CONF_TYPE: "button_1_single_click",
        }

        assert expected_trigger_1 in triggers

    def test_trigger_schema_validation(self):
        """Test trigger schema validation."""
        valid_config = {
            CONF_PLATFORM: "device",
            CONF_DEVICE_ID: "test_device_id",
            CONF_DOMAIN: DOMAIN,
            CONF_ENTITY_ID: "event.test_panel_buttons",
            CONF_TYPE: "button_1_single_click",
        }

        # Should not raise an exception
        result = TRIGGER_SCHEMA(valid_config)
        assert result == valid_config

    @pytest.mark.asyncio
    async def test_async_validate_trigger_config_valid(self, mock_hass):
        """Test validating valid trigger config."""
        config = {
            CONF_PLATFORM: "device",
            CONF_DEVICE_ID: "test_device_id",
            CONF_DOMAIN: DOMAIN,
            CONF_ENTITY_ID: "event.test_panel_buttons",
            CONF_TYPE: "button_1_single_click",
        }

        result = await async_validate_trigger_config(mock_hass, config)
        assert result == config
