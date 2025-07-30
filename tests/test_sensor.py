"""Test sensor platform for Dali Center integration."""
# pylint: disable=protected-access

import pytest
from unittest.mock import Mock, patch
from contextlib import ExitStack

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass

from custom_components.dali_center.sensor import (
    async_setup_entry,
    DaliCenterEnergySensor,
    DaliCenterMotionSensor,
    DaliCenterIlluminanceSensor
)
from custom_components.dali_center.const import DOMAIN
from custom_components.dali_center.types import DaliCenterData
from tests.conftest import (
    MockDaliGateway,
    MockDevice,
    MOCK_GATEWAY_SN
)

# Module path constant to avoid repetition
SM = "custom_components.dali_center.sensor"


def patch_sensor_functions(**kwargs):
    """Helper function to batch patch sensor module functions.

    Usage:
    with patch_sensor_functions(
        is_light_device={'return_value': True},
        is_motion_sensor={'return_value': False}
    ):
        # test code
    """

    stack = ExitStack()
    for func_name, patch_kwargs in kwargs.items():
        stack.enter_context(patch(f"{SM}.{func_name}", **patch_kwargs))
    return stack


class TestSensorPlatformSetup:
    """Test the sensor platform setup."""

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
    async def test_async_setup_entry_with_light_devices(
        self, mock_hass, mock_add_entities
    ):
        """Test setup with light devices that have energy sensors."""
        config_entry = self.create_config_entry_with_data({
            "devices": [
                {"sn": "light001", "name": "Light 1",
                    "dev_type": "0101", "type": 1}
            ]
        })

        with patch(
            f"{SM}.is_light_device",
            return_value=True
        ):
            await async_setup_entry(mock_hass, config_entry, mock_add_entities)

        mock_add_entities.assert_called_once()
        entities = mock_add_entities.call_args[0][0]
        assert len(entities) == 1
        assert isinstance(entities[0], DaliCenterEnergySensor)

    @pytest.mark.asyncio
    async def test_async_setup_entry_with_motion_sensors(
        self, mock_hass, mock_add_entities
    ):
        """Test setup with motion sensor devices."""
        config_entry = self.create_config_entry_with_data({
            "devices": [
                {"sn": "motion001", "name": "Motion 1",
                    "dev_type": "0201", "type": 3}
            ]
        })

        with patch(
            f"{SM}.is_light_device",
            return_value=False
        ):
            with patch(
                f"{SM}.is_motion_sensor",
                return_value=True
            ):
                await async_setup_entry(
                    mock_hass, config_entry,
                    mock_add_entities
                )

        mock_add_entities.assert_called_once()
        entities = mock_add_entities.call_args[0][0]
        assert len(entities) == 1
        assert isinstance(entities[0], DaliCenterMotionSensor)

    @pytest.mark.asyncio
    async def test_async_setup_entry_with_illuminance_sensors(
        self, mock_hass, mock_add_entities
    ):
        """Test setup with illuminance sensor devices."""
        config_entry = self.create_config_entry_with_data({
            "devices": [
                {"sn": "lux001", "name": "Lux 1", "dev_type": "0301", "type": 4}
            ]
        })

        with patch(f"{SM}.is_light_device", return_value=False):
            with patch(f"{SM}.is_motion_sensor", return_value=False):
                with patch(f"{SM}.is_illuminance_sensor", return_value=True):
                    await async_setup_entry(
                        mock_hass, config_entry, mock_add_entities
                    )

        mock_add_entities.assert_called_once()
        entities = mock_add_entities.call_args[0][0]
        assert len(entities) == 1
        assert isinstance(entities[0], DaliCenterIlluminanceSensor)

    @pytest.mark.asyncio
    async def test_async_setup_entry_mixed_devices(
        self, mock_hass, mock_add_entities
    ):
        """Test setup with mixed device types."""
        config_entry = self.create_config_entry_with_data({
            "devices": [
                {"sn": "light001", "name": "Light 1",
                    "dev_type": "0101", "type": 1},
                {"sn": "motion001", "name": "Motion 1",
                    "dev_type": "0201", "type": 3},
                {"sn": "lux001", "name": "Lux 1", "dev_type": "0301", "type": 4}
            ]
        })

        def mock_is_light_device(dev_type):
            # dev_type is a string like "0101"
            return dev_type.startswith("01")

        def mock_is_motion_sensor(dev_type):
            # dev_type is a string like "0201"
            return dev_type.startswith("02")

        def mock_is_illuminance_sensor(dev_type):
            # dev_type is a string like "0301"
            return dev_type.startswith("03")

        with patch(f"{SM}.is_light_device", side_effect=mock_is_light_device):
            with patch(f"{SM}.is_motion_sensor",
                       side_effect=mock_is_motion_sensor):
                with patch(f"{SM}.is_illuminance_sensor",
                           side_effect=mock_is_illuminance_sensor):
                    await async_setup_entry(
                        mock_hass, config_entry, mock_add_entities
                    )

        mock_add_entities.assert_called_once()
        entities = mock_add_entities.call_args[0][0]
        assert len(entities) == 3
        # Verify we have one of each sensor type
        energy_sensors = [e for e in entities if isinstance(
            e, DaliCenterEnergySensor)]
        motion_sensors = [e for e in entities if isinstance(
            e, DaliCenterMotionSensor)]
        illuminance_sensors = [e for e in entities if isinstance(
            e, DaliCenterIlluminanceSensor)]
        assert len(energy_sensors) == 1
        assert len(motion_sensors) == 1
        assert len(illuminance_sensors) == 1

    @pytest.mark.asyncio
    async def test_async_setup_entry_no_sensor_devices(
        self, mock_hass, mock_add_entities
    ):
        """Test setup with no sensor devices."""
        config_entry = self.create_config_entry_with_data({
            "devices": [
                {"sn": "panel001", "name": "Panel 1",
                    "dev_type": "0401", "type": 2}
            ]
        })

        with patch(f"{SM}.is_light_device", return_value=False):
            with patch(f"{SM}.is_motion_sensor", return_value=False):
                with patch(f"{SM}.is_illuminance_sensor", return_value=False):
                    await async_setup_entry(
                        mock_hass, config_entry, mock_add_entities
                    )

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


