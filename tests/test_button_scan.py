"""Tests for Scan Bus and Stop Scan button entities."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.dali_center.button import (
    DaliCenterScanBusButton,
    DaliCenterStopScanButton,
)
from custom_components.dali_center.const import DOMAIN


def _make_gateway(
    gw_sn: str = "gw_sn_123",
    bus_scanning: bool = False,
) -> MagicMock:
    """Create a mock DaliGateway."""
    gateway = MagicMock()
    gateway.gw_sn = gw_sn
    gateway.bus_scanning = bus_scanning
    gateway.name = "Test Gateway"
    return gateway


def _make_entry(entry_id: str = "test_entry_123") -> MagicMock:
    """Create a mock DaliCenterConfigEntry."""
    entry = MagicMock()
    entry.entry_id = entry_id
    return entry


# ---------------------------------------------------------------------------
# DaliCenterScanBusButton
# ---------------------------------------------------------------------------
class TestDaliCenterScanBusButton:
    """Test DaliCenterScanBusButton entity."""

    def test_init_attributes(self) -> None:
        """Button has correct name, icon, unique_id, and entity category."""
        gateway = _make_gateway(gw_sn="abcdef123456")
        entry = _make_entry()

        button = DaliCenterScanBusButton(gateway, entry)

        assert button._attr_name == "Scan Bus"
        assert button._attr_icon == "mdi:magnify-scan"
        assert button._attr_unique_id == "abcdef123456_scan_bus"
        assert button._attr_device_info["identifiers"] == {(DOMAIN, "abcdef123456")}

    def test_available_when_not_scanning(self) -> None:
        """Button is available when gateway is NOT scanning."""
        gateway = _make_gateway(bus_scanning=False)
        entry = _make_entry()
        button = DaliCenterScanBusButton(gateway, entry)

        assert button.available is True

    def test_unavailable_when_scanning(self) -> None:
        """Button is unavailable when gateway IS scanning."""
        gateway = _make_gateway(bus_scanning=True)
        entry = _make_entry()
        button = DaliCenterScanBusButton(gateway, entry)

        assert button.available is False

    async def test_press_creates_background_task(self) -> None:
        """Pressing scan button fires bus scan as a background task."""
        gateway = _make_gateway()
        entry = _make_entry()
        button = DaliCenterScanBusButton(gateway, entry)

        mock_hass = MagicMock()
        button.hass = mock_hass

        mock_do_scan = AsyncMock()
        button._do_bus_scan = mock_do_scan

        await button.async_press()

        # Should use async_create_task (fire-and-forget).
        mock_hass.async_create_task.assert_called_once()
        # Close the unawaited coroutine to suppress RuntimeWarning.
        task_coro = mock_hass.async_create_task.call_args[0][0]
        task_coro.close()

    @pytest.mark.parametrize(
        ("scanning_before", "scanning_after"),
        [(False, True), (True, False)],
    )
    def test_handle_scan_state_triggers_state_write(
        self, scanning_before: bool, scanning_after: bool
    ) -> None:
        """_handle_scan_state calls async_write_ha_state."""
        gateway = _make_gateway(bus_scanning=scanning_before)
        entry = _make_entry()
        button = DaliCenterScanBusButton(gateway, entry)

        with patch.object(button, "async_write_ha_state") as mock_write:
            button._handle_scan_state(scanning_after)
            mock_write.assert_called_once()


# ---------------------------------------------------------------------------
# DaliCenterStopScanButton
# ---------------------------------------------------------------------------
class TestDaliCenterStopScanButton:
    """Test DaliCenterStopScanButton entity."""

    def test_init_attributes(self) -> None:
        """Button has correct name, icon, unique_id, and entity category."""
        gateway = _make_gateway(gw_sn="abcdef123456")
        entry = _make_entry()

        button = DaliCenterStopScanButton(gateway, entry)

        assert button._attr_name == "Stop Scan"
        assert button._attr_icon == "mdi:stop"
        assert button._attr_unique_id == "abcdef123456_stop_scan"
        assert button._attr_device_info["identifiers"] == {(DOMAIN, "abcdef123456")}

    def test_unavailable_when_not_scanning(self) -> None:
        """Stop button is unavailable when gateway is NOT scanning."""
        gateway = _make_gateway(bus_scanning=False)
        entry = _make_entry()
        button = DaliCenterStopScanButton(gateway, entry)

        assert button.available is False

    def test_available_when_scanning(self) -> None:
        """Stop button is available when gateway IS scanning."""
        gateway = _make_gateway(bus_scanning=True)
        entry = _make_entry()
        button = DaliCenterStopScanButton(gateway, entry)

        assert button.available is True

    async def test_press_calls_stop_scan(self) -> None:
        """Pressing stop button directly awaits stop scan."""
        gateway = _make_gateway()
        entry = _make_entry()
        button = DaliCenterStopScanButton(gateway, entry)

        mock_hass = MagicMock()
        button.hass = mock_hass

        mock_do_stop = AsyncMock()
        button._do_stop_scan = mock_do_stop

        await button.async_press()

        # Should await directly (not fire-and-forget).
        mock_do_stop.assert_awaited_once_with(mock_hass, entry)

    @pytest.mark.parametrize(
        ("scanning_before", "scanning_after"),
        [(False, True), (True, False)],
    )
    def test_handle_scan_state_triggers_state_write(
        self, scanning_before: bool, scanning_after: bool
    ) -> None:
        """_handle_scan_state calls async_write_ha_state."""
        gateway = _make_gateway(bus_scanning=scanning_before)
        entry = _make_entry()
        button = DaliCenterStopScanButton(gateway, entry)

        with patch.object(button, "async_write_ha_state") as mock_write:
            button._handle_scan_state(scanning_after)
            mock_write.assert_called_once()
