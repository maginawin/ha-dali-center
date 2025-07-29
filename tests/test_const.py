"""Test the constants for Dali Center integration."""
from custom_components.dali_center.const import DOMAIN, MANUFACTURER


def test_domain_constant():
    """Test that the DOMAIN constant is correctly defined."""
    assert DOMAIN == "dali_center"
    assert isinstance(DOMAIN, str)


def test_manufacturer_constant():
    """Test that the MANUFACTURER constant is correctly defined."""
    assert MANUFACTURER == "Sunricher"
    assert isinstance(MANUFACTURER, str)
