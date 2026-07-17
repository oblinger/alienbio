"""Tests for M28.2: the observability scenario dial.

``observability`` is an opaque scenario-level fraction (0.0..1.0) controlling
how much of the world state the agent can observe. When set, a seed-chosen
subset of the top-level ``current_state`` entries is hidden from the agent's
Observation. The GROUND-TRUTH world state is never touched — only what the
agent observes is filtered.

Contract under test:
- Absent (None) => the observation is byte-identical to the no-dial case.
- Seed-deterministic => same seed + same fraction => same hidden subset.
- Fraction semantics => 1.0 keeps everything; a lower value hides a
  proportionate subset; 0.0 hides everything.
- Raises on bad input => out-of-range / malformed values raise (no clamp).
- Domain-neutral => a fraction over opaque state keys, no biology semantics.
"""

from __future__ import annotations

import copy
from typing import Any

import pytest

from alienbio.agent import Action, AgentSession
from alienbio.agent.session import (
    _coerce_observability,
    _filter_observable_state,
)


BASE_SCENARIO: dict[str, Any] = {
    "name": "observability_base",
    "briefing": "Base decision structure.",
    "constitution": "None.",
    "interface": {
        "actions": {
            "poke": {
                "description": "Poke the world",
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


# A multi-entry opaque state, for exercising fraction/count/determinism on the
# pure filter (the mock simulator only surfaces a single top-level key).
WIDE_STATE: dict[str, Any] = {f"K{i}": {"v": i} for i in range(10)}


# === Absent = identity (the #1 guarantee) ===

class TestAbsentIsIdentity:

    def test_default_observation_has_no_dial(self):
        obs = AgentSession(_scenario(), seed=7).observe()
        assert obs.observability is None

    def test_current_state_byte_identical_when_unset(self):
        """No-dial observation must equal a bare mock observable_state."""
        session = AgentSession(_scenario(), seed=7)
        raw = session.simulator.observable_state()
        obs = session.observe()
        assert obs.current_state == raw

    def test_filter_returns_same_object_when_none(self):
        """None short-circuits: the ground-truth dict flows through untouched."""
        state = {"a": 1, "b": 2}
        out = _filter_observable_state(state, None, seed=7)
        assert out is state


# === Surfacing on Observation / ActionResult ===

class TestDialSurfaces:

    def test_observability_surfaces_on_observation(self):
        obs = AgentSession(_scenario(observability=0.5), seed=1).observe()
        assert obs.observability == 0.5

    def test_observability_surfaces_on_action_result(self):
        session = AgentSession(_scenario(observability=0.5), seed=1)
        result = session.act(Action("observe", kind="measurement"))
        assert result.observability == 0.5

    def test_full_observability_keeps_all_entries(self):
        session = AgentSession(_scenario(observability=1.0), seed=1)
        raw = session.simulator.observable_state()
        obs = session.observe()
        assert obs.current_state == raw

    def test_zero_observability_hides_everything(self):
        obs = AgentSession(_scenario(observability=0.0), seed=1).observe()
        assert obs.current_state == {}


# === Ground truth is untouched ===

class TestGroundTruthUntouched:

    def test_filtering_does_not_mutate_simulator_state(self):
        session = AgentSession(_scenario(observability=0.0), seed=1)
        session.observe()
        # The simulator still reports its full ground-truth state.
        assert session.simulator.observable_state() == {
            "regions": {"Lora": {"substrate": {"M1": 10.0}}}
        }

    def test_filter_does_not_mutate_input(self):
        original = copy.deepcopy(WIDE_STATE)
        _filter_observable_state(WIDE_STATE, 0.3, seed=1)
        assert WIDE_STATE == original


# === Fraction semantics: expected visible count ===

class TestFractionCount:

    @pytest.mark.parametrize(
        "fraction,expected_visible",
        [(1.0, 10), (0.7, 7), (0.5, 5), (0.3, 3), (0.0, 0)],
    )
    def test_visible_count_matches_fraction(self, fraction, expected_visible):
        out = _filter_observable_state(WIDE_STATE, fraction, seed=1)
        assert len(out) == expected_visible

    def test_visible_entries_are_a_subset_of_ground_truth(self):
        out = _filter_observable_state(WIDE_STATE, 0.4, seed=1)
        assert set(out).issubset(set(WIDE_STATE))
        for k, v in out.items():
            assert v == WIDE_STATE[k]


# === Seed determinism ===

class TestSeedDeterminism:

    def test_same_seed_same_fraction_same_subset(self):
        a = _filter_observable_state(WIDE_STATE, 0.4, seed=42)
        b = _filter_observable_state(WIDE_STATE, 0.4, seed=42)
        assert a == b
        assert set(a) == set(b)

    def test_different_seed_can_differ(self):
        a = _filter_observable_state(WIDE_STATE, 0.4, seed=1)
        b = _filter_observable_state(WIDE_STATE, 0.4, seed=999)
        # Same count, but a seed-dependent (generally different) subset.
        assert len(a) == len(b) == 4
        assert set(a) != set(b)

    def test_session_hidden_subset_is_seed_reproducible(self):
        s1 = AgentSession(_scenario(observability=0.4), seed=123)
        s2 = AgentSession(_scenario(observability=0.4), seed=123)
        assert s1.observe().current_state == s2.observe().current_state


# === Raises on bad input (no silent clamp) ===

class TestRaisesOnBadInput:

    @pytest.mark.parametrize("bad", [-0.1, 1.1, 2.0, -1.0, 100])
    def test_out_of_range_fraction_raises(self, bad):
        with pytest.raises(ValueError):
            AgentSession(_scenario(observability=bad), seed=1)

    @pytest.mark.parametrize("bad", ["0.5", "full", [0.5], {"f": 0.5}, True, False])
    def test_malformed_value_raises(self, bad):
        with pytest.raises(TypeError):
            AgentSession(_scenario(observability=bad), seed=1)

    def test_coerce_none_passes_through(self):
        assert _coerce_observability(None) is None

    def test_coerce_int_bounds_accepted(self):
        assert _coerce_observability(1) == 1.0
        assert _coerce_observability(0) == 0.0
