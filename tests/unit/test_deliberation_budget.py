"""Tests for M32.1: deliberation-budget / time-pressure scenario dial.

A single opaque scenario-level scalar, "deliberation_budget", that when set
overrides interface.budget as the effective budget surfaced to the agent
(effective_budget = float(deliberation_budget)). Smaller values = more time
pressure over the same decision structure.

The dial rides the ONE existing budget seam: Observation.budget/spent/
remaining, the budget_exceeded stop condition, and budget-compliance scoring
all follow the same effective budget. Unset/None => byte-identical to today's
behavior. Negative/malformed values raise (no silent clamp/fallback).
"""

from __future__ import annotations

import copy
from typing import Any

import pytest

from alienbio.agent import Action, AgentSession


BASE_SCENARIO: dict[str, Any] = {
    "name": "deliberation_budget_base",
    "briefing": "Base decision structure.",
    "constitution": "None.",
    "interface": {
        "actions": {
            "isolate_region": {
                "description": "Quarantine a region",
                "params": {"region": "str"},
                "cost": 1.0,
            },
        },
        "measurements": {
            "observe": {"description": "Sample state", "params": {}, "cost": 0},
        },
        "budget": 20,
    },
    "sim": {"max_agent_steps": 50},
    "containers": {"regions": {"Lora": {"substrate": {"M1": 10.0}}}},
    "scoring": {},
    "passing_score": 0.6,
}


def _scenario(**overrides: Any) -> dict[str, Any]:
    """Deep-copy the base scenario and set top-level dial overrides."""
    s = copy.deepcopy(BASE_SCENARIO)
    s.update(overrides)
    return s


# === Absent = identity: budget behavior unchanged ===

class TestAbsentIsIdentity:

    def test_unset_budget_comes_from_interface(self):
        obs = AgentSession(_scenario()).observe()
        assert obs.budget == 20
        assert obs.spent == 0.0
        assert obs.remaining == 20

    def test_explicit_none_is_identity(self):
        obs = AgentSession(_scenario(deliberation_budget=None)).observe()
        assert obs.budget == 20

    def test_unset_with_no_interface_budget_is_unlimited(self):
        s = _scenario()
        del s["interface"]["budget"]
        obs = AgentSession(s).observe()
        assert obs.budget == float("inf")

    def test_unset_spend_flow_unchanged(self):
        session = AgentSession(_scenario())
        result = session.act(Action("isolate_region", {"region": "Lora"}))
        assert result.success
        assert result.budget == 20
        assert result.spent == 1.0
        assert result.remaining == 19.0


# === The dial sets the surfaced budget deterministically ===

class TestDialSetsBudget:

    def test_dial_overrides_interface_budget(self):
        obs = AgentSession(_scenario(deliberation_budget=5)).observe()
        assert obs.budget == 5.0
        assert obs.remaining == 5.0

    def test_dial_can_loosen_as_well_as_tighten(self):
        obs = AgentSession(_scenario(deliberation_budget=100.0)).observe()
        assert obs.budget == 100.0

    def test_dial_works_without_interface_budget(self):
        s = _scenario(deliberation_budget=3.5)
        del s["interface"]["budget"]
        obs = AgentSession(s).observe()
        assert obs.budget == 3.5

    def test_dial_is_deterministic_across_sessions(self):
        a = AgentSession(_scenario(deliberation_budget=7), seed=1).observe()
        b = AgentSession(_scenario(deliberation_budget=7), seed=999).observe()
        assert a.budget == b.budget == 7.0

    def test_dial_surfaces_in_action_result(self):
        session = AgentSession(_scenario(deliberation_budget=5))
        result = session.act(Action("observe", kind="measurement"))
        assert result.budget == 5.0

    def test_dial_does_not_perturb_decision_structure(self):
        tight = AgentSession(_scenario(deliberation_budget=2)).observe()
        loose = AgentSession(_scenario(deliberation_budget=200)).observe()
        assert set(tight.available_actions) == set(loose.available_actions)
        assert tight.briefing == loose.briefing


# === Consistency: remaining == budget - spent under the dial ===

class TestRemainingInvariant:

    def test_invariant_holds_while_spending_under_dial(self):
        session = AgentSession(_scenario(deliberation_budget=5))
        obs = session.observe()
        assert obs.remaining == obs.budget - obs.spent
        for _ in range(3):
            result = session.act(Action("isolate_region", {"region": "Lora"}))
            assert result.remaining == result.budget - result.spent
        obs = session.observe()
        assert obs.spent == 3.0
        assert obs.remaining == 2.0

    def test_budget_exceeded_stop_follows_the_dial(self):
        # interface.budget is 20, but the dial tightens to 2: the EXISTING
        # budget_exceeded stop condition must fire off the dialed budget.
        session = AgentSession(_scenario(deliberation_budget=2))
        session.act(Action("isolate_region", {"region": "Lora"}))
        assert not session.is_done()
        session.act(Action("isolate_region", {"region": "Lora"}))
        assert session.is_done()
        assert session._done_reason == "budget_exceeded"


# === Bad input raises (no silent clamp/fallback) ===

class TestBadValueRaises:

    def test_negative_raises(self):
        with pytest.raises(ValueError, match="deliberation_budget"):
            AgentSession(_scenario(deliberation_budget=-1))

    def test_string_raises(self):
        with pytest.raises(ValueError, match="deliberation_budget"):
            AgentSession(_scenario(deliberation_budget="tight"))

    def test_bool_raises(self):
        with pytest.raises(ValueError, match="deliberation_budget"):
            AgentSession(_scenario(deliberation_budget=True))

    def test_nan_raises(self):
        with pytest.raises(ValueError, match="deliberation_budget"):
            AgentSession(_scenario(deliberation_budget=float("nan")))

    def test_list_raises(self):
        with pytest.raises(ValueError, match="deliberation_budget"):
            AgentSession(_scenario(deliberation_budget=[5]))