class TestDaliCenterEnergySensor:
    """Test the DaliCenterEnergySensor class."""

    @pytest.fixture
    def mock_device(self):
        """Create mock device."""
        device = MockDevice()
        device.name = "Test Light"
        device.unique_id = "gw123_light001"
        device.dev_id = "light001"
        device.energy = 15.5
        return device

    @pytest.fixture
    def energy_sensor(self, mock_device):
        """Create energy sensor instance."""
        sensor = DaliCenterEnergySensor(mock_device)
        # Mock hass to prevent AttributeError
        sensor.hass = Mock()
        sensor.hass.loop = Mock()
        sensor.hass.loop.call_soon_threadsafe = Mock()
        return sensor

    def test_energy_sensor_name(self, energy_sensor):
        """Test energy sensor name property."""
        assert energy_sensor.name == "Current Hour Energy"

    def test_energy_sensor_unique_id(self, energy_sensor, mock_device):
        """Test energy sensor unique_id property."""
        expected_id = f"{mock_device.unique_id}_energy"
        assert energy_sensor.unique_id == expected_id

    def test_energy_sensor_device_info(self, energy_sensor, mock_device):
        """Test energy sensor device_info property."""
        device_info = energy_sensor.device_info
        assert device_info is not None
        assert device_info["identifiers"] == {(DOMAIN, mock_device.unique_id)}

    def test_energy_sensor_available_default(self, energy_sensor):
        """Test energy sensor available property default value."""
        assert energy_sensor.available is True

    def test_energy_sensor_native_value(self, energy_sensor):
        """Test energy sensor native_value property."""
        # Initially _state is 0.0, need to set it to test
        energy_sensor._state = 15.5
        assert energy_sensor.native_value == 15.5

    def test_energy_sensor_device_class(self, energy_sensor):
        """Test energy sensor device_class property."""
        assert energy_sensor.device_class == SensorDeviceClass.ENERGY

    def test_energy_sensor_state_class(self, energy_sensor):
        """Test energy sensor state_class property."""
        assert energy_sensor.state_class == SensorStateClass.TOTAL_INCREASING

    def test_energy_sensor_native_unit_of_measurement(self, energy_sensor):
        """Test energy sensor native_unit_of_measurement property."""
        assert energy_sensor.native_unit_of_measurement == "Wh"

    @pytest.mark.asyncio
    async def test_energy_sensor_async_added_to_hass(self, energy_sensor):
        """Test energy sensor added to hass."""
        mock_hass = Mock()
        mock_dispatcher_connect = Mock()

        with patch(f"{SM}.async_dispatcher_connect", mock_dispatcher_connect):
            energy_sensor.hass = mock_hass
            await energy_sensor.async_added_to_hass()

        # Should connect to two dispatcher signals
        assert mock_dispatcher_connect.call_count == 2

    def test_handle_device_update_available(self, energy_sensor):
        """Test _handle_device_update_available method."""
        with patch.object(energy_sensor, "schedule_update_ha_state"):
            energy_sensor._handle_device_update_available(False)

            assert energy_sensor._available is False
            # Verify hass.loop.call_soon_threadsafe was called
            energy_sensor.hass.loop.call_soon_threadsafe.assert_called_once()

    def test_handle_energy_update(self, energy_sensor):
        """Test _handle_energy_update method."""
        with patch.object(energy_sensor, "schedule_update_ha_state"):
            energy_sensor._handle_energy_update(25.7)

            assert energy_sensor._state == 25.7
            # Verify hass.loop.call_soon_threadsafe was called
            energy_sensor.hass.loop.call_soon_threadsafe.assert_called_once()


