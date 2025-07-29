"""Test the __init__.py module for Dali Center integration."""

import logging
from unittest.mock import Mock, patch

import pytest
from homeassistant.core import HomeAssistant

from custom_components.dali_center import _setup_dependency_logging, _notify_user_error
from tests.conftest import MOCK_GATEWAY_SN


class TestSetupDependencyLogging:
    """Test the _setup_dependency_logging function."""

    def test_setup_dependency_logging_debug_level(self):
        """Test setting up dependency logging with debug level."""
        with patch("logging.getLogger") as mock_get_logger:
            # Mock the current logger
            mock_current_logger = Mock()
            mock_current_logger.getEffectiveLevel.return_value = logging.DEBUG

            # Mock the gateway logger
            mock_gateway_logger = Mock()

            # Configure getLogger to return appropriate loggers
            def get_logger_side_effect(name):
                if name == "custom_components.dali_center":
                    return mock_current_logger
                elif name == "PySrDaliGateway":
                    return mock_gateway_logger
                return Mock()

            mock_get_logger.side_effect = get_logger_side_effect

            # Call the function
            _setup_dependency_logging()

            # Verify the gateway logger level was set
            mock_gateway_logger.setLevel.assert_called_once_with(logging.DEBUG)

    def test_setup_dependency_logging_info_level(self):
        """Test setting up dependency logging with info level."""
        with patch("logging.getLogger") as mock_get_logger:
            # Mock the current logger
            mock_current_logger = Mock()
            mock_current_logger.getEffectiveLevel.return_value = logging.INFO

            # Mock the gateway logger
            mock_gateway_logger = Mock()

            # Configure getLogger to return appropriate loggers
            def get_logger_side_effect(name):
                if name == "custom_components.dali_center":
                    return mock_current_logger
                elif name == "PySrDaliGateway":
                    return mock_gateway_logger
                return Mock()

            mock_get_logger.side_effect = get_logger_side_effect

            # Call the function
            _setup_dependency_logging()

            # Verify the gateway logger level was set
            mock_gateway_logger.setLevel.assert_called_once_with(logging.INFO)


class TestNotifyUserError:
    """Test the _notify_user_error function."""

    @pytest.fixture
    def mock_hass(self):
        """Create a mock HomeAssistant instance."""
        return Mock(spec=HomeAssistant)

    @pytest.mark.asyncio
    @patch("custom_components.dali_center.async_create")
    async def test_notify_user_error_without_gateway_sn(
        self, mock_async_create, mock_hass
    ):
        title = "Connection Error"
        message = "Failed to connect to gateway"

        await _notify_user_error(mock_hass, title, message)

        # Verify async_create was called with correct parameters
        mock_async_create.assert_called_once()
        call_args = mock_async_create.call_args

        assert call_args[0][0] is mock_hass  # hass parameter
        assert call_args[0][1] == message    # message parameter
        assert call_args[1]["title"] == "DALI Center: Connection Error"
        assert "notification_id" in call_args[1]

    @pytest.mark.asyncio
    @patch("custom_components.dali_center.async_create")
    async def test_notify_user_error_with_gateway_sn(
        self, mock_async_create, mock_hass
    ):
        title = "Device Error"
        message = "Device not responding"

        await _notify_user_error(mock_hass, title, message, MOCK_GATEWAY_SN)

        # Verify async_create was called with correct parameters
        mock_async_create.assert_called_once()
        call_args = mock_async_create.call_args

        assert call_args[0][0] is mock_hass  # hass parameter
        assert call_args[0][1] == message    # message parameter
        assert call_args[1]["title"] == (
            f"DALI Center ({MOCK_GATEWAY_SN}): Device Error"
        )
        assert "notification_id" in call_args[1]

    @pytest.mark.asyncio
    @patch("custom_components.dali_center.async_create")
    async def test_notify_user_error_notification_id_generation(
        self, mock_async_create, mock_hass
    ):
        title = "Test Error"
        message = "Test message"

        await _notify_user_error(mock_hass, title, message, MOCK_GATEWAY_SN)

        # Get the notification_id from the call
        call_args = mock_async_create.call_args
        notification_id = call_args[1]["notification_id"]

        # Verify the notification_id format
        expected_hash = hash(title + message)
        expected_id = f"dali_center_{MOCK_GATEWAY_SN}_{expected_hash}"
        assert notification_id == expected_id

    @pytest.mark.asyncio
    @patch("custom_components.dali_center.async_create")
    async def test_notify_user_error_empty_gateway_sn(
        self, mock_async_create, mock_hass
    ):
        title = "General Error"
        message = "Something went wrong"

        await _notify_user_error(mock_hass, title, message, "")

        # Verify async_create was called with correct parameters
        mock_async_create.assert_called_once()
        call_args = mock_async_create.call_args

        assert call_args[1]["title"] == "DALI Center: General Error"

        # Verify notification_id format for empty gateway_sn
        notification_id = call_args[1]["notification_id"]
        expected_hash = hash(title + message)
        expected_id = f"dali_center__{expected_hash}"
        assert notification_id == expected_id

    @pytest.mark.asyncio
    @patch("custom_components.dali_center.async_create")
    async def test_notify_user_error_different_messages_different_ids(
        self, mock_async_create, mock_hass
    ):
        # First call
        await _notify_user_error(
            mock_hass, "Error 1", "Message 1", MOCK_GATEWAY_SN
        )
        first_call_args = mock_async_create.call_args
        first_notification_id = first_call_args[1]["notification_id"]

        # Reset mock for second call
        mock_async_create.reset_mock()

        # Second call with different message
        await _notify_user_error(
            mock_hass, "Error 2", "Message 2", MOCK_GATEWAY_SN
        )
        second_call_args = mock_async_create.call_args
        second_notification_id = second_call_args[1]["notification_id"]

        # Verify the notification IDs are different
        assert first_notification_id != second_notification_id
