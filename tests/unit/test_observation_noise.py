"""Tests for M28.3: observation-noise / stochasticity scenario dial.

A scenario-level "observation_noise" key that perturbs the numeric READINGS
surfaced to the agent (Observation.current_state / measurement data) by a
seed-deterministic noise term. The ground-truth world state is never touched.

Guarantees under test:
- absent (or 0) => identity: observation equal to today's, ground truth shared
- seed-deterministic: same seed + same level => identical perturbed readings
- magnitude scales: larger level => larger perturbation (same eps, scaled)
- ground truth untouched: underlying world state unchanged after observing
- malformed level raises: negative / non-numeric / non-finite — no clamp
"""

from __future__ import annotations

import copy
from typing import Any

import pytest

from alienbio.agent import Action, AgentSession


BASE_SCENARIO: dict[str, Any] = {
    "name": "obs_noise_base",
    "briefing": "Base decision structure.",
    "constitution": "None.",
    "interface": {
        "actions": {
            "add_feedstock": {
                "description": "Add feedstock",
                "params": {"molecule": "str", "amount": "float"},
                "cost": 1.0,
            },
        },
        "measurements": {
            "observe": {"description": "Sample state", "params": {}, "cost": 0},
        },
        "budget": 20,
    },
    "sim": {"max_agent_steps": 50},
    "containers": {
        "regions": {
            "Lora": {"substrate": {"M1": 10.0, "M2": 4}, "label": "west"},
            "Kess": {"substrate": {"M1": 2.5}},
        }
    },
    "scoring": {},
    "passing_score": 0.6,
}


def _scenario(**overrides: Any) -> dict[str, Any]:
    """Deep-copy the base scenario and set top-level dial overrides."""
    s = copy.deepcopy(BASE_SCENARIO)
    s.update(overrides)
    return s


def _readings(state: dict[str, Any]) -> dict[str, float]:
    """Flatten the numeric readings of an observed state to path -> value."""
    out: dict[str, float] = {}

    def walk(value: Any, path: str) -> None:
        if isinstance(value, dict):
            for k, v in value.items():
                walk(v, f"{path}/{k}")
        elif isinstance(value, list):
            for i, v in enumerate(value):
                walk(v, f"{path}/{i}")
        elif isinstance(value, bool):
            pass
        elif isinstance(value, (int, float)):
            out[path] = value

    walk(state, "")
    return out


# === Absent => identity ===

class TestAbsentIsIdentity:

    def test_unset_observation_identical_to_baseline(self):
        baseline = AgentSession(_scenario(), seed=7).observe()
        unset = AgentSession(_scenario(), seed=7).observe()
        assert unset.current_state == baseline.current_state
        assert unset.observation_noise is None

    def test_unset_readings_exactly_ground_truth(self):
        session = AgentSession(_scenario(), seed=7)
        obs = session.observe()
        assert obs.current_state == session.simulator.observable_state()

    def test_zero_level_is_identity(self):
        obs = AgentSession(_scenario(observation_noise=0.0), seed=7).observe()
        truth = AgentSession(_scenario(), seed=7).observe()
        assert obs.current_state == truth.current_state


# === Dial surfaces on Observation / ActionResult ===

class TestDialSurfaces:

    def test_level_surfaces_in_observation(self):
        obs = AgentSession(_scenario(observation_noise=0.2), seed=7).observe()
        assert obs.observation_noise == 0.2

    def test_level_surfaces_in_action_result(self):
        session = AgentSession(_scenario(observation_noise=0.2), seed=7)
        result = session.act(Action("observe", kind="measurement"))
        assert result.observation_noise == 0.2


# === Noise actually perturbs readings ===