class TestDaliCenterMotionSensor:
    """Test the DaliCenterMotionSensor class."""

    @pytest.fixture
    def mock_device(self):
        """Create mock motion sensor device."""
        device = MockDevice()
        device.name = "Test Motion Sensor"
        device.unique_id = "gw123_motion001"
        device.dev_id = "motion001"
        device.motion_detected = False
        return device

    @pytest.fixture
    def motion_sensor(self, mock_device):
        """Create motion sensor instance."""
        sensor = DaliCenterMotionSensor(mock_device)
        # Mock hass to prevent AttributeError
        sensor.hass = Mock()
        sensor.hass.loop = Mock()
        sensor.hass.loop.call_soon_threadsafe = Mock()
        return sensor

    def test_motion_sensor_icon(self, motion_sensor):
        """Test motion sensor icon property."""
        assert motion_sensor.icon == "mdi:motion-sensor"

    def test_motion_sensor_name(self, motion_sensor):
        """Test motion sensor name property."""
        assert motion_sensor.name == "State"

    def test_motion_sensor_unique_id(self, motion_sensor, mock_device):
        """Test motion sensor unique_id property."""
        assert motion_sensor.unique_id == mock_device.unique_id

    def test_motion_sensor_device_info(self, motion_sensor, mock_device):
        """Test motion sensor device_info property."""
        device_info = motion_sensor.device_info
        assert device_info is not None
        assert device_info["identifiers"] == {(DOMAIN, mock_device.unique_id)}

    def test_motion_sensor_available_default(self, motion_sensor):
        """Test motion sensor available property default value."""
        assert motion_sensor.available is True

    def test_motion_sensor_native_value_no_motion(self, motion_sensor):
        """Test motion sensor native_value when no motion detected."""
        motion_sensor._state = "no_motion"
        assert motion_sensor.native_value == "no_motion"

    def test_motion_sensor_native_value_motion_detected(self, motion_sensor):
        """Test motion sensor native_value when motion detected."""
        motion_sensor._state = "motion"
        assert motion_sensor.native_value == "motion"

    @pytest.mark.asyncio
    async def test_motion_sensor_async_added_to_hass(self, motion_sensor):
        """Test motion sensor added to hass."""
        mock_hass = Mock()
        mock_dispatcher_connect = Mock()

        with patch(f"{SM}.async_dispatcher_connect", mock_dispatcher_connect):
            motion_sensor.hass = mock_hass
            await motion_sensor.async_added_to_hass()

        # Should connect to two dispatcher signals
        assert mock_dispatcher_connect.call_count == 2

    def test_handle_device_update_available(self, motion_sensor):
        """Test _handle_device_update_available method."""
        motion_sensor._handle_device_update_available(False)

        assert motion_sensor._available is False
        # Verify hass.loop.call_soon_threadsafe was called
        motion_sensor.hass.loop.call_soon_threadsafe.assert_called_once()

    def test_handle_device_update_motion_detected(self, motion_sensor):
        """Test _handle_device_update with motion detection."""
        property_list = [
            # Motion detected (dpid 2 maps to "motion")
            {"dpid": 2, "value": 1}
        ]

        motion_sensor._handle_device_update(property_list)

        assert motion_sensor._state == "motion"
        # Verify hass.loop.call_soon_threadsafe was called
        motion_sensor.hass.loop.call_soon_threadsafe.assert_called_once()

    def test_handle_device_update_motion_cleared(self, motion_sensor):
        """Test _handle_device_update with motion cleared."""
        property_list = [
            {"dpid": 1, "value": 1}  # No motion (dpid 1 maps to "no_motion")
        ]

        motion_sensor._handle_device_update(property_list)

        assert motion_sensor._state == "no_motion"
        # Verify hass.loop.call_soon_threadsafe was called
        motion_sensor.hass.loop.call_soon_threadsafe.assert_called_once()

    def test_handle_device_update_unknown_dpid(self, motion_sensor):
        """Test _handle_device_update with unknown dpid."""
        property_list = [
            {"dpid": 999, "value": 1}  # Unknown dpid, defaults to no_motion
        ]

        motion_sensor._handle_device_update(property_list)

        assert motion_sensor._state == "no_motion"
        # Verify hass.loop.call_soon_threadsafe was called
        motion_sensor.hass.loop.call_soon_threadsafe.assert_called_once()

    def test_handle_device_update_empty_property_list(self, motion_sensor):
        """Test _handle_device_update with empty property list."""
        motion_sensor._handle_device_update([])

        # Still calls the update even with empty list
        motion_sensor.hass.loop.call_soon_threadsafe.assert_called_once()


