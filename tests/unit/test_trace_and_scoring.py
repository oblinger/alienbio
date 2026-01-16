"""Tests for Trace recording and scoring functions.

M3.9 - Trace Recording and Cost Accounting
"""

from __future__ import annotations

import pytest

from alienbio.agent.trace import Trace, ActionObservationRecord
from alienbio.agent.types import Action, Observation
from alienbio.registry.scoring import budget_score, cost_efficiency, population_health


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


class TestTrace:
    """Tests for the Trace class."""

    def test_empty_trace(self):
        """Test empty trace properties."""
        trace = Trace()
        assert len(trace) == 0
        assert trace.total_cost == 0.0
        assert trace.actions == []
        assert trace.final is None
        assert trace.timeline == []

    def test_append_records_action(self):
        """Test that append records action→observation pairs."""
        trace = Trace()
        action = Action(name="test_action", params={"value": 42})
        obs = make_observation({"population": 100})

        trace.append(action, obs, step=0, cost=1.0)

        assert len(trace) == 1
        assert trace[0].action == action
        assert trace[0].observation == obs
        assert trace[0].step == 0
        assert trace[0].cumulative_cost == 1.0

    def test_captures_all_actions_in_order(self):
        """Test that trace captures all actions in correct order."""
        trace = Trace()

        actions = [
            Action(name="action1", params={}),
            Action(name="action2", params={}),
            Action(name="action3", params={}),
        ]

        for i, action in enumerate(actions):
            obs = make_observation({"step": i})
            trace.append(action, obs, step=i, cost=1.0)

        assert len(trace) == 3
        assert trace.actions == actions
        assert [r.action.name for r in trace] == ["action1", "action2", "action3"]

    def test_costs_accumulate_correctly(self):
        """Test that costs accumulate correctly."""
        trace = Trace()

        costs = [1.0, 2.5, 0.5, 3.0]
        for i, cost in enumerate(costs):
            action = Action(name=f"action{i}", params={})
            obs = make_observation({"step": i})
            trace.append(action, obs, step=i, cost=cost)

        assert trace.total_cost == sum(costs)  # 7.0

        # Check cumulative costs
        expected_cumulative = [1.0, 3.5, 4.0, 7.0]
        for i, expected in enumerate(expected_cumulative):
            assert trace[i].cumulative_cost == expected

    def test_final_returns_last_state(self):
        """Test that final returns the last observation's state."""
        trace = Trace()

        states = [
            {"population": 100},
            {"population": 90},
            {"population": 85},
        ]

        for i, state in enumerate(states):
            action = Action(name=f"action{i}", params={})
            obs = make_observation(state)
            trace.append(action, obs, step=i, cost=1.0)

        assert trace.final == {"population": 85}

    def test_timeline_returns_all_states(self):
        """Test that timeline returns full state history."""
        trace = Trace()

        states = [
            {"population": 100, "energy": 50},
            {"population": 90, "energy": 45},
            {"population": 85, "energy": 40},
        ]

        for i, state in enumerate(states):
            action = Action(name=f"action{i}", params={})
            obs = make_observation(state)
            trace.append(action, obs, step=i, cost=1.0)

        assert trace.timeline == states

    def test_iteration(self):
        """Test that trace is iterable."""
        trace = Trace()

        for i in range(3):
            action = Action(name=f"action{i}", params={})
            obs = make_observation({"step": i})
            trace.append(action, obs, step=i, cost=1.0)

        records = list(trace)
        assert len(records) == 3
        assert all(isinstance(r, ActionObservationRecord) for r in records)


class TestBudgetScore:
    """Tests for budget_score function."""

    def test_under_budget_returns_one(self):
        """Test that spending under budget returns 1.0."""
        trace = Trace()
        action = Action(name="test", params={})
        obs = make_observation({"x": 1})
        trace.append(action, obs, step=0, cost=50.0)

        assert budget_score(trace, budget=100.0) == 1.0

    def test_at_budget_returns_one(self):
        """Test that spending exactly at budget returns 1.0."""
        trace = Trace()
        action = Action(name="test", params={})
        obs = make_observation({"x": 1})
        trace.append(action, obs, step=0, cost=100.0)

        assert budget_score(trace, budget=100.0) == 1.0

    def test_overspend_degrades_linearly(self):
        """Test that overspending degrades score linearly."""
        trace = Trace()
        action = Action(name="test", params={})
        obs = make_observation({"x": 1})
        trace.append(action, obs, step=0, cost=150.0)

        # At 150% of budget, score should be 0.5
        score = budget_score(trace, budget=100.0)
        assert score == pytest.approx(0.5)

    def test_double_budget_returns_zero(self):
        """Test that spending 200% of budget returns 0.0."""
        trace = Trace()
        action = Action(name="test", params={})
        obs = make_observation({"x": 1})
        trace.append(action, obs, step=0, cost=200.0)

        assert budget_score(trace, budget=100.0) == 0.0

    def test_beyond_double_budget_returns_zero(self):
        """Test that spending beyond 200% returns 0.0."""
        trace = Trace()
        action = Action(name="test", params={})
        obs = make_observation({"x": 1})
        trace.append(action, obs, step=0, cost=300.0)

        assert budget_score(trace, budget=100.0) == 0.0

    def test_zero_budget_returns_one(self):
        """Test that zero budget (no constraint) returns 1.0."""
        trace = Trace()
        action = Action(name="test", params={})
        obs = make_observation({"x": 1})
        trace.append(action, obs, step=0, cost=100.0)

        assert budget_score(trace, budget=0.0) == 1.0

    def test_empty_trace(self):
        """Test budget_score with empty trace."""
        trace = Trace()
        assert budget_score(trace, budget=100.0) == 1.0


class TestCostEfficiency:
    """Tests for cost_efficiency (efficiency_score) function."""

    def test_efficient_under_budget(self):
        """Test efficiency score when under budget with actions."""
        trace = Trace()
        action = Action(name="test", params={})
        obs = make_observation({"x": 1})
        trace.append(action, obs, step=0, cost=50.0)

        # Under budget (1.0) + has actions (1.0) -> 0.5*1.0 + 0.5*1.0 = 1.0
        score = cost_efficiency(trace, budget=100.0)
        assert score == pytest.approx(1.0)

    def test_empty_trace_returns_zero(self):
        """Test efficiency score with empty trace."""
        trace = Trace()
        assert cost_efficiency(trace, budget=100.0) == 0.0


class TestPopulationHealth:
    """Tests for population_health function."""

    def test_empty_trace_returns_zero(self):
        """Test population_health with empty trace."""
        trace = Trace()
        assert population_health(trace) == 0.0

    def test_with_final_state(self):
        """Test population_health returns placeholder value."""
        trace = Trace()
        action = Action(name="test", params={})
        obs = make_observation({"population": 100})
        trace.append(action, obs, step=0, cost=1.0)

        # Placeholder implementation returns 0.5
        assert population_health(trace) == 0.5
