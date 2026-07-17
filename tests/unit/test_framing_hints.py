"""Tests for M32.6: explicit-hint / framing-variation dial.

The scenario-level "framing" key varies the wording of Observation.briefing
and/or appends explicit hints, WITHOUT changing world dynamics or the
grading oracle. Same world, different framing/hints surfaced to the agent.

Supported framing keys (all opaque text, no biology semantics):
- briefing: replacement wording for the base briefing
- hints: list of hint strings, each surfaced verbatim

Guarantees under test:
- absent framing => briefing byte-identical to today (identity)
- hint text appears verbatim in the surfaced briefing
- world dynamics and scoring are IDENTICAL with vs without framing
- composition is deterministic (no hidden randomness)
- malformed framing config RAISES at session construction — no silent fallback
"""

from __future__ import annotations

import copy
from typing import Any

import pytest

from alienbio.agent import Action, AgentSession, compose_briefing


BASE_BRIEFING = "Stabilize the M1 substrate level in region Lora."

BASE_SCENARIO: dict[str, Any] = {
    "name": "framing_base",
    "briefing": BASE_BRIEFING,
    "constitution": "None.",
    "interface": {
        "actions": {
            "isolate_region": {
                "description": "Quarantine a region",
                "params": {"region": "str"},
                "cost": 1.0,
            },
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
    "containers": {"regions": {"Lora": {"substrate": {"M1": 10.0}}}},
    "scoring": {},
    "passing_score": 0.6,
}


def _scenario(**overrides: Any) -> dict[str, Any]:
    """Deep-copy the base scenario and set top-level key overrides."""
    s = copy.deepcopy(BASE_SCENARIO)
    s.update(overrides)
    return s


def _run_fixed_episode(scenario: dict[str, Any], seed: int = 42) -> dict[str, Any]:
    """Run a fixed action sequence and capture everything the dial must NOT change."""
    session = AgentSession(scenario, seed=seed)
    states: list[dict[str, Any]] = []
    outcomes: list[tuple[bool, Any, float]] = []
    for action in (
        Action("observe", kind="measurement"),
        Action("isolate_region", params={"region": "Lora"}),
        Action("add_feedstock", params={"molecule": "M1", "amount": 2.0}),
        Action("observe", kind="measurement"),
    ):
        result = session.act(action)
        outcomes.append((result.success, result.data, result.cost))
        states.append(copy.deepcopy(session.observe().current_state))
    final = session.observe()
    results = session.results()
    return {
        "briefing": final.briefing,
        "states": states,
        "outcomes": outcomes,
        "scores": session.score(),
        "passed": results.passed,
        "spent": final.spent,
    }


# === Absent = identity ===

class TestAbsentIsIdentity:

    def test_no_framing_key_briefing_byte_identical(self):
        obs = AgentSession(_scenario()).observe()
        assert obs.briefing == BASE_BRIEFING

    def test_framing_none_briefing_byte_identical(self):
        obs = AgentSession(_scenario(framing=None)).observe()
        assert obs.briefing == BASE_BRIEFING

    def test_empty_framing_dict_is_identity(self):
        obs = AgentSession(_scenario(framing={})).observe()
        assert obs.briefing == BASE_BRIEFING

    def test_empty_hints_list_is_identity(self):
        obs = AgentSession(_scenario(framing={"hints": []})).observe()
        assert obs.briefing == BASE_BRIEFING


# === Hint text surfaces verbatim ===

class TestHintsSurfaceVerbatim:

    def test_single_hint_appears_verbatim(self):
        hint = "The M2 pathway saturates above concentration 5.0."
        obs = AgentSession(_scenario(framing={"hints": [hint]})).observe()
        assert hint in obs.briefing
        assert obs.briefing.startswith(BASE_BRIEFING)

    def test_multiple_hints_all_appear_in_order(self):
        hints = ["First: check the substrate.", "Second: isolate before adding."]
        obs = AgentSession(_scenario(framing={"hints": hints})).observe()
        positions = [obs.briefing.index(h) for h in hints]
        assert positions == sorted(positions)

    def test_reworded_briefing_replaces_base(self):
        reworded = "URGENT: region Lora is failing — act to hold M1 steady."
        obs = AgentSession(_scenario(framing={"briefing": reworded})).observe()
        assert obs.briefing == reworded
        assert BASE_BRIEFING not in obs.briefing

    def test_rewording_plus_hints_compose(self):
        reworded = "Keep M1 steady in Lora."
        hint = "Feedstock additions cannot be undone."
        obs = AgentSession(
            _scenario(framing={"briefing": reworded, "hints": [hint]})
        ).observe()
        assert obs.briefing.startswith(reworded)
        assert hint in obs.briefing

    def test_framed_briefing_surfaces_in_action_results_too(self):
        hint = "Measurements are free."
        session = AgentSession(_scenario(framing={"hints": [hint]}))
        result = session.act(Action("observe", kind="measurement"))
        assert hint in result.briefing
        assert result.briefing == session.observe().briefing


# === Dynamics + oracle unchanged ===

class TestDynamicsAndOracleUnchanged:

    def test_framing_changes_only_the_briefing(self):
        baseline = _run_fixed_episode(_scenario())
        framed = _run_fixed_episode(_scenario(framing={
            "briefing": "Reworded: hold M1 level steady in region Lora.",
            "hints": ["Isolation is cheap.", "Feedstock is irreversible."],
        }))
        # Only the briefing text differs...
        assert framed["briefing"] != baseline["briefing"]
        # ...world dynamics are identical...
        assert framed["states"] == baseline["states"]
        assert framed["outcomes"] == baseline["outcomes"]
        assert framed["spent"] == baseline["spent"]
        # ...and the grading oracle is identical.
        assert framed["scores"] == baseline["scores"]
        assert framed["passed"] == baseline["passed"]

    def test_hints_only_variant_also_leaves_oracle_unchanged(self):
        baseline = _run_fixed_episode(_scenario())
        hinted = _run_fixed_episode(_scenario(framing={"hints": ["A hint."]}))
        assert hinted["states"] == baseline["states"]
        assert hinted["scores"] == baseline["scores"]
        assert hinted["passed"] == baseline["passed"]


# === Deterministic / reproducible ===

class TestReproducible:

    def test_same_seed_same_framing_identical_episode(self):
        framing = {"briefing": "Variant wording.", "hints": ["h1", "h2"]}
        run_a = _run_fixed_episode(_scenario(framing=framing), seed=7)
        run_b = _run_fixed_episode(_scenario(framing=framing), seed=7)
        assert run_a == run_b

    def test_composition_is_pure(self):
        framing = {"hints": ["stable hint"]}
        assert (
            compose_briefing(BASE_BRIEFING, framing)
            == compose_briefing(BASE_BRIEFING, framing)
        )


# === Bad config raises — no silent fallback ===

class TestBadConfigRaises:

    def test_non_dict_framing_raises(self):
        with pytest.raises(TypeError, match="framing"):
            AgentSession(_scenario(framing="just a string"))

    def test_unknown_framing_key_raises(self):
        with pytest.raises(ValueError, match="Unknown framing keys"):
            AgentSession(_scenario(framing={"hintz": ["typo"]}))

    def test_non_str_briefing_raises(self):
        with pytest.raises(TypeError, match="briefing"):
            AgentSession(_scenario(framing={"briefing": 42}))

    def test_hints_not_a_list_raises(self):
        with pytest.raises(TypeError, match="hints"):
            AgentSession(_scenario(framing={"hints": "one bare string"}))

    def test_non_str_hint_element_raises(self):
        with pytest.raises(TypeError, match="hints"):
            AgentSession(_scenario(framing={"hints": ["ok", 3.14]}))

    def test_raises_at_construction_not_first_observe(self):
        # Malformed config must fail fast, before any interaction happens.
        with pytest.raises(ValueError):
            AgentSession(_scenario(framing={"bogus": True}))
