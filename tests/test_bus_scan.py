"""Tests for DALI bus scan logic in __init__.py."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from custom_components.dali_center.const import (
    DOMAIN,
    SIGNAL_ADD_ENTITIES,
    SIGNAL_SCAN_STATE,
)


def _make_device(dev_id: str, name: str = "Device") -> MagicMock:
    """Create a mock Device with the given dev_id."""
    device = MagicMock()
    device.dev_id = dev_id
    device.name = name
    device.dev_type = "light"
    device.channel = 1
    device.address = 0
    device.dev_sn = "sn_123"
    device.gw_sn = "gw_sn_123"
    device.model = "Test Model"
    return device


def _make_gateway(
    gw_sn: str = "gw_sn_123",
    bus_scanning: bool = False,
    channel_total: list[int] | None = None,
) -> MagicMock:
    """Create a mock DaliGateway."""
    gateway = MagicMock()
    gateway.gw_sn = gw_sn
    gateway.bus_scanning = bus_scanning
    gateway.channel_total = channel_total or [0]
    gateway.scan_bus = AsyncMock(return_value=[])
    gateway.stop_scan = AsyncMock()
    return gateway


def _make_entry(
    gateway: MagicMock,
    devices: list[MagicMock] | None = None,
) -> MagicMock:
    """Create a mock DaliCenterConfigEntry with runtime_data."""
    entry = MagicMock()
    entry.entry_id = "test_entry_123"
    entry.runtime_data.gateway = gateway
    entry.runtime_data.devices = list(devices) if devices else []
    return entry


def _make_hass() -> MagicMock:
    """Create a mock HomeAssistant instance."""
    hass = MagicMock()
    hass.loop = MagicMock()
    return hass


# ---------------------------------------------------------------------------
# _async_do_bus_scan
# ---------------------------------------------------------------------------
class TestAsyncDoBusScan:
    """Test _async_do_bus_scan function."""

    @pytest.fixture(autouse=True)
    def _patch_ha_helpers(self) -> None:  # type: ignore[misc]
        """Patch Home Assistant helper functions used by _async_do_bus_scan."""
        with (
            patch(
                "custom_components.dali_center.async_create"
            ) as self.mock_notify_create,
            patch(
                "custom_components.dali_center.async_dismiss"
            ) as self.mock_notify_dismiss,
            patch(
                "custom_components.dali_center.async_dispatcher_send"
            ) as self.mock_dispatcher_send,
            patch(
                "custom_components.dali_center.dr.async_get"
            ) as self.mock_dev_reg_get,
        ):
            self.mock_dev_reg = MagicMock()
            self.mock_dev_reg_get.return_value = self.mock_dev_reg
            yield

    async def test_scan_discovers_new_devices(self) -> None:
        """New devices from scan are added to runtime_data and dispatched."""
        from custom_components.dali_center import _async_do_bus_scan

        gateway = _make_gateway()
        existing_dev = _make_device("existing_1")
        new_dev = _make_device("new_1", name="New Light")
        gateway.scan_bus.return_value = [existing_dev, new_dev]

        entry = _make_entry(gateway, devices=[existing_dev])
        hass = _make_hass()

        await _async_do_bus_scan(hass, entry)

        # New device should be appended to runtime_data.devices.
        assert new_dev in entry.runtime_data.devices
        assert len(entry.runtime_data.devices) == 2

        # Dispatcher should fire SIGNAL_ADD_ENTITIES with new devices.
        add_call = [
            c
            for c in self.mock_dispatcher_send.call_args_list
            if SIGNAL_ADD_ENTITIES in str(c)
        ]
        assert len(add_call) == 1
        dispatched_devices = add_call[0][0][2]  # third positional arg
        assert dispatched_devices == [new_dev]

    async def test_scan_removes_missing_devices(self) -> None:
        """Devices missing from scan results are removed from runtime_data and registry."""
        from custom_components.dali_center import _async_do_bus_scan

        gateway = _make_gateway()
        remaining_dev = _make_device("remaining_1")
        removed_dev = _make_device("removed_1", name="Gone Light")
        gateway.scan_bus.return_value = [remaining_dev]

        entry = _make_entry(gateway, devices=[remaining_dev, removed_dev])
        hass = _make_hass()

        # Mock device registry to return a device entry for removal.
        mock_device_entry = MagicMock()
        mock_device_entry.id = "ha_device_id_removed"
        self.mock_dev_reg.async_get_device.return_value = mock_device_entry

        await _async_do_bus_scan(hass, entry)

        # Removed device should no longer be in runtime_data.
        assert removed_dev not in entry.runtime_data.devices
        assert len(entry.runtime_data.devices) == 1

        # Device registry should remove the device.
        self.mock_dev_reg.async_remove_device.assert_called_once_with(
            "ha_device_id_removed"
        )

    async def test_scan_no_changes(self) -> None:
        """When scan results match existing devices, no add/remove actions occur."""
        from custom_components.dali_center import _async_do_bus_scan

        gateway = _make_gateway()
        dev = _make_device("dev_1")
        gateway.scan_bus.return_value = [dev]

        entry = _make_entry(gateway, devices=[dev])
        hass = _make_hass()

        await _async_do_bus_scan(hass, entry)

        # No SIGNAL_ADD_ENTITIES dispatch (only scan state signals).
        add_calls = [
            c
            for c in self.mock_dispatcher_send.call_args_list
            if SIGNAL_ADD_ENTITIES in str(c)
        ]
        assert len(add_calls) == 0

        # No device registry removal.
        self.mock_dev_reg.async_remove_device.assert_not_called()

    async def test_scan_sends_scan_state_signals(self) -> None:
        """Scan state signals are sent at start (True) and end (False)."""
        from custom_components.dali_center import _async_do_bus_scan

        gateway = _make_gateway()
        gateway.scan_bus.return_value = []
        entry = _make_entry(gateway)
        hass = _make_hass()

        await _async_do_bus_scan(hass, entry)

        scan_state_signal = f"{SIGNAL_SCAN_STATE}_{entry.entry_id}"
        scan_calls = [
            c
            for c in self.mock_dispatcher_send.call_args_list
            if scan_state_signal in str(c)
        ]
        assert len(scan_calls) == 2
        # First call: scanning started (True).
        assert scan_calls[0] == call(hass, scan_state_signal, True)
        # Second call: scanning stopped (False).
        assert scan_calls[1] == call(hass, scan_state_signal, False)

    async def test_scan_shows_notification(self) -> None:
        """Persistent notifications are shown during scan and on completion."""
        from custom_components.dali_center import _async_do_bus_scan

        gateway = _make_gateway()
        gateway.scan_bus.return_value = []
        entry = _make_entry(gateway)
        hass = _make_hass()

        await _async_do_bus_scan(hass, entry)

        # At least two notifications: scanning + result.
        assert self.mock_notify_create.call_count >= 2

    async def test_scan_timeout_shows_notification(self) -> None:
        """Timeout during scan shows failure notification and makes no changes."""
        from custom_components.dali_center import _async_do_bus_scan

        gateway = _make_gateway()
        gateway.scan_bus.side_effect = TimeoutError()

        dev = _make_device("dev_1")
        entry = _make_entry(gateway, devices=[dev])
        hass = _make_hass()

        await _async_do_bus_scan(hass, entry)

        # Device list unchanged.
        assert len(entry.runtime_data.devices) == 1

        # Timeout notification shown.
        timeout_calls = [
            c
            for c in self.mock_notify_create.call_args_list
            if "timed out" in str(c).lower()
        ]
        assert len(timeout_calls) == 1

    async def test_scan_exception_dismisses_notification(self) -> None:
        """Unexpected exception dismisses notification and makes no changes."""
        from custom_components.dali_center import _async_do_bus_scan

        gateway = _make_gateway()
        gateway.scan_bus.side_effect = RuntimeError("unexpected")

        dev = _make_device("dev_1")
        entry = _make_entry(gateway, devices=[dev])
        hass = _make_hass()

        await _async_do_bus_scan(hass, entry)

        # Device list unchanged.
        assert len(entry.runtime_data.devices) == 1

        # Notification dismissed.
        self.mock_notify_dismiss.assert_called_once()


# ---------------------------------------------------------------------------
# _async_do_stop_scan
# ---------------------------------------------------------------------------
class TestAsyncDoStopScan:
    """Test _async_do_stop_scan function."""

    @pytest.fixture(autouse=True)
    def _patch_ha_helpers(self) -> None:  # type: ignore[misc]
        """Patch Home Assistant helper functions."""
        with (
            patch(
                "custom_components.dali_center.async_dismiss"
            ) as self.mock_notify_dismiss,
        ):
            yield

    async def test_stop_scan_when_scanning(self) -> None:
        """Stop scan calls gateway.stop_scan and dismisses notification."""
        from custom_components.dali_center import _async_do_stop_scan

        gateway = _make_gateway(bus_scanning=True)
        entry = _make_entry(gateway)
        hass = _make_hass()

        await _async_do_stop_scan(hass, entry)

        gateway.stop_scan.assert_awaited_once()
        self.mock_notify_dismiss.assert_called_once()

    async def test_stop_scan_when_not_scanning(self) -> None:
        """Stop scan does nothing when no scan is in progress."""
        from custom_components.dali_center import _async_do_stop_scan

        gateway = _make_gateway(bus_scanning=False)
        entry = _make_entry(gateway)
        hass = _make_hass()

        await _async_do_stop_scan(hass, entry)

        gateway.stop_scan.assert_not_awaited()
        self.mock_notify_dismiss.assert_not_called()


# ---------------------------------------------------------------------------
# _remove_devices
# ---------------------------------------------------------------------------
class TestRemoveDevices:
    """Test _remove_devices helper."""

    def test_removes_from_runtime_data_and_registry(self) -> None:
        """Removed devices are cleaned from both runtime_data and device registry."""
        from custom_components.dali_center import _remove_devices

        gateway = _make_gateway()
        dev_a = _make_device("dev_a")
        dev_b = _make_device("dev_b")
        entry = _make_entry(gateway, devices=[dev_a, dev_b])
        hass = _make_hass()

        mock_device_entry = MagicMock()
        mock_device_entry.id = "ha_id_b"

        with patch("custom_components.dali_center.dr.async_get") as mock_dr:
            mock_dev_reg = MagicMock()
            mock_dr.return_value = mock_dev_reg
            mock_dev_reg.async_get_device.return_value = mock_device_entry

            _remove_devices(hass, entry, [dev_b])

        assert dev_b not in entry.runtime_data.devices
        assert dev_a in entry.runtime_data.devices
        mock_dev_reg.async_remove_device.assert_called_once_with("ha_id_b")

    def test_suppresses_value_error_for_missing_device(self) -> None:
        """Does not raise if device is already absent from runtime_data list."""
        from custom_components.dali_center import _remove_devices

        gateway = _make_gateway()
        dev_a = _make_device("dev_a")
        dev_missing = _make_device("dev_missing")
        entry = _make_entry(gateway, devices=[dev_a])
        hass = _make_hass()

        with patch("custom_components.dali_center.dr.async_get") as mock_dr:
            mock_dev_reg = MagicMock()
            mock_dr.return_value = mock_dev_reg
            mock_dev_reg.async_get_device.return_value = None

            # Should not raise.
            _remove_devices(hass, entry, [dev_missing])

        # dev_a still present.
        assert dev_a in entry.runtime_data.devices


# ---------------------------------------------------------------------------
# _resolve_entry_from_device_id
# ---------------------------------------------------------------------------
class TestResolveEntryFromDeviceId:
    """Test _resolve_entry_from_device_id helper."""

    def test_resolves_valid_device_id(self) -> None:
        """Returns config entry for a valid device_id."""
        from custom_components.dali_center import _resolve_entry_from_device_id

        hass = _make_hass()
        mock_device = MagicMock()
        mock_device.config_entries = {"entry_1"}

        mock_entry = MagicMock()
        mock_entry.domain = DOMAIN

        with patch("custom_components.dali_center.dr.async_get") as mock_dr:
            mock_dev_reg = MagicMock()
            mock_dr.return_value = mock_dev_reg
            mock_dev_reg.async_get.return_value = mock_device

            hass.config_entries.async_get_entry.return_value = mock_entry

            result = _resolve_entry_from_device_id(hass, "device_123")

        assert result is mock_entry

    def test_returns_none_for_unknown_device(self) -> None:
        """Returns None when device_id is not found in registry."""
        from custom_components.dali_center import _resolve_entry_from_device_id

        hass = _make_hass()

        with patch("custom_components.dali_center.dr.async_get") as mock_dr:
            mock_dev_reg = MagicMock()
            mock_dr.return_value = mock_dev_reg
            mock_dev_reg.async_get.return_value = None

            result = _resolve_entry_from_device_id(hass, "bad_id")

        assert result is None

    def test_returns_none_for_wrong_domain(self) -> None:
        """Returns None when device belongs to a different integration."""
        from custom_components.dali_center import _resolve_entry_from_device_id

        hass = _make_hass()
        mock_device = MagicMock()
        mock_device.config_entries = {"entry_1"}

        mock_entry = MagicMock()
        mock_entry.domain = "other_integration"

        with patch("custom_components.dali_center.dr.async_get") as mock_dr:
            mock_dev_reg = MagicMock()
            mock_dr.return_value = mock_dev_reg
            mock_dev_reg.async_get.return_value = mock_device

            hass.config_entries.async_get_entry.return_value = mock_entry

            result = _resolve_entry_from_device_id(hass, "device_123")

        assert result is None