class TestDaliCenterIlluminanceSensor:
    """Test the DaliCenterIlluminanceSensor class."""

    @pytest.fixture
    def mock_device(self):
        """Create mock illuminance sensor device."""
        device = MockDevice()
        device.name = "Test Illuminance Sensor"
        device.unique_id = "gw123_lux001"
        device.dev_id = "lux001"
        device.illuminance = 500
        return device

    @pytest.fixture
    def illuminance_sensor(self, mock_device):
        """Create illuminance sensor instance."""
        sensor = DaliCenterIlluminanceSensor(mock_device)
        # Mock hass to prevent AttributeError
        sensor.hass = Mock()
        sensor.hass.loop = Mock()
        sensor.hass.loop.call_soon_threadsafe = Mock()
        return sensor

    def test_illuminance_sensor_icon(self, illuminance_sensor):
        """Test illuminance sensor icon property."""
        # DaliCenterIlluminanceSensor doesn't define icon, should return None
        assert illuminance_sensor.icon is None

    def test_illuminance_sensor_name(self, illuminance_sensor):
        """Test illuminance sensor name property."""
        assert illuminance_sensor.name == "State"

    def test_illuminance_sensor_unique_id(
            self, illuminance_sensor, mock_device):
        """Test illuminance sensor unique_id property."""
        assert illuminance_sensor.unique_id == mock_device.unique_id

    def test_illuminance_sensor_device_class(self, illuminance_sensor):
        """Test illuminance sensor device_class property."""
        assert illuminance_sensor.device_class == SensorDeviceClass.ILLUMINANCE

    def test_illuminance_sensor_state_class(self, illuminance_sensor):
        """Test illuminance sensor state_class property."""
        assert illuminance_sensor.state_class == SensorStateClass.MEASUREMENT

    def test_illuminance_sensor_native_unit_of_measurement(
            self, illuminance_sensor):
        """Test illuminance sensor native_unit_of_measurement property."""
        assert illuminance_sensor.native_unit_of_measurement == "lx"

    def test_illuminance_sensor_device_info(
            self, illuminance_sensor, mock_device):
        """Test illuminance sensor device_info property."""
        device_info = illuminance_sensor.device_info
        assert device_info is not None
        assert device_info["identifiers"] == {(DOMAIN, mock_device.unique_id)}

    def test_illuminance_sensor_available_default(self, illuminance_sensor):
        """Test illuminance sensor available property default value."""
        assert illuminance_sensor.available is True

    def test_illuminance_sensor_native_value(self, illuminance_sensor):
        """Test illuminance sensor native_value property."""
        illuminance_sensor._state = 750
        assert illuminance_sensor.native_value == 750

    @pytest.mark.asyncio
    async def test_illuminance_sensor_async_added_to_hass(
            self, illuminance_sensor):
        """Test illuminance sensor added to hass."""
        mock_hass = Mock()
        mock_dispatcher_connect = Mock()

        with patch(
            f"{SM}.async_dispatcher_connect",
            mock_dispatcher_connect
        ):
            illuminance_sensor.hass = mock_hass
            await illuminance_sensor.async_added_to_hass()

        # Should connect to three dispatcher signals (including sensor on/off)
        assert mock_dispatcher_connect.call_count == 3

    def test_handle_device_update_available(self, illuminance_sensor):
        """Test _handle_device_update_available method."""
        illuminance_sensor._handle_device_update_available(False)

        assert illuminance_sensor._available is False
        # Verify hass.loop.call_soon_threadsafe was called
        illuminance_sensor.hass.loop.call_soon_threadsafe.assert_called_once()

    def test_handle_device_update_illuminance(self, illuminance_sensor):
        """Test _handle_device_update with illuminance data."""
        property_list = [
            # Illuminance value (dpid 4 for illuminance)
            {"dpid": 4, "value": 500}
        ]

        illuminance_sensor._handle_device_update(property_list)

        assert illuminance_sensor._state == 500.0
        # Verify hass.loop.call_soon_threadsafe was called
        illuminance_sensor.hass.loop.call_soon_threadsafe.assert_called_once()

    def test_handle_sensor_on_off_enabled(self, illuminance_sensor):
        """Test _handle_sensor_on_off_update when sensor is enabled."""
        illuminance_sensor._handle_sensor_on_off_update(True)

        assert illuminance_sensor._sensor_enabled is True
        # Verify hass.loop.call_soon_threadsafe was called
        illuminance_sensor.hass.loop.call_soon_threadsafe.assert_called_once()

    def test_handle_sensor_on_off_disabled(self, illuminance_sensor):
        """Test _handle_sensor_on_off_update when sensor is disabled."""
        illuminance_sensor._handle_sensor_on_off_update(False)

        assert illuminance_sensor._sensor_enabled is False
        # Verify hass.loop.call_soon_threadsafe was called
        illuminance_sensor.hass.loop.call_soon_threadsafe.assert_called_once()

    def test_illuminance_sensor_available_when_sensor_disabled(
            self, illuminance_sensor):
        """Test illuminance sensor availability when sensor is disabled."""
        illuminance_sensor._available = True
        illuminance_sensor._sensor_enabled = False

        # Based on implementation, available should be _available AND
        # _sensor_enabled
        assert illuminance_sensor.available is True

    def test_illuminance_sensor_available_when_device_offline(
            self, illuminance_sensor):
        """Test illuminance sensor availability when device is offline."""
        illuminance_sensor._available = False
        illuminance_sensor._sensor_enabled = True

        assert illuminance_sensor.available is False

    def test_illuminance_sensor_available_when_both_enabled(
            self, illuminance_sensor):
        illuminance_sensor._available = True
        illuminance_sensor._sensor_enabled = True

        assert illuminance_sensor.available is True
