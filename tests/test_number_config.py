"""Tests for device configuration number entities.

Verifies that:
- Power on level and system failure level entities work for all light devices
- CCT coolest/warmest entities are only created for CCT devices (dev_type 0102)
- Generic async_set_native_value constructs correct DeviceParamType for all params
- _create_number_entities returns correct entity count by device type
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from custom_components.dali_center.number import (
    DaliCenterCctCoolestNumber,
    DaliCenterCctWarmestNumber,
    DaliCenterDeviceParameterNumber,
    DaliCenterPowerOnLevelNumber,
    DaliCenterSystemFailureLevelNumber,
    _create_number_entities,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_device(dev_type: str = "0101") -> MagicMock:
    """Create a mock Device object."""
    mock = MagicMock()
    mock.dev_id = "test_dev_001"
    mock.dev_type = dev_type
    mock.name = "Test Light"
    mock.model = "TestModel"
    mock.gw_sn = "GW001"
    mock.address = 1
    mock.channel = 0
    mock.unique_id = "test_unique_001"
    return mock


# ---------------------------------------------------------------------------
# Power On Level entity tests
# ---------------------------------------------------------------------------
class TestPowerOnLevelEntity:
    """Power on level number entity for all light devices."""

    def test_attributes(self) -> None:
        """Entity should have correct name, icon, and range."""
        entity = DaliCenterPowerOnLevelNumber(_make_device())
        assert entity._attr_name == "Power On Level"
        assert entity._attr_icon == "mdi:power-on"
        assert entity._attr_native_min_value == 10
        assert entity._attr_native_max_value == 1000

    def test_read_power_status(self) -> None:
        """Entity should update native_value from DEV_PARAM callback."""
        entity = DaliCenterPowerOnLevelNumber(_make_device())
        entity.hass = MagicMock()

        with patch.object(entity, "schedule_update_ha_state"):
            entity._handle_device_parameters({"power_status": 500})

        assert entity._attr_native_value == 500

    def test_read_missing_power_status(self) -> None:
        """Entity should keep None when power_status is not in params."""
        entity = DaliCenterPowerOnLevelNumber(_make_device())
        entity.hass = MagicMock()

        with patch.object(entity, "schedule_update_ha_state"):
            entity._handle_device_parameters({"fade_time": 5})

        assert entity._attr_native_value is None

    @pytest.mark.asyncio
    async def test_set_power_status(self) -> None:
        """Setting value should call set_device_parameters with correct key."""
        device = _make_device()
        entity = DaliCenterPowerOnLevelNumber(device)
        entity.hass = MagicMock()

        await entity.async_set_native_value(800)

        device.set_device_parameters.assert_called_once_with({"power_status": 800})
        device.get_device_parameters.assert_called_once()


# ---------------------------------------------------------------------------
# System Failure Level entity tests
# ---------------------------------------------------------------------------
class TestSystemFailureLevelEntity:
    """System failure level number entity for all light devices."""

    def test_attributes(self) -> None:
        """Entity should have correct name, icon, and range."""
        entity = DaliCenterSystemFailureLevelNumber(_make_device())
        assert entity._attr_name == "System Failure Level"
        assert entity._attr_icon == "mdi:alert-outline"
        assert entity._attr_native_min_value == 0
        assert entity._attr_native_max_value == 254

    def test_read_system_failure_status(self) -> None:
        """Entity should update native_value from DEV_PARAM callback."""
        entity = DaliCenterSystemFailureLevelNumber(_make_device())
        entity.hass = MagicMock()

        with patch.object(entity, "schedule_update_ha_state"):
            entity._handle_device_parameters({"system_failure_status": 100})

        assert entity._attr_native_value == 100

    @pytest.mark.asyncio
    async def test_set_system_failure_status(self) -> None:
        """Setting value should call set_device_parameters with correct key."""
        device = _make_device()
        entity = DaliCenterSystemFailureLevelNumber(device)
        entity.hass = MagicMock()

        await entity.async_set_native_value(0)

        device.set_device_parameters.assert_called_once_with(
            {"system_failure_status": 0}
        )


# ---------------------------------------------------------------------------
# CCT entity device type filtering
# ---------------------------------------------------------------------------
class TestCctEntityDeviceTypeFiltering:
    """CCT entities should only be created for dev_type 0102."""

    def test_cct_entities_created_for_0102(self) -> None:
        """CCT device should produce 8 number entities."""
        device = _make_device(dev_type="0102")
        entities = _create_number_entities(device)
        assert len(entities) == 8

        cct_entities = [
            e
            for e in entities
            if isinstance(e, DaliCenterCctCoolestNumber | DaliCenterCctWarmestNumber)
        ]
        assert len(cct_entities) == 2

    def test_cct_entities_not_created_for_0101(self) -> None:
        """Non-CCT device should produce 6 number entities."""
        device = _make_device(dev_type="0101")
        entities = _create_number_entities(device)
        assert len(entities) == 6

        cct_entities = [
            e
            for e in entities
            if isinstance(e, DaliCenterCctCoolestNumber | DaliCenterCctWarmestNumber)
        ]
        assert len(cct_entities) == 0

    def test_cct_entities_not_created_for_0103(self) -> None:
        """RGB device should produce 6 number entities."""
        device = _make_device(dev_type="0103")
        entities = _create_number_entities(device)
        assert len(entities) == 6

    def test_cct_coolest_attributes(self) -> None:
        """CCT Coolest entity should have correct range."""
        entity = DaliCenterCctCoolestNumber(_make_device(dev_type="0102"))
        assert entity._attr_native_min_value == 1000
        assert entity._attr_native_max_value == 10000
        assert entity._attr_icon == "mdi:thermometer-low"

    def test_cct_warmest_attributes(self) -> None:
        """CCT Warmest entity should have correct range."""
        entity = DaliCenterCctWarmestNumber(_make_device(dev_type="0102"))
        assert entity._attr_native_min_value == 1000
        assert entity._attr_native_max_value == 10000
        assert entity._attr_icon == "mdi:thermometer-high"


# ---------------------------------------------------------------------------
# Generic async_set_native_value tests
# ---------------------------------------------------------------------------
class TestGenericAsyncSetNativeValue:
    """Generic async_set_native_value should construct correct DeviceParamType."""

    @pytest.mark.asyncio
    async def test_all_parameters_construct_correct_dict(self) -> None:
        """Each subclass should send {parameter_name: value} to the device."""
        test_cases: list[tuple[type[DaliCenterDeviceParameterNumber], str, int]] = [
            (DaliCenterPowerOnLevelNumber, "power_status", 500),
            (DaliCenterSystemFailureLevelNumber, "system_failure_status", 127),
            (DaliCenterCctCoolestNumber, "cct_cool", 6500),
            (DaliCenterCctWarmestNumber, "cct_warm", 2700),
        ]

        for entity_cls, param_name, value in test_cases:
            device = _make_device(dev_type="0102")
            entity = entity_cls(device)
            entity.hass = MagicMock()

            await entity.async_set_native_value(value)

            device.set_device_parameters.assert_called_once_with({param_name: value})
            device.get_device_parameters.assert_called_once()
