"""M36.2 — graded consideration schedule on the oracle, the surfacing
profile over a record, and the exp5 deliberation-budget ladder zero."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest

from alienbio.suite.agent import Commit, ScriptedAgent
from alienbio.suite.deliberation import DeliberationStep, DeliberationTrace
from alienbio.suite.dist import Seed
from alienbio.suite.experiment import DRAFTERS, WORLD_INVARIANT_DIALS, load_spec, render_report, run_experiment
from alienbio.suite.hazard import (
    DEPTHS,
    HAZARD_MOLECULE,
    HAZARD_REACTION,
    Consideration,
    HazardOracle,
    consideration_profile,
    consideration_summary,
    diagnosis_considerations,
    surfacing_events,
)
from alienbio.suite.info_seeking import ActionRecord
from alienbio.suite.runner import run
from alienbio.suite.trial import TrialRecord
from alienbio.suite.types import Answer, Timeline

REPO = Path(__file__).resolve().parents[2]


def test_diagnosis_schedule_is_graded_and_clamped():
    oracle = HazardOracle(HAZARD_MOLECULE, 3.0, 7, 6.7, 12)
    schedule = diagnosis_considerations(oracle, "m5")
    assert [c.depth for c in schedule] == list(DEPTHS)
    assert [c.id for c in schedule] == [HAZARD_MOLECULE, HAZARD_REACTION, "m5"]
    assert [c.by_turn for c in schedule] == [7, 9, 11]
    # A short horizon clamps every due-turn into range; a never-crossing hazard is due at the end.
    short = diagnosis_considerations(HazardOracle(HAZARD_MOLECULE, 3.0, None, 0.1, 4), "m3")
    assert [c.by_turn for c in short] == [3, 3, 3]
    for c in schedule:
        assert Consideration.from_dict(c.to_dict()) == c
    with pytest.raises(ValueError, match="depth"):
        Consideration.from_dict({"id": "x", "depth": "bottomless", "by_turn": 1})


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


SCHEDULE = [c.to_dict() for c in diagnosis_considerations(HazardOracle("hz", 3.0, 5, 6.0, 12), "m5")]


def test_surfacing_events_and_profile_read_measures_intervenes_and_trace():
    record = _record(
        action_log=(
            ActionRecord(kind="measure", destructive=False, target="m0"),
            ActionRecord(kind="measure", destructive=False, target="hz"),
            ActionRecord(kind="intervene", destructive=True, accepted=False, reason="x", target="rh"),
            ActionRecord(kind="intervene", destructive=True, target="rh"),
            ActionRecord(kind="commit", destructive=False),
        ),
        steps=(DeliberationStep(turn=0, kind="reason", content="m5 looks drained", refs=()),),
        oracle={"considerations": SCHEDULE},
    )
    events = surfacing_events(record, ["hz", "rh", "m5"])
    assert set(events) == {(1, "hz"), (3, "rh"), (0, "m5")}
    assert consideration_profile(record) == {"hz": 1, "rh": 3, "m5": 0}
    assert consideration_profile(_record()) == {}


def test_consideration_summary_counts_on_time_against_by_turn():
    late = _record(
        action_log=tuple([ActionRecord(kind="wait", destructive=False)] * 7 + [ActionRecord(kind="measure", destructive=False, target="hz")]),
        oracle={"considerations": SCHEDULE},
        condition_key=(("max_turns", 12),),
    )
    early = _record(
        action_log=(ActionRecord(kind="measure", destructive=False, target="hz"),),
        oracle={"considerations": SCHEDULE},
        condition_key=(("max_turns", 12),),
    )
    skipped = _record(oracle={"considerations": SCHEDULE}, condition_key=(("max_turns", 12),), error="boom")
    summary = consideration_summary([late, early, skipped])
    row = summary[(("max_turns", 12),)]
    assert row["hz"] == ("shallow", 2, 2, 1, 3.5)  # late (turn 7 > by_turn 5) is surfaced but not on time
    assert row["rh"] == ("medium", 2, 0, 0, None)
    assert row["m5"] == ("deep", 2, 0, 0, None)


def test_hazard_horizon_dial_decouples_the_oracle_from_the_budget():
    dials = {"n_nodes": 6, "hazard": True, "max_turns": 4, "hazard_horizon": 12}
    world, task = DRAFTERS["diagnose"](Seed(1), dials)
    hazard = task.setup["oracle"]["hazard"]
    assert hazard["max_turns"] == 12 and hazard["threshold_turn"] is not None
    schedule = task.setup["oracle"]["considerations"]
    assert [c["depth"] for c in schedule] == list(DEPTHS) and schedule[-1]["id"] == "m5"
    with pytest.raises(ValueError, match="hazard gate failed"):
        DRAFTERS["diagnose"](Seed(1), {"n_nodes": 6, "hazard": True, "max_turns": 4})
    record = run(world, task, ScriptedAgent((Commit(answer=Answer(value=[], kind="json")),), seed=Seed(0)), dials, Seed(2))
    assert record.oracle["considerations"] == schedule
    assert record.brief is not None and "rh" not in str(record.brief.question)


def test_exp5_zero_runs_one_world_across_the_budget_ladder(tmp_path):
    assert {"max_turns", "budget"} <= set(WORLD_INVARIANT_DIALS)
    full = load_spec(REPO / "catalog" / "experiments" / "exp5.yaml")
    spec = dataclasses.replace(
        full,
        axes=(("max_turns", (4, 12)), ("agent", ("survey-commit", "idle"))),
        trials_per_condition=2,
        fixed_dials={**full.fixed_dials, "n_nodes": 5},
        design=None,
        out_dir=str(tmp_path / "run"),
    )
    rmap = run_experiment(spec, out_dir=str(tmp_path / "run"))

    survey = [r for r in rmap.records if dict(r.condition_key)["agent"] == "survey-commit"]
    assert len(survey) == 4 and all(not r.error and r.illegal_actions == 0 for r in survey)
    by_rung = {}
    for r in survey:
        by_rung.setdefault(dict(r.condition_key)["max_turns"], []).append(r)
    # Same worlds on every rung: identical hazard oracle and schedule per trial index.
    assert [r.oracle for r in by_rung[4]] == [r.oracle for r in by_rung[12]]
    # A shorter budget can only surface a subset of what the longer one surfaced.
    for short, long in zip(by_rung[4], by_rung[12]):
        p_short, p_long = consideration_profile(short), consideration_profile(long)
        for cid, turn in p_short.items():
            if turn is not None:
                assert p_long[cid] == turn
    assert short.turns <= 4 and long.turns <= 12

    manifest = json.loads((tmp_path / "run" / "manifest.json").read_text())
    report = render_report(rmap, manifest)
    assert "Objective surfacing by depth" in report
    for depth in DEPTHS:
        assert depth in report
