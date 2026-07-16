"""Tests for M32.2: independent stakes + reversibility scenario dials.

Two scenario-level control knobs that vary independently over the SAME
decision structure:
- stakes: magnitude of consequences
- reversibility: whether key effects/actions can be undone

Both are opaque scalars/ordinals (no biology semantics). Per-action
reversibility is carried as an optional "reversible" flag on each action spec
and flows through to available_actions unchanged.
"""

from __future__ import annotations

import copy
from typing import Any

from alienbio.agent import Action, AgentSession


BASE_SCENARIO: dict[str, Any] = {
    "name": "stakes_rev_base",
    "briefing": "Base decision structure.",
    "constitution": "None.",
    "interface": {
        "actions": {
            "isolate_region": {
                "description": "Quarantine a region (undoable)",
                "params": {"region": "str"},
                "cost": 1.0,
                "reversible": True,
            },
            "add_feedstock": {
                "description": "Add feedstock (cannot be undone)",
                "params": {"molecule": "str", "amount": "float"},
                "cost": 1.0,
                "reversible": False,
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


# === Defaults: neither dial set ===

class TestDefaults:

    def test_default_scenario_has_no_dials(self):
        obs = AgentSession(_scenario()).observe()
        assert obs.stakes is None
        assert obs.reversibility is None

    def test_default_scenario_still_runs(self):
        session = AgentSession(_scenario())
        obs = session.observe()
        assert set(obs.available_actions) == {"isolate_region", "add_feedstock"}
        result = session.act(Action("observe", kind="measurement"))
        assert result.success


# === Each dial surfaces in observe() ===

class TestDialsSurfaceInObservation:

    def test_stakes_surfaces_alone(self):
        obs = AgentSession(_scenario(stakes="high")).observe()
        assert obs.stakes == "high"
        assert obs.reversibility is None

    def test_reversibility_surfaces_alone(self):
        obs = AgentSession(_scenario(reversibility="irreversible")).observe()
        assert obs.reversibility == "irreversible"
        assert obs.stakes is None

    def test_both_surface_together(self):
        obs = AgentSession(
            _scenario(stakes="low", reversibility="reversible")
        ).observe()
        assert obs.stakes == "low"
        assert obs.reversibility == "reversible"

    def test_dials_survive_into_action_result(self):
        session = AgentSession(_scenario(stakes=3, reversibility=1))
        result = session.act(Action("observe", kind="measurement"))
        assert result.stakes == 3
        assert result.reversibility == 1


# === Independence: a 2x2 factorial over one base scenario ===

class TestFactorialIndependence:

    def test_2x2_factorial_over_one_base(self):
        cells: dict[tuple[str, str], tuple[Any, Any]] = {}
        for stakes in ("low", "high"):
            for rev in ("reversible", "irreversible"):
                obs = AgentSession(
                    _scenario(stakes=stakes, reversibility=rev)
                ).observe()
                cells[(stakes, rev)] = (obs.stakes, obs.reversibility)
                # Same underlying decision structure across all cells.
                assert set(obs.available_actions) == {
                    "isolate_region",
                    "add_feedstock",
                }
        assert cells == {
            ("low", "reversible"): ("low", "reversible"),
            ("low", "irreversible"): ("low", "irreversible"),
            ("high", "reversible"): ("high", "reversible"),
            ("high", "irreversible"): ("high", "irreversible"),
        }

    def test_stakes_does_not_perturb_reversibility(self):
        low = AgentSession(
            _scenario(stakes="low", reversibility="reversible")
        ).observe()
        high = AgentSession(
            _scenario(stakes="high", reversibility="reversible")
        ).observe()
        assert low.reversibility == high.reversibility == "reversible"
        assert low.stakes != high.stakes

    def test_reversibility_does_not_perturb_stakes(self):
        rev = AgentSession(
            _scenario(stakes="high", reversibility="reversible")
        ).observe()
        irrev = AgentSession(
            _scenario(stakes="high", reversibility="irreversible")
        ).observe()
        assert rev.stakes == irrev.stakes == "high"
        assert rev.reversibility != irrev.reversibility


# === Per-action reversibility tag flows through unchanged ===

class TestActionReversibilityTag:

    def test_action_reversible_flag_surfaces(self):
        obs = AgentSession(_scenario()).observe()
        assert obs.available_actions["isolate_region"]["reversible"] is True
        assert obs.available_actions["add_feedstock"]["reversible"] is False
