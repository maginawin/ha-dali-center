"""Pytest configuration and fixtures for Dali Center integration tests."""

from __future__ import annotations

import pytest
from unittest.mock import patch
from homeassistant.config_entries import ConfigEntry

from custom_components.dali_center.const import DOMAIN


# Mock data for testing
MOCK_GATEWAY_SN = "DALI123456"
MOCK_GATEWAY_IP = "192.168.1.100"

MOCK_DEVICE_DATA = {
    "sn": "001",
    "name": "Test Light",
    "type": 1,  # Light device type
    "brightness": 100,
    "power": True,
    "energy": 10.5,
}

MOCK_GROUP_DATA = {
    "sn": "group001",
    "name": "Living Room",
    "type": 1,
    "brightness": 80,
    "power": True,
}

MOCK_SCENE_DATA = {
    "sn": "scene001",
    "name": "Evening",
    "type": 1,
}


class MockDevice:
    """Mock Device class for testing."""

    def __init__(self, data: dict | None = None):
        data = data or MOCK_DEVICE_DATA
        self.sn = data.get("sn", "001")
        self.name = data.get("name", "Test Device")
        self.type = data.get("type", 1)
        self.dev_type = data.get("type", 1)  # Add dev_type for compatibility
        self.brightness = data.get("brightness", 100)
        self.power = data.get("power", True)
        self.energy = data.get("energy", 0.0)
        self.status = "online"
        self.unique_id = f"{self.sn}_device"
        self.dev_id = self.sn
        # Add light-specific attributes
        self.color_mode = "brightness"
        self.brightness_range = (0, 100)
        self.color_temp_range = None
        self.features = []
        self.gw_sn = MOCK_GATEWAY_SN  # Add gateway serial number

    def turn_on(self, **kwargs):
        """Mock turn_on method."""
        self.power = True
        if "brightness" in kwargs:
            self.brightness = kwargs["brightness"]

    def turn_off(self):
        """Mock turn_off method."""
        self.power = False


class MockGroup:
    """Mock Group class for testing."""

    def __init__(self, data: dict | None = None):
        data = data or MOCK_GROUP_DATA
        self.sn = data.get("sn", "group001")
        self.name = data.get("name", "Test Group")
        self.type = data.get("type", 1)
        self.brightness = data.get("brightness", 100)
        self.power = data.get("power", True)
        self.group_id = self.sn
        self.status = "online"


class MockScene:
    """Mock Scene class for testing."""

    def __init__(self, data: dict | None = None):
        data = data or MOCK_SCENE_DATA
        self.sn = data.get("sn", "scene001")
        self.name = data.get("name", "Test Scene")
        self.type = data.get("type", 1)


class MockDaliGateway:
    """Mock DaliGateway class for testing."""

    def __init__(self, gateway_data: dict | str = MOCK_GATEWAY_SN):
        if isinstance(gateway_data, str):
            self.sn = gateway_data
            self.gw_sn = gateway_data
            self.ip = MOCK_GATEWAY_IP
        else:
            self.sn = gateway_data.get("gw_sn", MOCK_GATEWAY_SN)
            self.gw_sn = gateway_data.get("gw_sn", MOCK_GATEWAY_SN)
            self.ip = gateway_data.get("ip", MOCK_GATEWAY_IP)

        self.connected = False
        self.devices = [MockDevice()]
        self.groups = [MockGroup()]
        self.scenes = [MockScene()]

    async def connect(self) -> bool:
        """Mock connect method."""
        self.connected = True
        return True

    async def disconnect(self) -> None:
        """Mock disconnect method."""
        self.connected = False

    async def get_devices(self) -> list[MockDevice]:
        """Mock get_devices method."""
        return self.devices

    async def get_groups(self) -> list[MockGroup]:
        """Mock get_groups method."""
        return self.groups

    async def get_scenes(self) -> list[MockScene]:
        """Mock get_scenes method."""
        return self.scenes

    async def discover_devices(self) -> list[MockDevice]:
        """Mock discover_devices method."""
        return self.devices

    async def discover_groups(self) -> list[MockGroup]:
        """Mock discover_groups method."""
        return self.groups

    async def discover_scenes(self) -> list[MockScene]:
        """Mock discover_scenes method."""
        return self.scenes

    def to_dict(self) -> dict:
        """Mock to_dict method."""
        return {
            "gw_sn": self.gw_sn,
            "ip": self.ip,
            "name": f"Gateway {self.gw_sn}"
        }

    async def write_device(self, device_sn: str, **kwargs) -> None:
        """Mock write_device method."""
        # Update the device state based on the write command
        for device in self.devices:
            if device.sn == device_sn:
                for key, value in kwargs.items():
                    setattr(device, key, value)
                break


