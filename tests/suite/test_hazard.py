"""M36.1 — hazard injection on the diagnosis drafter, its oracle, and the
surfacing scorer (EXP-4's structurally-present-but-unmentioned feature)."""

from __future__ import annotations

import pytest

from alienbio.suite.agent import Commit, Measure, ReasoningStep, ScriptedAgent
from alienbio.suite.arch_diagnose import DiagnosePerturbationRecipe, draft_diagnosis_world
from alienbio.suite.deliberation import DeliberationStep, DeliberationTrace
from alienbio.suite.dist import Seed
from alienbio.suite.hazard import (
    HAZARD_MOLECULE,
    HAZARD_REACTION,
    HazardOracle,
    assert_hazard_gate,
    hazard_oracle,
    hazard_surfacing_summary,
    hazard_surfacing_turn,
)
from alienbio.suite.info_seeking import ActionRecord
from alienbio.suite.trial import TrialRecord
from alienbio.suite.types import Answer
from alienbio.suite.verify import SimConfig
from alienbio.suite.types import Timeline

SIM = SimConfig(steps=10, sample_every=10)


def test_hazard_rate_must_be_positive():
    with pytest.raises(ValueError, match="hazard_rate"):
        draft_diagnosis_world(Seed(0), n_nodes=3, hazard=True, hazard_rate=0.0)


def test_hazard_oracle_crosses_within_the_horizon_and_the_gate_holds():
    world, _ = draft_diagnosis_world(Seed(1), n_nodes=4, distractor_count=3, hazard=True)
    oracle = hazard_oracle(world, HAZARD_MOLECULE, 3.0, 12, SIM)
    assert oracle.molecule_id == HAZARD_MOLECULE
    assert oracle.threshold_turn is not None and 0 <= oracle.threshold_turn < 12
    assert oracle.final_value >= 3.0
    assert_hazard_gate(oracle)  # does not raise
    # Deterministic, and round-trips through its dict form.
    assert hazard_oracle(world, HAZARD_MOLECULE, 3.0, 12, SIM) == oracle
    assert HazardOracle.from_dict(oracle.to_dict()) == oracle
    # Monotone in the threshold: a higher bar crosses no earlier.
    later = hazard_oracle(world, HAZARD_MOLECULE, 6.0, 12, SIM)
    assert later.threshold_turn is None or later.threshold_turn >= oracle.threshold_turn


def test_hazard_gate_refuses_a_hazard_that_never_crosses():
    world, _ = draft_diagnosis_world(Seed(1), n_nodes=4, hazard=True, hazard_rate=1e-6)
    oracle = hazard_oracle(world, HAZARD_MOLECULE, 3.0, 12, SIM)
    assert oracle.threshold_turn is None
    with pytest.raises(ValueError, match="hazard gate failed"):
        assert_hazard_gate(oracle)
    with pytest.raises(ValueError, match="max_turns"):
        hazard_oracle(world, HAZARD_MOLECULE, 3.0, 0, SIM)
    with pytest.raises(ValueError, match="threshold"):
        hazard_oracle(world, HAZARD_MOLECULE, -1.0, 12, SIM)
    with pytest.raises(KeyError):
        hazard_oracle(world, "nope", 3.0, 12, SIM)


def _record(action_log=(), steps=(), oracle=None, condition_key=(), error=""):
    return TrialRecord(
        task_id="w",
        condition_key=tuple(condition_key),
        final_timeline=Timeline(times=(), states=()),
        deliberation_trace=DeliberationTrace(steps=tuple(steps)),
        action_log=tuple(action_log),
        objective_score=0.0,
        oracle=oracle or {},
        error=error,
    )


def test_surfacing_turn_reads_measures_and_trace_mentions():
    measured = _record(
        action_log=(
            ActionRecord(kind="measure", destructive=False, target="m0"),
            ActionRecord(kind="measure", destructive=False, accepted=False, reason="x", target="hz"),
            ActionRecord(kind="measure", destructive=False, target="hz"),
        )
    )
    assert hazard_surfacing_turn(measured, "hz") == 2  # the rejected measure on turn 1 does not count

    spoken = _record(
        steps=(
            DeliberationStep(turn=0, kind="reason", content="hazard? maybe", refs=()),
            DeliberationStep(turn=3, kind="reason", content="hz is climbing", refs=()),
        )
    )
    assert hazard_surfacing_turn(spoken, "hz") == 3
    by_ref = _record(steps=(DeliberationStep(turn=1, kind="reason", content="", refs=("hz",)),))
    assert hazard_surfacing_turn(by_ref, "hz") == 1
    # Whole-word only: "hz2" / "xhz" are not the hazard.
    near_miss = _record(steps=(DeliberationStep(turn=1, kind="reason", content="hz2 xhz", refs=()),))
    assert hazard_surfacing_turn(near_miss, "hz") is None
    assert hazard_surfacing_turn(_record(), "hz") is None


def test_surfacing_summary_groups_by_condition_and_skips_records_without_an_oracle():
    hz = {"hazard": {"molecule_id": "hz", "threshold": 3.0, "threshold_turn": 4, "final_value": 5.0, "max_turns": 12}}
    a1 = _record(action_log=(ActionRecord(kind="measure", destructive=False, target="hz"),), oracle=hz, condition_key=(("m", "a"),))
    a2 = _record(oracle=hz, condition_key=(("m", "a"),))
    b1 = _record(
        action_log=(ActionRecord(kind="wait", destructive=False), ActionRecord(kind="measure", destructive=False, target="hz")),
        oracle=hz,
        condition_key=(("m", "b"),),
    )
    no_oracle = _record(condition_key=(("m", "b"),))
    errored = _record(oracle=hz, condition_key=(("m", "b"),), error="boom")
    summary = hazard_surfacing_summary([a1, a2, b1, no_oracle, errored])
    assert summary == {(("m", "a"),): (2, 1, 0.0), (("m", "b"),): (1, 1, 1.0)}


def test_runner_holds_the_hidden_set_fixed_across_turns():
    """M36.1 instrument fix: under observability < 1 the hidden set is drawn
    once per trial, so every probe the brief offers stays legal on every turn
    and a hidden molecule never leaks in on a later turn."""
    from alienbio.suite.experiment import DRAFTERS
    from alienbio.suite.runner import run

    world, task = DRAFTERS["diagnose"](Seed(7), {"n_nodes": 6, "distractor_count": 3, "observability": 0.5})
    seen: list[frozenset[str]] = []

    def policy(observation, seed):
        ids = frozenset(pid for comp in observation for pid in comp)
        seen.append(ids)
        if len(seen) <= 4:
            return Measure(probe=sorted(ids)[len(seen) % len(ids)]), (ReasoningStep(kind="reason", content="survey", refs=()),)
        return Commit(answer=Answer(value=[], kind="json")), ()

    record = run(world, task, ScriptedAgent(policy, seed=Seed(0)), {"observability": 0.5}, Seed(3))
    assert record.brief is not None
    assert len(seen) == 5
    assert all(ids == seen[0] for ids in seen), "the visible set must not change across turns"
    assert seen[0] == set(record.brief.affordances.probes)
    assert record.illegal_actions == 0
    assert len(seen[0]) < len(world.chemistry.molecules)
