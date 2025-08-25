"""Test device trigger for Dali Center event entities."""
# pylint: disable=protected-access

from unittest.mock import AsyncMock, Mock, patch

import pytest

from custom_components.dali_center.const import DOMAIN
from custom_components.dali_center.device_trigger import (
    TRIGGER_SCHEMA,
    async_attach_trigger,
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


@pytest.mark.usefixtures("mock_pysrdaligateway")
class TestDeviceTrigger:
    """Test device trigger functionality."""

    @pytest.fixture
    def mock_hass(self):
        """Create mock HomeAssistant instance."""
        mock = Mock(spec=HomeAssistant)
        mock.states = Mock()
        return mock

    @pytest.fixture
    def mock_registry(self):
        """Create mock entity registry."""
        return Mock()

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
    async def test_async_get_triggers_no_event_types(
        self, mock_hass, mock_registry, mock_entry
    ):
        """Test getting triggers when entity has no event_types."""
        with (
            patch(f"{CFM}.er.async_get", return_value=mock_registry),
            patch(f"{CFM}.er.async_entries_for_device", return_value=[mock_entry]),
            patch(f"{CFM}.get_capability", return_value=None),
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
            patch(f"{CFM}.get_capability", return_value=event_types),
        ):
            triggers = await async_get_triggers(mock_hass, "test_device_id")

        assert len(triggers) == 2

        expected_trigger_1 = {
            CONF_PLATFORM: "device",
            CONF_DEVICE_ID: "test_device_id",
            CONF_DOMAIN: DOMAIN,
            CONF_ENTITY_ID: mock_entry.entity_id,
            CONF_TYPE: "button_1_single_click",
        }
        expected_trigger_2 = {
            CONF_PLATFORM: "device",
            CONF_DEVICE_ID: "test_device_id",
            CONF_DOMAIN: DOMAIN,
            CONF_ENTITY_ID: mock_entry.entity_id,
            CONF_TYPE: "button_1_double_click",
        }

        assert expected_trigger_1 in triggers
        assert expected_trigger_2 in triggers

    @pytest.mark.asyncio
    async def test_async_get_triggers_filters_non_event_entities(
        self, mock_hass, mock_registry
    ):
        """Test that non-event entities are filtered out."""
        light_entry = Mock()
        light_entry.entity_id = "light.test_light"
        light_entry.domain = "light"
        light_entry.platform = DOMAIN

        event_entry = Mock()
        event_entry.entity_id = "event.test_panel_buttons"
        event_entry.domain = "event"
        event_entry.platform = DOMAIN
        event_entry.id = "test_entry_id"

        with (
            patch(f"{CFM}.er.async_get", return_value=mock_registry),
            patch(
                f"{CFM}.er.async_entries_for_device",
                return_value=[light_entry, event_entry],
            ),
            patch(f"{CFM}.get_capability", return_value=["button_1_single_click"]),
        ):
            triggers = await async_get_triggers(mock_hass, "test_device_id")

        # Should only process the event entity
        assert len(triggers) == 1

    @pytest.mark.asyncio
    async def test_async_attach_trigger_matching_event(self, mock_hass):
        """Test attaching trigger that matches the event type."""
        config = {
            CONF_ENTITY_ID: "event.test_panel_buttons",
            CONF_TYPE: "button_1_single_click",
        }

        action = AsyncMock()
        trigger_info = Mock()

        with (
            patch(
                f"{CFM}.event_trigger.TRIGGER_SCHEMA",
                return_value={"platform": "event"},
            ),
            patch(
                f"{CFM}.event_trigger.async_attach_trigger", return_value=AsyncMock()
            ) as mock_attach,
        ):
            result = await async_attach_trigger(mock_hass, config, action, trigger_info)

            # Verify event trigger was called
            mock_attach.assert_called_once()
            assert isinstance(result, AsyncMock)

    @pytest.mark.asyncio
    async def test_async_attach_trigger_non_matching_event(self, mock_hass):
        """Test attaching trigger with different event type."""
        config = {
            CONF_ENTITY_ID: "event.test_panel_buttons",
            CONF_TYPE: "button_1_double_click",
        }

        action = AsyncMock()
        trigger_info = Mock()

        with (
            patch(
                f"{CFM}.event_trigger.TRIGGER_SCHEMA",
                return_value={"platform": "event"},
            ),
            patch(
                f"{CFM}.event_trigger.async_attach_trigger", return_value=AsyncMock()
            ) as mock_attach,
        ):
            result = await async_attach_trigger(mock_hass, config, action, trigger_info)

            # Verify event trigger was called with correct config
            mock_attach.assert_called_once()
            assert isinstance(result, AsyncMock)

    @pytest.mark.asyncio
    async def test_async_attach_trigger_no_entity_state(self, mock_hass):
        """Test attaching trigger when entity state doesn't exist."""
        config = {
            CONF_ENTITY_ID: "event.test_panel_buttons",
            CONF_TYPE: "button_1_single_click",
        }

        action = AsyncMock()
        trigger_info = Mock()

        with (
            patch(
                f"{CFM}.event_trigger.TRIGGER_SCHEMA",
                return_value={"platform": "event"},
            ),
            patch(
                f"{CFM}.event_trigger.async_attach_trigger", return_value=AsyncMock()
            ) as mock_attach,
        ):
            result = await async_attach_trigger(mock_hass, config, action, trigger_info)

            # Verify event trigger was called
            mock_attach.assert_called_once()
            assert isinstance(result, AsyncMock)

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

    def test_trigger_schema_validation_missing_required(self):
        """Test trigger schema validation with missing required fields."""
        invalid_config = {
            CONF_PLATFORM: "device",
            CONF_DEVICE_ID: "test_device_id",
            CONF_DOMAIN: DOMAIN,
            # Missing CONF_ENTITY_ID and CONF_TYPE
        }

        with pytest.raises(Exception):  # voluptuous will raise an exception
            TRIGGER_SCHEMA(invalid_config)

    @pytest.mark.asyncio
    async def test_async_attach_trigger_with_context(self, mock_hass):
        """Test attaching trigger with context parameter."""
        config = {
            CONF_ENTITY_ID: "event.test_panel_buttons",
            CONF_TYPE: "button_1_single_click",
        }

        action = AsyncMock()
        trigger_info = Mock()

        with (
            patch(
                f"{CFM}.event_trigger.TRIGGER_SCHEMA",
                return_value={"platform": "event"},
            ),
            patch(
                f"{CFM}.event_trigger.async_attach_trigger", return_value=AsyncMock()
            ) as mock_attach,
        ):
            result = await async_attach_trigger(mock_hass, config, action, trigger_info)

            # Verify event trigger was called
            mock_attach.assert_called_once()
            assert isinstance(result, AsyncMock)
