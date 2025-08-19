"""Test switch platform for Dali Center integration."""
# pylint: disable=protected-access

from unittest.mock import Mock, patch

import pytest

from custom_components.dali_center.const import DOMAIN
from custom_components.dali_center.switch import (
    DaliCenterIlluminanceSensorEnableSwitch,
    async_setup_entry,
)
from custom_components.dali_center.types import DaliCenterData
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from tests.conftest import MOCK_GATEWAY_SN, MockDaliGateway, MockDevice


class TestSwitchPlatformSetup:
    """Test the switch platform setup."""

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
    async def test_async_setup_entry_with_illuminance_sensors(
        self, mock_hass, mock_add_entities
    ):
        """Test setup with illuminance sensor devices."""
        config_entry = self.create_config_entry_with_data(
            {
                "devices": [
                    {"sn": "lux001", "name": "Lux 1", "dev_type": "0301", "type": 4}
                ]
            }
        )

        with patch(
            "custom_components.dali_center.switch.is_illuminance_sensor",
            return_value=True,
        ):
            await async_setup_entry(mock_hass, config_entry, mock_add_entities)

        mock_add_entities.assert_called_once()
        entities = mock_add_entities.call_args[0][0]
        assert len(entities) == 1
        assert isinstance(entities[0], DaliCenterIlluminanceSensorEnableSwitch)

    @pytest.mark.asyncio
    async def test_async_setup_entry_with_multiple_illuminance_sensors(
        self, mock_hass, mock_add_entities
    ):
        """Test setup with multiple illuminance sensor devices."""
        config_entry = self.create_config_entry_with_data(
            {
                "devices": [
                    {"sn": "lux001", "name": "Lux 1", "dev_type": "0301", "type": 4},
                    {"sn": "lux002", "name": "Lux 2", "dev_type": "0302", "type": 4},
                ]
            }
        )

        with patch(
            "custom_components.dali_center.switch.is_illuminance_sensor",
            return_value=True,
        ):
            await async_setup_entry(mock_hass, config_entry, mock_add_entities)

        mock_add_entities.assert_called_once()
        entities = mock_add_entities.call_args[0][0]
        assert len(entities) == 2
        for entity in entities:
            assert isinstance(entity, DaliCenterIlluminanceSensorEnableSwitch)

    @pytest.mark.asyncio
    async def test_async_setup_entry_with_no_illuminance_sensors(
        self, mock_hass, mock_add_entities
    ):
        """Test setup with no illuminance sensor devices."""
        config_entry = self.create_config_entry_with_data(
            {
                "devices": [
                    {
                        "sn": "light001",
                        "name": "Light 1",
                        "dev_type": "0101",
                        "type": 1,
                    },
                    {
                        "sn": "motion001",
                        "name": "Motion 1",
                        "dev_type": "0201",
                        "type": 3,
                    },
                ]
            }
        )

        with patch(
            "custom_components.dali_center.switch.is_illuminance_sensor",
            return_value=False,
        ):
            await async_setup_entry(mock_hass, config_entry, mock_add_entities)

        mock_add_entities.assert_not_called()

    @pytest.mark.asyncio
    async def test_async_setup_entry_mixed_devices(self, mock_hass, mock_add_entities):
        config_entry = self.create_config_entry_with_data(
            {
                "devices": [
                    {
                        "sn": "light001",
                        "name": "Light 1",
                        "dev_type": "0101",
                        "type": 1,
                    },
                    {"sn": "lux001", "name": "Lux 1", "dev_type": "0301", "type": 4},
                    {
                        "sn": "motion001",
                        "name": "Motion 1",
                        "dev_type": "0201",
                        "type": 3,
                    },
                ]
            }
        )

        def mock_is_illuminance_sensor(device_type):
            return device_type == "0301"  # Only lux001 should create a switch

        with patch(
            "custom_components.dali_center.switch.is_illuminance_sensor",
            side_effect=mock_is_illuminance_sensor,
        ):
            await async_setup_entry(mock_hass, config_entry, mock_add_entities)

        mock_add_entities.assert_called_once()
        entities = mock_add_entities.call_args[0][0]
        assert len(entities) == 1
        assert isinstance(entities[0], DaliCenterIlluminanceSensorEnableSwitch)

    @pytest.mark.asyncio
    async def test_async_setup_entry_empty_devices(self, mock_hass, mock_add_entities):
        """Test setup with empty devices list."""
        config_entry = self.create_config_entry_with_data({"devices": []})

        await async_setup_entry(mock_hass, config_entry, mock_add_entities)

        mock_add_entities.assert_not_called()

    @pytest.mark.asyncio
    async def test_async_setup_entry_duplicate_devices(
        self, mock_hass, mock_add_entities
    ):
        config_entry = self.create_config_entry_with_data(
            {
                "devices": [
                    {"sn": "lux001", "name": "Lux 1", "dev_type": "0301", "type": 4},
                    {
                        "sn": "lux001",
                        "name": "Lux 1 Duplicate",
                        "dev_type": "0301",
                        "type": 4,
                    },
                ]
            }
        )

        with patch(
            "custom_components.dali_center.switch.is_illuminance_sensor",
            return_value=True,
        ):
            await async_setup_entry(mock_hass, config_entry, mock_add_entities)

        mock_add_entities.assert_called_once()
        entities = mock_add_entities.call_args[0][0]
        # Should only create one switch for duplicate device
        assert len(entities) == 1


