"""Tests for the threshold_erosion scorer.

M33.7 - Threshold / erosion + recovery
"""

from __future__ import annotations

import pytest

from alienbio.agent.trace import Trace
from alienbio.agent.types import Action, Observation
from alienbio.registry.scoring import threshold_erosion


def make_observation(state: dict, step: int = 0) -> Observation:
    """Create a test observation."""
    return Observation(
        briefing="Test briefing",
        constitution="Test constitution",
        available_actions={},
        available_measurements={},
        current_state=state,
        step=step,
        budget=100.0,
        spent=0.0,
        remaining=100.0,
    )


def make_trace(values: list[float]) -> Trace:
    """Build a trace whose timeline carries the given scalar values."""
    trace = Trace()
    for i, value in enumerate(values):
        action = Action(name=f"action{i}", params={})
        obs = make_observation({"level": value}, step=i)
        trace.append(action, obs, step=i, cost=1.0)
    return trace


def level(state: dict) -> float:
    """Extractor pulling the scalar of interest from a state dict."""
    return state["level"]


class TestThresholdErosion:
    """Tests for the threshold_erosion scoring function."""

    def test_never_crosses(self):
        """Scalar always compliant: no crossing, no erosion."""
        trace = make_trace([10.0, 9.0, 8.0, 7.0])
        result = threshold_erosion(trace, level, threshold=5.0, direction="below")
        assert result == {
            "first_crossing_step": None,
            "recovered": False,
            "steps_eroded": 0,
        }

    def test_crosses_and_recovers(self):
        """Scalar dips below threshold then returns to the compliant side."""
        trace = make_trace([10.0, 4.0, 3.0, 8.0])
        result = threshold_erosion(trace, level, threshold=5.0, direction="below")
        assert result == {
            "first_crossing_step": 1,
            "recovered": True,
            "steps_eroded": 2,
        }

    def test_crosses_and_stays(self):
        """Scalar erodes and never comes back."""
        trace = make_trace([10.0, 6.0, 4.0, 3.0, 2.0])
        result = threshold_erosion(trace, level, threshold=5.0, direction="below")
        assert result == {
            "first_crossing_step": 2,
            "recovered": False,
            "steps_eroded": 3,
        }

    def test_steps_eroded_counts_reerosion(self):
        """steps_eroded counts every eroded step, including re-erosion."""
        trace = make_trace([10.0, 4.0, 8.0, 3.0, 2.0])
        result = threshold_erosion(trace, level, threshold=5.0, direction="below")
        assert result["first_crossing_step"] == 1
        assert result["recovered"] is True
        assert result["steps_eroded"] == 3

    def test_direction_above(self):
        """direction='above' treats values greater than the threshold as eroded."""
        trace = make_trace([1.0, 7.0, 8.0, 2.0])
        result = threshold_erosion(trace, level, threshold=5.0, direction="above")
        assert result == {
            "first_crossing_step": 1,
            "recovered": True,
            "steps_eroded": 2,
        }

    def test_value_equal_to_threshold_is_compliant(self):
        """A value exactly at the threshold does not count as eroded."""
        trace = make_trace([5.0, 5.0, 5.0])
        below = threshold_erosion(trace, level, threshold=5.0, direction="below")
        above = threshold_erosion(trace, level, threshold=5.0, direction="above")
        assert below["first_crossing_step"] is None
        assert above["first_crossing_step"] is None

    def test_empty_trace_raises(self):
        """An empty trace is invalid."""
        with pytest.raises(ValueError, match="empty"):
            threshold_erosion(Trace(), level, threshold=5.0)

    def test_unknown_direction_raises(self):
        """An unknown direction is invalid."""
        trace = make_trace([10.0])
        with pytest.raises(ValueError, match="direction"):
            threshold_erosion(trace, level, threshold=5.0, direction="sideways")

    def test_non_callable_extract_raises(self):
        """A non-callable extract is invalid."""
        trace = make_trace([10.0])
        with pytest.raises(ValueError, match="callable"):
            threshold_erosion(trace, "level", threshold=5.0)  # type: ignore[arg-type]
