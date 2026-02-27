"""Tests for light group brightness aggregation (Issue #73).

Verifies that:
- calculate_aggregated_light_state correctly aggregates member brightness
- parse_light_status correctly converts gateway 0-1000 range to HA 0-255 range
- The end-to-end brightness chain (gateway → parse → aggregate) produces correct values
"""

from __future__ import annotations

from unittest.mock import MagicMock

from PySrDaliGateway.helper import parse_light_status

from custom_components.dali_center.light import calculate_aggregated_light_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_state(
    state: str = "on",
    brightness: int | None = 255,
    color_temp_kelvin: int | None = None,
    rgbw_color: tuple[int, int, int, int] | None = None,
    supported_color_modes: list[str] | None = None,
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
    return mock


def _make_states_getter(
    states: dict[str, MagicMock],
) -> MagicMock:
    """Create a states.get callable that returns mock states by entity_id."""
    return MagicMock(side_effect=states.get)


# ---------------------------------------------------------------------------
# parse_light_status: brightness conversion (PySrDaliGateway layer)
# ---------------------------------------------------------------------------
class TestParseLightStatusBrightness:
    """Test brightness conversion from gateway 0-1000 range to HA 0-255 range."""

    def test_full_brightness(self) -> None:
        """1000 (gateway max) should map to 255 (HA max)."""
        props = [{"dpid": 22, "value": 1000}]
        result = parse_light_status(props)
        assert result["brightness"] == 255

    def test_half_brightness(self) -> None:
        """500 should map to ~127."""
        props = [{"dpid": 22, "value": 500}]
        result = parse_light_status(props)
        assert result["brightness"] == 127

    def test_quarter_brightness(self) -> None:
        """250 should map to ~63."""
        props = [{"dpid": 22, "value": 250}]
        result = parse_light_status(props)
        assert result["brightness"] == 63

    def test_minimum_nonzero_brightness(self) -> None:
        """1 should map to 0 (int truncation)."""
        props = [{"dpid": 22, "value": 1}]
        result = parse_light_status(props)
        assert result["brightness"] == 0

    def test_zero_brightness(self) -> None:
        """brightness_value=0 should map to 0, not 255.

        Previously this had a special case that mapped 0 to 255,
        causing the '<25% wraps to 100%' bug in Issue #73.
        """
        props = [{"dpid": 22, "value": 0}]
        result = parse_light_status(props)
        assert result["brightness"] == 0

    def test_roundtrip_full_brightness(self) -> None:
        """Verify roundtrip: HA 255 → gateway 1000 → HA 255."""
        # HA sends: brightness * 1000 / 255
        ha_brightness = 255
        gateway_value = ha_brightness * 1000 / 255  # ~1000.0
        # Gateway returns: int(gateway_value / 1000 * 255)
        props = [{"dpid": 22, "value": gateway_value}]
        result = parse_light_status(props)
        assert result["brightness"] == ha_brightness

    def test_roundtrip_half_brightness(self) -> None:
        """Verify roundtrip: HA 128 → gateway ~502 → HA ~128."""
        ha_brightness = 128
        gateway_value = ha_brightness * 1000 / 255  # ~501.96
        props = [{"dpid": 22, "value": gateway_value}]
        result = parse_light_status(props)
        # Allow ±1 for integer rounding
        assert abs(result["brightness"] - ha_brightness) <= 1


# ---------------------------------------------------------------------------
# calculate_aggregated_light_state: group aggregation (ha-dali-center layer)
# ---------------------------------------------------------------------------
class TestCalculateAggregatedLightState:
    """Test brightness aggregation for light groups."""

    def test_all_lights_same_brightness(self) -> None:
        """All members at 255 → group should be 255."""
        states = {
            "light.a": _make_state(brightness=255),
            "light.b": _make_state(brightness=255),
            "light.c": _make_state(brightness=255),
        }
        result = calculate_aggregated_light_state(
            list(states.keys()),
            _make_states_getter(states),
            {"brightness"},
        )
        assert result.is_on is True
        assert result.brightness == 255

    def test_mixed_brightness(self) -> None:
        """Members at different brightness → group is average of ON lights."""
        states = {
            "light.a": _make_state(brightness=200),
            "light.b": _make_state(brightness=100),
        }
        result = calculate_aggregated_light_state(
            list(states.keys()),
            _make_states_getter(states),
            {"brightness"},
        )
        assert result.brightness == 150  # (200 + 100) // 2

    def test_some_lights_off(self) -> None:
        """OFF lights should be excluded from brightness average."""
        states = {
            "light.a": _make_state(brightness=200),
            "light.b": _make_state(state="off", brightness=0),
            "light.c": _make_state(brightness=100),
        }
        result = calculate_aggregated_light_state(
            list(states.keys()),
            _make_states_getter(states),
            {"brightness"},
        )
        # Only light.a (200) and light.c (100) are on → average = 150
        assert result.brightness == 150

    def test_all_lights_off(self) -> None:
        """All lights off → group is off with brightness 0."""
        states = {
            "light.a": _make_state(state="off", brightness=0),
            "light.b": _make_state(state="off", brightness=0),
        }
        result = calculate_aggregated_light_state(
            list(states.keys()),
            _make_states_getter(states),
            {"brightness"},
        )
        assert result.is_on is False
        assert result.brightness == 0

    def test_single_light_group(self) -> None:
        """Group with one member should match that member exactly."""
        states = {
            "light.a": _make_state(brightness=128),
        }
        result = calculate_aggregated_light_state(
            list(states.keys()),
            _make_states_getter(states),
            {"brightness"},
        )
        assert result.brightness == 128

    def test_missing_state(self) -> None:
        """Entity not found in states → should be skipped."""
        states = {
            "light.a": _make_state(brightness=200),
            # light.b does not exist in states
        }
        result = calculate_aggregated_light_state(
            ["light.a", "light.b"],
            _make_states_getter(states),
            {"brightness"},
        )
        assert result.brightness == 200

    def test_brightness_none_excluded(self) -> None:
        """Light that is 'on' but has no brightness attr → contributes 0."""
        states = {
            "light.a": _make_state(brightness=200),
            "light.b": _make_state(brightness=None),
        }
        result = calculate_aggregated_light_state(
            list(states.keys()),
            _make_states_getter(states),
            {"brightness"},
        )
        # light.b is "on" but brightness=None → contributes 0 to total
        # (200 + 0) // 2 = 100
        assert result.brightness == 100


# ---------------------------------------------------------------------------
# End-to-end scenario: Issue #73 reproduction
# ---------------------------------------------------------------------------
class TestIssue73EndToEnd:
    """Reproduce the exact scenarios from Issue #73.

    The user reports: when controlling DALI groups, the HA brightness display
    is wrong. These tests simulate what happens when the gateway reports back
    member device statuses after a group command.
    """

    def test_scenario_100_percent_shows_77(self) -> None:
        """Issue #73: Set to 100% → HA shows ~77%.

        If the gateway returns 770 instead of 1000 for member devices after a
        group brightness command, the group would show ~77%.
        """
        # Gateway returns 770 for each member (instead of 1000)
        parsed_a = parse_light_status(
            [{"dpid": 20, "value": 1}, {"dpid": 22, "value": 770}]
        )
        parsed_b = parse_light_status(
            [{"dpid": 20, "value": 1}, {"dpid": 22, "value": 770}]
        )

        brightness_a = parsed_a["brightness"]  # int(770/1000*255) = 196 ≈ 77%
        brightness_b = parsed_b["brightness"]

        states = {
            "light.a": _make_state(brightness=brightness_a),
            "light.b": _make_state(brightness=brightness_b),
        }
        result = calculate_aggregated_light_state(
            list(states.keys()),
            _make_states_getter(states),
            {"brightness"},
        )
        # 196 ≈ 77% of 255 — matches user's reported behavior
        assert result.brightness == 196
        assert result.brightness != 255, "Should be 255 if gateway reported correctly"

    def test_scenario_50_percent_shows_25(self) -> None:
        """Issue #73: Set to 50% → HA shows ~25%.

        If the gateway returns 250 instead of 500 for member devices,
        the group would show ~25%.
        """
        parsed_a = parse_light_status(
            [{"dpid": 20, "value": 1}, {"dpid": 22, "value": 250}]
        )
        parsed_b = parse_light_status(
            [{"dpid": 20, "value": 1}, {"dpid": 22, "value": 250}]
        )

        brightness_a = parsed_a["brightness"]  # int(250/1000*255) = 63 ≈ 25%
        brightness_b = parsed_b["brightness"]

        states = {
            "light.a": _make_state(brightness=brightness_a),
            "light.b": _make_state(brightness=brightness_b),
        }
        result = calculate_aggregated_light_state(
            list(states.keys()),
            _make_states_getter(states),
            {"brightness"},
        )
        # 63 ≈ 25% of 255 — matches user's reported behavior
        assert result.brightness == 63
        assert result.brightness != 127, "Should be ~127 if gateway reported correctly"

    def test_scenario_low_brightness_no_longer_wraps(self) -> None:
        """Issue #73 fix: Set to <25% → should show 0%, not wrap to 100%.

        Previously parse_light_status had a special case where
        brightness_value=0 mapped to brightness=255. Now fixed to map to 0.
        """
        # Gateway reports brightness=0 for member devices
        parsed_a = parse_light_status(
            [{"dpid": 20, "value": 1}, {"dpid": 22, "value": 0}]
        )
        parsed_b = parse_light_status(
            [{"dpid": 20, "value": 1}, {"dpid": 22, "value": 0}]
        )

        # Fixed: brightness_value=0 → brightness=0
        assert parsed_a["brightness"] == 0
        assert parsed_b["brightness"] == 0

        states = {
            "light.a": _make_state(brightness=parsed_a["brightness"]),
            "light.b": _make_state(brightness=parsed_b["brightness"]),
        }
        result = calculate_aggregated_light_state(
            list(states.keys()),
            _make_states_getter(states),
            {"brightness"},
        )
        assert result.brightness == 0

    def test_correct_behavior_when_gateway_reports_accurately(self) -> None:
        """When gateway reports correct values, aggregation works fine.

        This proves the aggregation logic itself is correct —
        the problem is upstream (gateway reporting wrong values).
        """
        # Gateway correctly reports 1000 for 100% brightness
        parsed = parse_light_status(
            [{"dpid": 20, "value": 1}, {"dpid": 22, "value": 1000}]
        )
        assert parsed["brightness"] == 255

        states = {
            "light.a": _make_state(brightness=255),
            "light.b": _make_state(brightness=255),
            "light.c": _make_state(brightness=255),
        }
        result = calculate_aggregated_light_state(
            list(states.keys()),
            _make_states_getter(states),
            {"brightness"},
        )
        assert result.brightness == 255
