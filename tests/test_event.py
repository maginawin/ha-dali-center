"""Tests for the Dali Center event platform."""

from unittest.mock import MagicMock, patch

from PySrDaliGateway.types import PanelEventType, PanelStatus
import pytest

from custom_components.dali_center.event import DaliCenterPanelEvent


@pytest.fixture
def mock_panel() -> MagicMock:
    """Create a mock Panel device."""
    panel = MagicMock()
    panel.dev_id = "test_device_123"
    panel.name = "Test Panel"
    panel.model = "Panel Model"
    panel.gw_sn = "gateway_sn_123"
    panel.status = "online"
    panel.get_available_event_types.return_value = [
        "button_1_press",
        "button_2_press",
    ]
    return panel


@pytest.fixture
def mock_hass() -> MagicMock:
    """Create a mock Home Assistant instance."""
    hass = MagicMock()
    hass.loop = MagicMock()
    hass.bus = MagicMock()
    return hass


@pytest.fixture
def panel_event(mock_panel: MagicMock, mock_hass: MagicMock) -> DaliCenterPanelEvent:
    """Create a DaliCenterPanelEvent instance."""
    event = DaliCenterPanelEvent(mock_panel)
    event.hass = mock_hass
    event.entity_id = "event.test_panel_buttons"
    return event


class TestDaliCenterPanelEvent:
    """Test DaliCenterPanelEvent callback behavior."""

    def test_handle_device_update_should_not_use_call_soon_threadsafe(
        self, panel_event: DaliCenterPanelEvent, mock_hass: MagicMock
    ) -> None:
        """Test that _handle_device_update does not use redundant call_soon_threadsafe.

        The callback is already dispatched to the event loop by PySrDaliGateway's
        _dispatch_callback, so using call_soon_threadsafe again is redundant and
        can cause race conditions during startup (Issue #63).
        """
        status: PanelStatus = {
            "event_name": "button_1_press",
            "key_no": 1,
            "event_type": PanelEventType.PRESS,
            "rotate_value": None,
        }

        with (
            patch.object(panel_event, "_trigger_event") as mock_trigger,
            patch.object(panel_event, "schedule_update_ha_state") as mock_schedule,
        ):
            panel_event._handle_device_update(status)  # noqa: SLF001

            # CRITICAL: call_soon_threadsafe should NOT be called
            # The buggy implementation calls it, causing the segfault
            mock_hass.loop.call_soon_threadsafe.assert_not_called()

            # _trigger_event should be called synchronously
            mock_trigger.assert_called_once_with("button_1_press")

            # schedule_update_ha_state should be called synchronously
            mock_schedule.assert_called_once()

    def test_handle_device_update_with_rotate_event(
        self, panel_event: DaliCenterPanelEvent, mock_hass: MagicMock
    ) -> None:
        """Test _handle_device_update with rotate event includes rotate_value."""
        status: PanelStatus = {
            "event_name": "knob_rotate",
            "key_no": 1,
            "event_type": PanelEventType.ROTATE,
            "rotate_value": 15,
        }

        with (
            patch.object(panel_event, "_trigger_event") as mock_trigger,
            patch.object(panel_event, "schedule_update_ha_state") as mock_schedule,
        ):
            panel_event._handle_device_update(status)  # noqa: SLF001

            # Should NOT use call_soon_threadsafe
            mock_hass.loop.call_soon_threadsafe.assert_not_called()

            # _trigger_event should include rotate_value
            mock_trigger.assert_called_once_with("knob_rotate", {"rotate_value": 15})

            mock_schedule.assert_called_once()

    def test_handle_device_update_fires_bus_event(
        self, panel_event: DaliCenterPanelEvent, mock_hass: MagicMock
    ) -> None:
        """Test that _handle_device_update fires event on the bus."""
        status: PanelStatus = {
            "event_name": "button_1_press",
            "key_no": 1,
            "event_type": PanelEventType.PRESS,
            "rotate_value": None,
        }

        with (
            patch.object(panel_event, "_trigger_event"),
            patch.object(panel_event, "schedule_update_ha_state"),
        ):
            panel_event._handle_device_update(status)  # noqa: SLF001

            # Should NOT use call_soon_threadsafe
            mock_hass.loop.call_soon_threadsafe.assert_not_called()

            # Bus event should be fired synchronously
            mock_hass.bus.async_fire.assert_called_once()
            call_args = mock_hass.bus.async_fire.call_args
            assert call_args[0][0] == "dali_center_event"
            assert call_args[0][1]["entity_id"] == "event.test_panel_buttons"
            assert call_args[0][1]["event_type"] == "button_1_press"