class TestNoisePerturbs:

    def test_positive_level_changes_numeric_readings(self):
        truth = _readings(AgentSession(_scenario(), seed=7).observe().current_state)
        noised = _readings(
            AgentSession(_scenario(observation_noise=0.5), seed=7)
            .observe().current_state
        )
        assert set(noised) == set(truth)
        assert any(noised[p] != truth[p] for p in truth)

    def test_non_numeric_leaves_untouched(self):
        obs = AgentSession(_scenario(observation_noise=0.5), seed=7).observe()
        assert obs.current_state["regions"]["Lora"]["label"] == "west"

    def test_measurement_data_is_noised(self):
        session = AgentSession(_scenario(observation_noise=0.5), seed=7)
        truth = _readings(session.simulator.observable_state())
        result = session.act(Action("observe", kind="measurement"))
        data = _readings(result.data)
        assert any(data[p] != truth[p] for p in truth)


# === Seed-deterministic ===

class TestSeedDeterminism:

    def test_same_seed_same_level_identical_readings(self):
        a = AgentSession(_scenario(observation_noise=0.3), seed=42).observe()
        b = AgentSession(_scenario(observation_noise=0.3), seed=42).observe()
        assert a.current_state == b.current_state

    def test_different_seed_different_readings(self):
        a = AgentSession(_scenario(observation_noise=0.3), seed=1).observe()
        b = AgentSession(_scenario(observation_noise=0.3), seed=2).observe()
        assert a.current_state != b.current_state

    def test_reobserving_same_step_reproduces_readings(self):
        session = AgentSession(_scenario(observation_noise=0.3), seed=42)
        assert session.observe().current_state == session.observe().current_state


# === Magnitude scales with the level ===

class TestMagnitudeScales:

    def test_larger_level_larger_perturbation_per_reading(self):
        truth = _readings(AgentSession(_scenario(), seed=9).observe().current_state)
        low = _readings(
            AgentSession(_scenario(observation_noise=0.1), seed=9)
            .observe().current_state
        )
        high = _readings(
            AgentSession(_scenario(observation_noise=0.8), seed=9)
            .observe().current_state
        )
        # eps is drawn independently of the level, so per reading the
        # perturbation is exactly |truth| * level * |eps| — monotone in level.
        for path, true_val in truth.items():
            assert abs(high[path] - true_val) >= abs(low[path] - true_val)
        assert sum(abs(high[p] - truth[p]) for p in truth) > \
            sum(abs(low[p] - truth[p]) for p in truth)


# === Ground truth untouched ===

class TestGroundTruthUntouched:

    def test_world_state_unchanged_after_noised_observation(self):
        session = AgentSession(_scenario(observation_noise=0.5), seed=7)
        before = copy.deepcopy(session.simulator.observable_state())
        session.observe()
        session.act(Action("observe", kind="measurement"))
        session.observe()
        assert session.simulator.observable_state() == before

    def test_noised_state_is_a_distinct_structure(self):
        session = AgentSession(_scenario(observation_noise=0.5), seed=7)
        obs = session.observe()
        # Mutating the observed copy must not leak into ground truth.
        obs.current_state["regions"]["Lora"]["substrate"]["M1"] = -999.0
        truth = session.simulator.observable_state()
        assert truth["regions"]["Lora"]["substrate"]["M1"] == 10.0


# === Malformed levels raise — no silent clamp/fallback ===

class TestBadLevelRaises:

    def test_negative_level_raises(self):
        with pytest.raises(ValueError):
            AgentSession(_scenario(observation_noise=-0.1), seed=7)

    def test_non_numeric_level_raises(self):
        with pytest.raises(TypeError):
            AgentSession(_scenario(observation_noise="high"), seed=7)

    def test_bool_level_raises(self):
        with pytest.raises(TypeError):
            AgentSession(_scenario(observation_noise=True), seed=7)

    def test_nan_level_raises(self):
        with pytest.raises(ValueError):
            AgentSession(_scenario(observation_noise=float("nan")), seed=7)

    def test_inf_level_raises(self):
        with pytest.raises(ValueError):
            AgentSession(_scenario(observation_noise=float("inf")), seed=7)
