"""Test event platform for Dali Center integration."""
# pylint: disable=protected-access

import pytest
from unittest.mock import Mock, patch

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry

from custom_components.dali_center.event import (
    async_setup_entry,
    DaliCenterPanelEvent,
    _generate_event_types_for_panel
)
from custom_components.dali_center.const import DOMAIN
from custom_components.dali_center.types import DaliCenterData
from tests.conftest import (
    MockDaliGateway,
    MockDevice,
    MOCK_GATEWAY_SN
)

# Module path constant to avoid repetition
EM = "custom_components.dali_center.event"


class TestGenerateEventTypes:
    """Test the _generate_event_types_for_panel function."""

    def test_generate_event_types_2_button_panel(self):
        """Test event types for 2-button panel."""
        event_types = _generate_event_types_for_panel("0302")
        expected_count = 2 * 4  # 2 buttons × 4 events per button
        assert len(event_types) == expected_count

        # Check specific events exist
        assert "button_1_single_click" in event_types
        assert "button_2_long_press_stop" in event_types

    def test_generate_event_types_4_button_panel(self):
        """Test event types for 4-button panel."""
        event_types = _generate_event_types_for_panel("0304")
        expected_count = 4 * 4  # 4 buttons × 4 events per button
        assert len(event_types) == expected_count

    def test_generate_event_types_unknown_device(self):
        """Test event types for unknown device defaults to fallback."""
        event_types = _generate_event_types_for_panel("unknown")
        assert len(event_types) == 3  # Fallback default events
        assert "button_1_single_click" in event_types
        assert "button_1_double_click" in event_types
        assert "button_1_long_press" in event_types


class TestEventPlatformSetup:
    """Test the event platform setup."""

    @pytest.fixture
    def mock_hass(self):
        """Create mock HomeAssistant instance."""
        return Mock(spec=HomeAssistant)

    def create_config_entry_with_data(self, data):
        """Create config entry with specific data."""
        gateway = MockDaliGateway()
        entry = ConfigEntry(
            version=1,
            minor_version=1,
            domain=DOMAIN,
            title="Test Gateway",
            data=data,
            source="user",
            entry_id="test_entry_id",
            unique_id=MOCK_GATEWAY_SN,
            options={},
            discovery_keys={},
            subentries_data=None,
        )
        entry.runtime_data = DaliCenterData(gateway=gateway)
        return entry

    @pytest.fixture
    def mock_add_entities(self):
        """Create mock add_entities callback."""
        return Mock(spec=AddEntitiesCallback)

    @pytest.mark.asyncio
    async def test_async_setup_entry_with_panel_devices(
        self, mock_hass, mock_add_entities
    ):
        """Test setup with panel devices."""
        config_entry = self.create_config_entry_with_data({
            "devices": [
                {"sn": "panel001", "name": "Panel 1",
                    "dev_type": "0304", "type": 2}
            ]
        })

        with patch(f"{EM}.is_panel_device", return_value=True):
            await async_setup_entry(mock_hass, config_entry, mock_add_entities)

        mock_add_entities.assert_called_once()
        entities = mock_add_entities.call_args[0][0]
        assert len(entities) == 1
        assert isinstance(entities[0], DaliCenterPanelEvent)

    @pytest.mark.asyncio
    async def test_async_setup_entry_no_panel_devices(
        self, mock_hass, mock_add_entities
    ):
        """Test setup with no panel devices."""
        config_entry = self.create_config_entry_with_data({
            "devices": [
                {"sn": "light001", "name": "Light 1",
                    "dev_type": "0101", "type": 1}
            ]
        })

        with patch(f"{EM}.is_panel_device", return_value=False):
            await async_setup_entry(mock_hass, config_entry, mock_add_entities)

        mock_add_entities.assert_not_called()

    @pytest.mark.asyncio
    async def test_async_setup_entry_empty_devices(
        self, mock_hass, mock_add_entities
    ):
        """Test setup with empty devices list."""
        config_entry = self.create_config_entry_with_data({
            "devices": []
        })

        await async_setup_entry(mock_hass, config_entry, mock_add_entities)

        mock_add_entities.assert_not_called()

    @pytest.mark.asyncio
    async def test_async_setup_entry_multiple_panel_devices(
        self, mock_hass, mock_add_entities
    ):
        """Test setup with multiple panel devices."""
        config_entry = self.create_config_entry_with_data({
            "devices": [
                {"sn": "panel001", "name": "Panel 1",
                    "dev_type": "0304", "type": 2},
                {"sn": "panel002", "name": "Panel 2",
                    "dev_type": "0306", "type": 2}
            ]
        })

        with patch(f"{EM}.is_panel_device", return_value=True):
            await async_setup_entry(mock_hass, config_entry, mock_add_entities)

        mock_add_entities.assert_called_once()
        entities = mock_add_entities.call_args[0][0]
        assert len(entities) == 2
        for entity in entities:
            assert isinstance(entity, DaliCenterPanelEvent)


