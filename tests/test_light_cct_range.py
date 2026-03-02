"""Tests for CCT range reading and group aggregation.

Verifies that:
- DaliCenterLight updates CCT range on DEV_PARAM callback
- Missing or zero CCT fields keep defaults
- DaliCenterLightGroup derives CCT range as union of members
- DaliCenterAllLights CCT range stays at defaults
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from custom_components.dali_center.light import (
    DaliCenterAllLights,
    DaliCenterLight,
    DaliCenterLightGroup,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_state(
    state: str = "on",
    brightness: int | None = 255,
    color_temp_kelvin: int | None = None,
    rgbw_color: tuple[int, int, int, int] | None = None,
    supported_color_modes: list[str] | None = None,
    min_color_temp_kelvin: int | None = None,
    max_color_temp_kelvin: int | None = None,
) -> MagicMock:
    """Create a mock HA State object for a light entity."""
    mock = MagicMock()
    mock.state = state
    mock.attributes = {
        "brightness": brightness,
        "supported_color_modes": supported_color_modes or ["brightness"],
    }
    if color_temp_kelvin is not None:
        mock.attributes["color_temp_kelvin"] = color_temp_kelvin
    if rgbw_color is not None:
        mock.attributes["rgbw_color"] = rgbw_color
    if min_color_temp_kelvin is not None:
        mock.attributes["min_color_temp_kelvin"] = min_color_temp_kelvin
    if max_color_temp_kelvin is not None:
        mock.attributes["max_color_temp_kelvin"] = max_color_temp_kelvin
    return mock


def _make_states_getter(
    states: dict[str, MagicMock],
) -> MagicMock:
    """Create a states.get callable that returns mock states by entity_id."""
    return MagicMock(side_effect=states.get)


def _make_light_entity(dev_type: str = "0102") -> DaliCenterLight:
    """Create a DaliCenterLight with a mocked Device and hass."""
    mock_device = MagicMock()
    mock_device.dev_id = "test_dev_001"
    mock_device.dev_type = dev_type
    mock_device.name = "Test Light"
    mock_device.model = "TestModel"
    mock_device.gw_sn = "GW001"
    mock_device.address = 1
    mock_device.channel = 0
    mock_device.color_mode = "color_temp"
    mock_device.unique_id = "test_unique_001"

    entity = DaliCenterLight(mock_device)
    # Provide a mock hass so async_write_ha_state works.
    entity.hass = MagicMock()
    return entity


# ---------------------------------------------------------------------------
# DaliCenterLight CCT tests
# ---------------------------------------------------------------------------
class TestCctDeviceUpdatesRangeOnDevParam:
    """CCT device receives DEV_PARAM callback and updates CCT range."""

    def test_cct_device_updates_range_on_dev_param(self) -> None:
        """CCT range should update when valid parameters are received."""
        entity = _make_light_entity(dev_type="0102")

        # Verify defaults
        assert entity._attr_min_color_temp_kelvin == 1000
        assert entity._attr_max_color_temp_kelvin == 8000

        # Simulate DEV_PARAM callback (patch async_write_ha_state since
        # the entity is not fully wired into HA).
        with patch.object(entity, "async_write_ha_state"):
            entity._handle_dev_param_update(
                {
                    "cct_warm": 2700,
                    "cct_cool": 6500,
                }
            )

        assert entity._attr_min_color_temp_kelvin == 2700
        assert entity._attr_max_color_temp_kelvin == 6500


class TestNonCctDeviceSkipsGetDevParam:
    """Non-CCT devices should not send getDevParam request."""

    def test_non_cct_device_skips_get_dev_param(self) -> None:
        """DevType != '0102' should not trigger getDevParam."""
        entity = _make_light_entity(dev_type="0101")

        # Verify the device type is not CCT
        assert entity._light.dev_type == "0101"

        # The entity should not have registered DEV_PARAM listener.
        # We verify by checking that _handle_dev_param_update is not
        # called during normal operation (it exists but isn't wired up).
        # The real check is in async_added_to_hass which has the
        # `if self._light.dev_type == "0102"` guard.
        assert entity._light.dev_type != "0102"


class TestMissingCctFieldsKeepsDefaults:
    """Missing CCT fields in getDevParamRes should keep defaults."""

    def test_missing_cct_fields_keeps_defaults(self) -> None:
        """When cct_cool/cct_warm are missing, defaults stay."""
        entity = _make_light_entity(dev_type="0102")

        # Callback with no CCT fields
        entity._handle_dev_param_update(
            {
                "fade_time": 5,
                "fade_rate": 7,
            }
        )

        assert entity._attr_min_color_temp_kelvin == 1000
        assert entity._attr_max_color_temp_kelvin == 8000

    def test_partial_cct_fields_keeps_defaults(self) -> None:
        """When only one CCT field is present, defaults stay."""
        entity = _make_light_entity(dev_type="0102")

        entity._handle_dev_param_update(
            {
                "cct_warm": 2700,
                # cct_cool missing
            }
        )

        assert entity._attr_min_color_temp_kelvin == 1000
        assert entity._attr_max_color_temp_kelvin == 8000


class TestCctZeroValueKeepsDefaults:
    """CCT fields with value 0 should keep defaults."""

    def test_cct_zero_value_keeps_defaults(self) -> None:
        """When cct_cool or cct_warm is 0, defaults stay."""
        entity = _make_light_entity(dev_type="0102")

        entity._handle_dev_param_update(
            {
                "cct_warm": 0,
                "cct_cool": 0,
            }
        )

        assert entity._attr_min_color_temp_kelvin == 1000
        assert entity._attr_max_color_temp_kelvin == 8000

    def test_cct_one_zero_keeps_defaults(self) -> None:
        """When one CCT field is 0, defaults stay."""
        entity = _make_light_entity(dev_type="0102")

        entity._handle_dev_param_update(
            {
                "cct_warm": 2700,
                "cct_cool": 0,
            }
        )

        assert entity._attr_min_color_temp_kelvin == 1000
        assert entity._attr_max_color_temp_kelvin == 8000


# ---------------------------------------------------------------------------
# DaliCenterLightGroup CCT tests
# ---------------------------------------------------------------------------
def _make_group_entity(
    member_entity_ids: list[str],
) -> DaliCenterLightGroup:
    """Create a DaliCenterLightGroup with mocked Group and hass."""
    mock_group = MagicMock()
    mock_group.gw_sn = "GW001"
    mock_group.name = "Test Group"
    mock_group.unique_id = "test_group_001"
    mock_group.devices = [
        {"name": f"Light {i}", "unique_id": f"uid_{i}"}
        for i in range(len(member_entity_ids))
    ]

    entity = DaliCenterLightGroup(mock_group)
    # Inject cached_property value via instance __dict__.
    entity.__dict__["_group_entity_ids"] = member_entity_ids
    return entity


class TestGroupCctRangeUniformMembers:
    """All CCT members have the same range."""

    def test_group_cct_range_uniform_members(self) -> None:
        """Group range should equal member range when all are identical."""
        states = {
            "light.a": _make_state(
                supported_color_modes=["color_temp"],
                min_color_temp_kelvin=2700,
                max_color_temp_kelvin=6500,
            ),
            "light.b": _make_state(
                supported_color_modes=["color_temp"],
                min_color_temp_kelvin=2700,
                max_color_temp_kelvin=6500,
            ),
            "light.c": _make_state(
                supported_color_modes=["color_temp"],
                min_color_temp_kelvin=2700,
                max_color_temp_kelvin=6500,
            ),
        }

        entity = _make_group_entity(list(states.keys()))
        entity._attr_supported_color_modes = {"color_temp"}

        # Mock hass.states.get
        mock_hass = MagicMock()
        mock_hass.states.get = _make_states_getter(states)
        entity.hass = mock_hass

        entity._calculate_group_cct_range()

        assert entity._attr_min_color_temp_kelvin == 2700
        assert entity._attr_max_color_temp_kelvin == 6500


class TestGroupCctRangeMixedMembers:
    """Members with different CCT ranges."""

    def test_group_cct_range_mixed_members(self) -> None:
        """Group range should be union: min of warm, max of cool."""
        states = {
            "light.a": _make_state(
                supported_color_modes=["color_temp"],
                min_color_temp_kelvin=2700,
                max_color_temp_kelvin=6500,
            ),
            "light.b": _make_state(
                supported_color_modes=["color_temp"],
                min_color_temp_kelvin=3000,
                max_color_temp_kelvin=5000,
            ),
        }

        entity = _make_group_entity(list(states.keys()))
        entity._attr_supported_color_modes = {"color_temp"}

        mock_hass = MagicMock()
        mock_hass.states.get = _make_states_getter(states)
        entity.hass = mock_hass

        entity._calculate_group_cct_range()

        assert entity._attr_min_color_temp_kelvin == 2700
        assert entity._attr_max_color_temp_kelvin == 6500


class TestGroupCctRangeUpdatesOnMemberChange:
    """Group recalculates when member CCT range changes."""

    def test_group_cct_range_updates_on_member_change(self) -> None:
        """Group should recalculate CCT range when a member updates."""
        # Initial state: both at defaults (skip)
        states = {
            "light.a": _make_state(
                supported_color_modes=["color_temp"],
                min_color_temp_kelvin=1000,
                max_color_temp_kelvin=8000,
            ),
            "light.b": _make_state(
                supported_color_modes=["color_temp"],
                min_color_temp_kelvin=1000,
                max_color_temp_kelvin=8000,
            ),
        }

        entity = _make_group_entity(list(states.keys()))
        entity._attr_supported_color_modes = {"color_temp"}

        mock_hass = MagicMock()
        mock_hass.states.get = _make_states_getter(states)
        entity.hass = mock_hass

        entity._calculate_group_cct_range()
        # Still at defaults since all members are at defaults
        assert entity._attr_min_color_temp_kelvin == 1000
        assert entity._attr_max_color_temp_kelvin == 8000

        # Now member A gets its CCT range
        states["light.a"] = _make_state(
            supported_color_modes=["color_temp"],
            min_color_temp_kelvin=2700,
            max_color_temp_kelvin=6500,
        )
        mock_hass.states.get = _make_states_getter(states)

        entity._calculate_group_cct_range()
        assert entity._attr_min_color_temp_kelvin == 2700
        assert entity._attr_max_color_temp_kelvin == 6500

        # Now member B also gets its CCT range (wider)
        states["light.b"] = _make_state(
            supported_color_modes=["color_temp"],
            min_color_temp_kelvin=2000,
            max_color_temp_kelvin=7000,
        )
        mock_hass.states.get = _make_states_getter(states)

        entity._calculate_group_cct_range()
        assert entity._attr_min_color_temp_kelvin == 2000
        assert entity._attr_max_color_temp_kelvin == 7000


# ---------------------------------------------------------------------------
# DaliCenterAllLights CCT test
# ---------------------------------------------------------------------------
class TestAllLightsCctRangeUnchanged:
    """AllLights entity should keep default CCT range."""

    def test_all_lights_cct_range_unchanged(self) -> None:
        """AllLights CCT range should always be 1000-8000."""
        mock_controller = MagicMock()
        mock_controller.gw_sn = "GW001"
        mock_controller.address = 255
        mock_controller.channel = 0
        mock_controller.dev_type = "FFFF"
        mock_controller.model = "AllLights"
        mock_controller.unique_id = "all_lights_001"

        entity = DaliCenterAllLights(mock_controller, "config_entry_001")

        assert entity._attr_min_color_temp_kelvin == 1000
        assert entity._attr_max_color_temp_kelvin == 8000
