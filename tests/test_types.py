"""Test type definitions for Dali Center integration."""
# pylint: disable=protected-access

from custom_components.dali_center.types import ConfigData, DaliCenterData
from tests.conftest import MockDaliGateway, MOCK_GATEWAY_SN


def test_config_data_structure():
    """Test ConfigData TypedDict structure."""
    # Test that ConfigData can be created with all fields
    config_data: ConfigData = {
        "sn": MOCK_GATEWAY_SN,
        "gateway": MockDaliGateway(),
        "devices": [],
        "groups": [],
        "scenes": [],
    }

    assert config_data["sn"] == MOCK_GATEWAY_SN
    assert isinstance(config_data["gateway"], MockDaliGateway)
    assert isinstance(config_data["devices"], list)
    assert isinstance(config_data["groups"], list)
    assert isinstance(config_data["scenes"], list)


def test_config_data_partial():
    """Test ConfigData TypedDict with partial data (total=False)."""
    # Test that ConfigData can be created with only some fields
    config_data: ConfigData = {
        "sn": MOCK_GATEWAY_SN,
    }

    assert config_data["sn"] == MOCK_GATEWAY_SN
    assert "gateway" not in config_data
    assert "devices" not in config_data


def test_dali_center_data_structure():
    """Test DaliCenterData dataclass structure."""
    gateway = MockDaliGateway()
    data = DaliCenterData(gateway=gateway)

    assert data.gateway is gateway
    assert isinstance(data.gateway, MockDaliGateway)


def test_dali_center_data_attributes():
    """Test DaliCenterData dataclass attributes."""
    gateway = MockDaliGateway()
    data = DaliCenterData(gateway=gateway)

    # Test that we can access gateway attributes through the data object
    assert data.gateway.sn == MOCK_GATEWAY_SN
    assert data.gateway.connected is False
