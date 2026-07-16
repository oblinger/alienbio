"""Tests for constitution / objective injection (M30.1).

A scenario may declare an agent-facing constitution — either legacy free-form
text or a structured spec (objectives, prohibitions, priority ordering).
AgentSession surfaces it verbatim on every observation.
"""

from __future__ import annotations

import pytest

from alienbio.agent.session import AgentSession
from alienbio.agent.types import Action, Constitution, coerce_constitution


STRUCTURED_CONSTITUTION = {
    "objectives": ["Stabilize the ecosystem", "Characterize unknown species"],
    "prohibitions": ["Do not exterminate any population", "Do not exceed budget"],
    "priorities": ["Safety", "Knowledge", "Efficiency"],
}


def make_scenario(**overrides) -> dict:
    """Minimal scenario for constitution testing."""
    scenario = {
        "name": "constitution_test",
        "briefing": "Test the constitution plumbing.",
        "interface": {
            "actions": {
                "poke": {"description": "Poke the world", "params": {}, "cost": 1.0}
            },
            "measurements": {},
            "budget": 10,
        },
        "sim": {"max_agent_steps": 5},
    }
    scenario.update(overrides)
    return scenario


class TestConstitutionInjection:
    """Scenario-declared constitutions surface through observe()."""

    def test_structured_constitution_surfaces_verbatim(self):
        """A structured constitution appears verbatim in observe().constitution."""
        session = AgentSession(make_scenario(constitution=STRUCTURED_CONSTITUTION))
        obs = session.observe()
        assert isinstance(obs.constitution, Constitution)
        assert obs.constitution.objectives == STRUCTURED_CONSTITUTION["objectives"]
        assert obs.constitution.prohibitions == STRUCTURED_CONSTITUTION["prohibitions"]
        assert obs.constitution.priorities == STRUCTURED_CONSTITUTION["priorities"]

    def test_string_constitution_passes_through(self):
        """Legacy free-form string constitutions pass through unchanged."""
        session = AgentSession(make_scenario(constitution="Do no harm."))
        assert session.observe().constitution == "Do no harm."

    def test_missing_constitution_yields_empty_default(self):
        """A scenario without a constitution yields the empty string."""
        session = AgentSession(make_scenario())
        assert session.observe().constitution == ""

    def test_priority_ordering_round_trips(self):
        """Priority order is preserved exactly as declared."""
        priorities = ["Third", "First", "Second"]
        session = AgentSession(make_scenario(constitution={"priorities": priorities}))
        obs = session.observe()
        assert isinstance(obs.constitution, Constitution)
        assert obs.constitution.priorities == priorities

    def test_constitution_stable_across_turns(self):
        """The constitution is surfaced on every turn, including ActionResults."""
        session = AgentSession(make_scenario(constitution=STRUCTURED_CONSTITUTION))
        first = session.observe().constitution
        result = session.act(Action(name="poke"))
        second = session.observe().constitution
        assert result.constitution == first
        assert second == first

    def test_scenario_change_reflected_next_turn(self):
        """If the scenario's constitution changes, observe() picks it up."""
        scenario = make_scenario(constitution="Old rules.")
        session = AgentSession(scenario)
        assert session.observe().constitution == "Old rules."
        scenario["constitution"] = {"objectives": ["New objective"]}
        obs = session.observe()
        assert isinstance(obs.constitution, Constitution)
        assert obs.constitution.objectives == ["New objective"]


class TestCoerceConstitution:
    """Coercion of scenario-level constitution specs."""

    def test_none_becomes_empty_string(self):
        assert coerce_constitution(None) == ""

    def test_constitution_instance_passes_through(self):
        const = Constitution(objectives=["X"])
        assert coerce_constitution(const) is const

    def test_partial_dict_defaults_missing_lists(self):
        const = coerce_constitution({"objectives": ["Only objective"]})
        assert isinstance(const, Constitution)
        assert const.objectives == ["Only objective"]
        assert const.prohibitions == []
        assert const.priorities == []

    def test_unknown_keys_rejected(self):
        with pytest.raises(ValueError, match="Unknown constitution keys"):
            coerce_constitution({"objectives": [], "mandates": ["nope"]})

    def test_invalid_type_rejected(self):
        with pytest.raises(TypeError, match="Invalid constitution spec type"):
            coerce_constitution(42)

    def test_str_rendering_includes_all_sections(self):
        text = str(coerce_constitution(STRUCTURED_CONSTITUTION))
        assert "Stabilize the ecosystem" in text
        assert "Do not exterminate any population" in text
        assert text.index("Safety") < text.index("Knowledge") < text.index("Efficiency")