class TestDaliCenterPanelEvent:
    """Test the DaliCenterPanelEvent class."""

    @pytest.fixture
    def mock_device(self):
        """Create mock panel device."""
        device = MockDevice()
        device.name = "Test Panel"
        device.unique_id = "gw123_panel001"
        device.dev_id = "panel001"
        device.gw_sn = MOCK_GATEWAY_SN
        return device

    @pytest.fixture
    def panel_event(self, mock_device):
        """Create panel event instance."""
        event = DaliCenterPanelEvent(mock_device)
        # Mock hass to avoid AttributeError
        mock_hass = Mock()
        mock_hass.bus = Mock()
        mock_hass.bus.async_fire = Mock()
        event.hass = mock_hass
        event.async_write_ha_state = Mock()
        return event

    def test_panel_event_icon(self, panel_event):
        """Test panel event icon property."""
        assert panel_event.icon == "mdi:gesture-tap-button"

    def test_panel_event_device_info(self, panel_event, mock_device):
        """Test panel event device_info property."""
        device_info = panel_event.device_info
        assert device_info is not None
        # The actual implementation uses device unique_id, not dev_id
        assert device_info["identifiers"] == {(DOMAIN, mock_device.unique_id)}

    def test_panel_event_available_default(self, panel_event):
        """Test panel event available property default value."""
        assert panel_event.available is True

    def test_panel_event_available_after_update(self, panel_event):
        """Test panel event available property after update."""
        # Mock hass to avoid RuntimeError
        panel_event.hass = Mock()
        panel_event.async_write_ha_state = Mock()

        panel_event._handle_device_update_available(False)
        assert panel_event.available is False
        panel_event.async_write_ha_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_panel_event_async_added_to_hass(self, panel_event):
        """Test panel event added to hass."""
        mock_hass = Mock()
        mock_dispatcher_connect = Mock()

        with patch(f"{EM}.async_dispatcher_connect", mock_dispatcher_connect):
            panel_event.hass = mock_hass
            await panel_event.async_added_to_hass()

        # Should connect to two dispatcher signals
        assert mock_dispatcher_connect.call_count == 2

    def test_handle_device_update_available(self, panel_event):
        """Test _handle_device_update_available method."""
        with patch.object(
            panel_event, "async_write_ha_state"
        ) as mock_write_state:
            panel_event._handle_device_update_available(False)

            assert panel_event._available is False
            mock_write_state.assert_called_once()

    def test_handle_device_update_single_click(self, panel_event):
        """Test _handle_device_update with single click event."""
        property_list = [
            {"dpid": 1, "keyNo": 1, "value": 1}  # Single click on button 1
        ]

        with patch.object(panel_event, "_trigger_event") as mock_trigger:
            with patch.object(panel_event, "async_write_ha_state"):
                with patch(f"{EM}.BUTTON_EVENTS", {1: "single_click"}):
                    panel_event._handle_device_update(property_list)
                    mock_trigger.assert_called_once_with(
                        "button_1_single_click"
                    )

    def test_handle_device_update_double_click(self, panel_event):
        """Test _handle_device_update with double click event."""
        property_list = [
            {"dpid": 2, "keyNo": 2, "value": 1}  # Double click on button 2
        ]

        with patch.object(panel_event, "_trigger_event") as mock_trigger:
            with patch.object(panel_event, "async_write_ha_state"):
                with patch(f"{EM}.BUTTON_EVENTS", {2: "double_click"}):
                    panel_event._handle_device_update(property_list)
                    mock_trigger.assert_called_once_with(
                        "button_2_double_click")

    def test_handle_device_update_long_press(self, panel_event):
        """Test _handle_device_update with long press event."""
        property_list = [
            {"dpid": 3, "keyNo": 3, "value": 1}  # Long press on button 3
        ]

        with patch.object(panel_event, "_trigger_event") as mock_trigger:
            with patch.object(panel_event, "async_write_ha_state"):
                with patch(f"{EM}.BUTTON_EVENTS", {3: "long_press"}):
                    panel_event._handle_device_update(property_list)

                    mock_trigger.assert_called_once_with("button_3_long_press")

    def test_handle_device_update_rotate(self, panel_event):
        """Test _handle_device_update with rotate event."""
        property_list = [
            # Rotate on button 1 with value 5
            {"dpid": 4, "keyNo": 1, "value": 5}
        ]

        with patch.object(panel_event, "_trigger_event") as mock_trigger:
            with patch.object(panel_event, "async_write_ha_state"):
                with patch(f"{EM}.BUTTON_EVENTS", {4: "rotate"}):
                    panel_event._handle_device_update(property_list)

                    mock_trigger.assert_called_once_with(
                        "button_1_rotate", {"rotate_value": 5})

    def test_handle_device_update_unknown_event(self, panel_event):
        """Test _handle_device_update with unknown event."""
        property_list = [
            {"dpid": 99, "keyNo": 1, "value": 1}  # Unknown dpid
        ]

        with patch.object(panel_event, "_trigger_event") as mock_trigger:
            with patch.object(panel_event, "async_write_ha_state"):
                with patch(f"{EM}.BUTTON_EVENTS", {}):
                    with patch(f"{EM}._LOGGER") as mock_logger:
                        panel_event._handle_device_update(property_list)

                        mock_trigger.assert_not_called()
                        mock_logger.debug.assert_called_once()

    def test_handle_device_update_multiple_events(self, panel_event):
        """Test _handle_device_update with multiple events."""
        property_list = [
            {"dpid": 1, "keyNo": 1, "value": 1},  # Single click on button 1
            {"dpid": 2, "keyNo": 2, "value": 1}   # Double click on button 2
        ]

        with patch.object(panel_event, "_trigger_event") as mock_trigger:
            with patch.object(panel_event, "async_write_ha_state"):
                with patch(
                    f"{EM}.BUTTON_EVENTS",
                    {1: "single_click", 2: "double_click"}
                ):
                    panel_event._handle_device_update(property_list)

                    assert mock_trigger.call_count == 2
                    mock_trigger.assert_any_call("button_1_single_click")
                    mock_trigger.assert_any_call("button_2_double_click")

    def test_handle_device_update_empty_property_list(self, panel_event):
        """Test _handle_device_update with empty property list."""
        with patch.object(panel_event, "_trigger_event") as mock_trigger:
            panel_event._handle_device_update([])

            mock_trigger.assert_not_called()

    def test_handle_device_update_missing_properties(self, panel_event):
        """Test _handle_device_update with missing properties."""
        property_list = [
            {"dpid": 1},  # Missing keyNo and value
            {"keyNo": 1}  # Missing dpid and value
        ]

        with patch.object(panel_event, "_trigger_event") as mock_trigger:
            with patch.object(panel_event, "async_write_ha_state"):
                with patch(f"{EM}.BUTTON_EVENTS", {1: "single_click"}):
                    with patch(f"{EM}._LOGGER"):
                        panel_event._handle_device_update(property_list)

                        assert mock_trigger.call_count == 1
                    mock_trigger.assert_called_with("button_None_single_click")
