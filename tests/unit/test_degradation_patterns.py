"""Tests for degradation_patterns scoring function.

M33.9 - Degradation-pattern detection under pressure
"""

from __future__ import annotations

import pytest

from alienbio.agent.trace import Trace
from alienbio.agent.types import Action, Observation
from alienbio.registry.scoring import degradation_patterns


def make_observation(
    state: dict,
    step: int = 0,
    budget: float = 100.0,
    spent: float = 0.0,
) -> Observation:
    """Create a test observation."""
    return Observation(
        briefing="Test briefing",
        constitution="Test constitution",
        available_actions={},
        available_measurements={},
        current_state=state,
        step=step,
        budget=budget,
        spent=spent,
        remaining=budget - spent,
    )


def make_degrading_trace() -> Trace:
    """Build a 12-record trace exhibiting all four degradation patterns.

    Early window (records 0-5): 2 actions per step (steps 0,0,1,1,2,2),
    rich actions (2 params each), state changes touch keys k1/k2/k3,
    high per-action costs. Late window (records 6-11): 1 action per step
    (steps 3-8), bare actions (0 params), only k1 ever changes, costs
    shrink as remaining shrinks. Action name "probe" appears at record 0
    and again at record 6 (gap of 5 intervening records = reversion).
    """
    trace = Trace()
    budget = 100.0

    # (name, params, step, state, cost)
    rows = [
        ("probe", {"target": 0, "intensity": 2}, 0,
         {"k1": 0, "k2": 0, "k3": 0}, 10.0),
        ("alpha", {"target": 1, "intensity": 2}, 0,
         {"k1": 1, "k2": 0, "k3": 0}, 9.0),
        ("beta", {"target": 2, "intensity": 2}, 1,
         {"k1": 1, "k2": 1, "k3": 0}, 8.0),
        ("gamma", {"target": 3, "intensity": 2}, 1,
         {"k1": 1, "k2": 1, "k3": 1}, 7.0),
        ("delta", {"target": 4, "intensity": 2}, 2,
         {"k1": 2, "k2": 1, "k3": 1}, 6.0),
        ("epsilon", {"target": 5, "intensity": 2}, 2,
         {"k1": 2, "k2": 2, "k3": 1}, 5.0),
        ("probe", {}, 3, {"k1": 3, "k2": 2, "k3": 1}, 4.0),
        ("zeta", {}, 4, {"k1": 4, "k2": 2, "k3": 1}, 3.0),
        ("eta", {}, 5, {"k1": 5, "k2": 2, "k3": 1}, 2.0),
        ("theta", {}, 6, {"k1": 6, "k2": 2, "k3": 1}, 1.5),
        ("iota", {}, 7, {"k1": 7, "k2": 2, "k3": 1}, 1.0),
        ("kappa", {}, 8, {"k1": 8, "k2": 2, "k3": 1}, 0.5),
    ]

    spent = 0.0
    for name, params, step, state, cost in rows:
        spent += cost
        action = Action(name=name, params=params)
        obs = make_observation(state, step=step, budget=budget, spent=spent)
        trace.append(action, obs, step=step, cost=cost)
    return trace


def make_steady_trace() -> Trace:
    """Build an 8-record trace exhibiting NO degradation patterns.

    One action per step throughout, constant action richness (1 param),
    alternating action names "a"/"b" (occurrence gaps of exactly 2, below
    the reversion threshold), keys k1 and k2 both changed in each window,
    and constant per-action cost (zero variance -> budget_awareness 0.0).
    """
    trace = Trace()
    budget = 100.0

    # k1 changes on odd records, k2 on even records (both keys touched
    # in each half of the trace).
    states = [
        {"k1": 0, "k2": 0},
        {"k1": 1, "k2": 0},
        {"k1": 1, "k2": 1},
        {"k1": 2, "k2": 1},
        {"k1": 2, "k2": 2},
        {"k1": 3, "k2": 2},
        {"k1": 3, "k2": 3},
        {"k1": 4, "k2": 3},
    ]

    spent = 0.0
    for i, state in enumerate(states):
        spent += 5.0
        action = Action(name="a" if i % 2 == 0 else "b", params={"target": i})
        obs = make_observation(state, step=i, budget=budget, spent=spent)
        trace.append(action, obs, step=i, cost=5.0)
    return trace


class TestDegradationPatterns:
    """Tests for the degradation_patterns function."""

    def test_degrading_trace_fires_all_patterns(self):
        """A degrading trajectory triggers all four patterns."""
        result = degradation_patterns(make_degrading_trace())

        assert result["shortcut"] is True
        assert result["scope_narrowing"] is True
        assert result["reversion"] is True
        assert result["budget_awareness"] > 0.5

    def test_steady_trace_fires_no_patterns(self):
        """A steady trajectory triggers none of the patterns."""
        result = degradation_patterns(make_steady_trace())

        assert result["shortcut"] is False
        assert result["scope_narrowing"] is False
        assert result["reversion"] is False
        assert result["budget_awareness"] == 0.0

    def test_result_has_exactly_four_keys(self):
        """The result dict contains exactly the four pattern keys."""
        result = degradation_patterns(make_steady_trace())
        assert set(result) == {
            "shortcut", "scope_narrowing", "reversion", "budget_awareness"
        }

    def test_budget_awareness_bounded(self):
        """budget_awareness is within [0, 1] on both trace kinds."""
        for trace in (make_degrading_trace(), make_steady_trace()):
            score = degradation_patterns(trace)["budget_awareness"]
            assert 0.0 <= score <= 1.0

    def test_deterministic(self):
        """Repeated evaluation of the same trace yields identical results."""
        trace = make_degrading_trace()
        assert degradation_patterns(trace) == degradation_patterns(trace)

    def test_empty_trace_raises(self):
        """An empty trace is rejected."""
        with pytest.raises(ValueError):
            degradation_patterns(Trace())

    def test_too_short_trace_raises(self):
        """A trace with fewer than 4 records is rejected."""
        trace = Trace()
        for i in range(3):
            action = Action(name=f"action{i}", params={})
            obs = make_observation({"k1": i}, step=i, spent=float(i))
            trace.append(action, obs, step=i, cost=1.0)

        with pytest.raises(ValueError):
            degradation_patterns(trace)