class TestDaliCenterIlluminanceSensorEnableSwitch:
    """Test the DaliCenterIlluminanceSensorEnableSwitch class."""

    @pytest.fixture
    def mock_device(self):
        """Create mock illuminance sensor device."""
        device = MockDevice()
        device.name = "Test Illuminance Sensor"
        device.unique_id = "gw123_lux001"
        device.dev_id = "lux001"
        device.sensor_enabled = True
        device.set_sensor_enabled = Mock()
        return device

    @pytest.fixture
    def illuminance_switch(self, mock_device):
        """Create illuminance sensor enable switch instance."""
        switch = DaliCenterIlluminanceSensorEnableSwitch(mock_device)
        # Mock hass to prevent AttributeError
        switch.hass = Mock()
        switch.hass.loop = Mock()
        switch.hass.loop.call_soon_threadsafe = Mock()
        return switch

    def test_illuminance_switch_name(self, illuminance_switch):
        """Test illuminance switch name property."""
        assert illuminance_switch.name == "Sensor Enable"

    def test_illuminance_switch_unique_id(self, illuminance_switch, mock_device):
        """Test illuminance switch unique_id property."""
        expected_id = f"{mock_device.dev_id}_sensor_enable"
        assert illuminance_switch.unique_id == expected_id

    def test_illuminance_switch_device_info(self, illuminance_switch, mock_device):
        """Test illuminance switch device_info property."""
        device_info = illuminance_switch.device_info
        assert device_info is not None
        assert device_info["identifiers"] == {(DOMAIN, mock_device.dev_id)}

    def test_illuminance_switch_available_default(self, illuminance_switch):
        """Test illuminance switch available property default value."""
        assert illuminance_switch.available is True

    def test_illuminance_switch_is_on_when_enabled(self, illuminance_switch):
        """Test is_on property when sensor is enabled."""
        illuminance_switch._attr_is_on = True
        assert illuminance_switch.is_on is True

    def test_illuminance_switch_is_on_when_disabled(self, illuminance_switch):
        """Test is_on property when sensor is disabled."""
        illuminance_switch._attr_is_on = False
        assert illuminance_switch.is_on is False

    def test_illuminance_switch_icon(self, illuminance_switch):
        """Test illuminance switch icon property."""
        assert illuminance_switch.icon == "mdi:brightness-6"

    @pytest.mark.asyncio
    async def test_illuminance_switch_async_turn_on(
        self, illuminance_switch, mock_device
    ):
        """Test turning on the illuminance sensor."""
        # Mock add_job method
        illuminance_switch.hass.add_job = Mock()

        await illuminance_switch.async_turn_on()

        mock_device.set_sensor_enabled.assert_called_once_with(True)
        # Verify add_job was called to dispatch the signal
        illuminance_switch.hass.add_job.assert_called_once()

    @pytest.mark.asyncio
    async def test_illuminance_switch_async_turn_off(
        self, illuminance_switch, mock_device
    ):
        """Test turning off the illuminance sensor."""
        # Mock add_job method
        illuminance_switch.hass.add_job = Mock()

        await illuminance_switch.async_turn_off()

        mock_device.set_sensor_enabled.assert_called_once_with(False)
        # Verify add_job was called to dispatch the signal
        illuminance_switch.hass.add_job.assert_called_once()

    @pytest.mark.asyncio
    async def test_illuminance_switch_async_turn_on_error(
        self, illuminance_switch, mock_device
    ):
        """Test turning on the illuminance sensor with error."""
        illuminance_switch.hass = Mock()
        mock_device.set_sensor_enabled.side_effect = Exception("Set sensor failed")

        with patch("custom_components.dali_center.switch._LOGGER") as mock_logger:
            await illuminance_switch.async_turn_on()

            mock_device.set_sensor_enabled.assert_called_once_with(True)
            mock_logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_illuminance_switch_async_turn_off_error(
        self, illuminance_switch, mock_device
    ):
        """Test turning off the illuminance sensor with error."""
        illuminance_switch.hass = Mock()
        mock_device.set_sensor_enabled.side_effect = Exception("Set sensor failed")

        with patch("custom_components.dali_center.switch._LOGGER") as mock_logger:
            await illuminance_switch.async_turn_off()

            mock_device.set_sensor_enabled.assert_called_once_with(False)
            mock_logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_illuminance_switch_async_added_to_hass(self, illuminance_switch):
        """Test illuminance switch added to hass."""
        mock_hass = Mock()
        mock_dispatcher_connect = Mock()

        with patch(
            "custom_components.dali_center.switch.async_dispatcher_connect",
            mock_dispatcher_connect,
        ):
            illuminance_switch.hass = mock_hass
            await illuminance_switch.async_added_to_hass()

        # Should connect to two dispatcher signals
        assert mock_dispatcher_connect.call_count == 2

    def test_handle_device_update_available(self, illuminance_switch):
        """Test _handle_device_update_available method."""
        illuminance_switch._handle_device_update_available(False)

        assert illuminance_switch._attr_available is False
        # Verify hass.loop.call_soon_threadsafe was called
        illuminance_switch.hass.loop.call_soon_threadsafe.assert_called_once()

    def test_handle_sensor_on_off_enabled(self, illuminance_switch):
        """Test _handle_sensor_on_off_update when sensor is enabled."""
        illuminance_switch._handle_sensor_on_off_update(True)

        assert illuminance_switch._attr_is_on is True
        # Verify hass.loop.call_soon_threadsafe was called
        illuminance_switch.hass.loop.call_soon_threadsafe.assert_called_once()

    def test_handle_sensor_on_off_disabled(self, illuminance_switch):
        """Test _handle_sensor_on_off_update when sensor is disabled."""
        illuminance_switch._handle_sensor_on_off_update(False)

        assert illuminance_switch._attr_is_on is False
        # Verify hass.loop.call_soon_threadsafe was called
        illuminance_switch.hass.loop.call_soon_threadsafe.assert_called_once()

    def test_illuminance_switch_available_when_device_offline(self, illuminance_switch):
        """Test switch availability when device is offline."""
        illuminance_switch._attr_available = False
        assert illuminance_switch.available is False

    def test_illuminance_switch_available_when_device_online(self, illuminance_switch):
        """Test switch availability when device is online."""
        illuminance_switch._attr_available = True
        assert illuminance_switch.available is True

    def test_illuminance_switch_state_persistence(self, illuminance_switch):
        """Test that switch state persists across multiple checks."""
        illuminance_switch._attr_is_on = True
        assert illuminance_switch.is_on is True
        assert illuminance_switch.is_on is True  # Should be consistent

        illuminance_switch._attr_is_on = False
        assert illuminance_switch.is_on is False
        assert illuminance_switch.is_on is False  # Should be consistent

    def test_illuminance_switch_device_info_structure(
        self, illuminance_switch, mock_device
    ):
        """Test device_info structure contains all expected fields."""
        device_info = illuminance_switch.device_info

        assert "identifiers" in device_info
        assert "name" in device_info
        assert "manufacturer" in device_info
        assert "model" in device_info
        assert "via_device" in device_info

        assert device_info["name"] == mock_device.name
        assert device_info["manufacturer"] == "Sunricher"
        assert device_info["via_device"] == (DOMAIN, mock_device.gw_sn)

    @pytest.mark.asyncio
    async def test_illuminance_switch_multiple_turn_operations(
        self, illuminance_switch, mock_device
    ):
        """Test multiple turn on/off operations."""
        # Mock add_job method
        illuminance_switch.hass.add_job = Mock()

        # Turn on
        await illuminance_switch.async_turn_on()
        mock_device.set_sensor_enabled.assert_called_with(True)

        # Turn off
        await illuminance_switch.async_turn_off()
        mock_device.set_sensor_enabled.assert_called_with(False)

        # Turn on again
        await illuminance_switch.async_turn_on()
        mock_device.set_sensor_enabled.assert_called_with(True)

        # Verify call count
        assert mock_device.set_sensor_enabled.call_count == 3
        # Verify add_job was called 3 times for dispatching signals
        assert illuminance_switch.hass.add_job.call_count == 3