class MockDaliGatewayDiscovery:
    """Mock DaliGatewayDiscovery class for testing."""

    @staticmethod
    async def discover() -> list[dict]:
        """Mock discover method."""
        return [{
            "sn": MOCK_GATEWAY_SN,
            "ip": MOCK_GATEWAY_IP,
            "name": "Test Gateway"
        }]

    async def discover_gateways(self) -> list[dict]:
        """Mock discover_gateways method."""
        return [{
            "gw_sn": MOCK_GATEWAY_SN,
            "ip": MOCK_GATEWAY_IP,
            "name": "Test Gateway"
        }]


# Mock helper functions
def mock_is_light_device(dev_type: int) -> bool:
    """Mock is_light_device helper function."""
    return dev_type == 1


def mock_is_panel_device(device: MockDevice) -> bool:
    """Mock is_panel_device helper function."""
    return device.type == 2


def mock_is_motion_sensor(device: MockDevice) -> bool:
    """Mock is_motion_sensor helper function."""
    return device.type == 3


def mock_is_illuminance_sensor(device: MockDevice) -> bool:
    """Mock is_illuminance_sensor helper function."""
    return device.type == 4


# Mock constants
MOCK_BUTTON_EVENTS = ["press", "double_press", "long_press"]


@pytest.fixture(autouse=True)
def mock_pysrdaligateway():
    """Auto-use fixture to mock PySrDaliGateway library."""
    with patch.multiple(
        "custom_components.dali_center.config_flow",
        DaliGateway=MockDaliGateway,
        DaliGatewayDiscovery=MockDaliGatewayDiscovery,
    ), patch.multiple(
        "custom_components.dali_center.__init__",
        DaliGateway=MockDaliGateway,
    ), patch.multiple(
        "custom_components.dali_center.light",
        DaliGateway=MockDaliGateway,
        Device=lambda gateway, device_data: MockDevice(device_data),
        Group=lambda gateway, group_data: MockGroup(group_data),
        is_light_device=mock_is_light_device,
    ), patch.multiple(
        "custom_components.dali_center.sensor",
        DaliGateway=MockDaliGateway,
        Device=MockDevice,
        is_light_device=mock_is_light_device,
        is_motion_sensor=mock_is_motion_sensor,
        is_illuminance_sensor=mock_is_illuminance_sensor,
    ), patch.multiple(
        "custom_components.dali_center.button",
        DaliGateway=MockDaliGateway,
        Scene=MockScene,
        Device=MockDevice,
        is_panel_device=mock_is_panel_device,
    ), patch.multiple(
        "custom_components.dali_center.event",
        DaliGateway=MockDaliGateway,
        Device=MockDevice,
        is_panel_device=mock_is_panel_device,
    ), patch.multiple(
        "custom_components.dali_center.switch",
        DaliGateway=MockDaliGateway,
        Device=MockDevice,
        is_illuminance_sensor=mock_is_illuminance_sensor,
    ), patch(
        "custom_components.dali_center.event.BUTTON_EVENTS",
        MOCK_BUTTON_EVENTS,
    ):
        yield


@pytest.fixture
def mock_config_entry():
    """Create a mock config entry for testing."""
    return ConfigEntry(
        version=1,
        minor_version=1,
        domain=DOMAIN,
        title="Test Gateway",
        data={
            "sn": MOCK_GATEWAY_SN,
            "devices": [
                {"sn": "light001", "name": "Test Light", "type": 1}
            ],
            "groups": [
                {"sn": "group001", "name": "Test Group", "type": 1}
            ]
        },
        source="user",
        entry_id="test_entry_id",
        unique_id=MOCK_GATEWAY_SN,
        options={},
        discovery_keys={},
        subentries_data=None,
    )


@pytest.fixture
def mock_dali_gateway():
    """Create a mock DaliGateway instance."""
    return MockDaliGateway()


@pytest.fixture
def mock_device():
    """Create a mock Device instance."""
    return MockDevice()


@pytest.fixture
def mock_group():
    """Create a mock Group instance."""
    return MockGroup()


@pytest.fixture
def mock_scene():
    """Create a mock Scene instance."""
    return MockScene()
