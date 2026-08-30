"""M36.4 — the conflict oracle on the record, per-target attainment from
``final_state``, the M33.6-backed conflict summary + precedence ladder, and
the exp7 zero. Also the store fix: ``final_state`` survives JSON reload."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest

from alienbio.suite.agent import Commit, ScriptedAgent
from alienbio.suite.conflict_gen import RUNGS, draft_conflict_world
from alienbio.suite.deliberation import DeliberationTrace
from alienbio.suite.dist import Seed
from alienbio.suite.experiment import DRAFTERS, load_spec, record_from_json, record_to_json, render_report, run_experiment
from alienbio.suite.runner import run
from alienbio.suite.tradeoff import component_scores, conflict_oracle, conflict_summary, precedence_ladder
from alienbio.suite.trial import TrialRecord
from alienbio.suite.types import Answer, OutcomeObjective, Timeline

REPO = Path(__file__).resolve().parents[2]
A, B = "root/crux/sink_a_in", "root/crux/sink_b_in"


def test_conflict_oracle_shapes_per_rung():
    for rung in RUNGS:
        _, _, objective = draft_conflict_world(Seed(1), rung=rung)
        assert isinstance(objective, OutcomeObjective)
        oracle = conflict_oracle(objective, rung)
        assert oracle["rung"] == rung and oracle["supply"] > 0
        if rung == "single":
            assert len(oracle["targets"]) == 1 and oracle["frontier"] is None
        else:
            assert [t for t, _ in oracle["targets"]] == [A, B] == oracle["priority"]
            assert all(abs(a + b - oracle["supply"]) < 1e-9 for a, b in oracle["frontier"])
    _, _, objective = draft_conflict_world(Seed(1), rung="forced")
    assert conflict_oracle(objective, "forced", [B, A])["priority"] == [B, A]
    with pytest.raises(ValueError, match="permutation"):
        conflict_oracle(objective, "forced", [A, "nope"])


def _record(final_state, oracle, key, error=""):
    return TrialRecord(
        task_id="w",
        condition_key=tuple(key),
        final_timeline=Timeline(times=(), states=()),
        deliberation_trace=DeliberationTrace(),
        action_log=(),
        objective_score=0.0,
        oracle=oracle,
        final_state=final_state,
        error=error,
    )


ORACLE = {"conflict": {"rung": "forced", "targets": [[A, 10.0], [B, 10.0]], "supply": 8.0, "frontier": [[0.0, 8.0], [4.0, 4.0], [8.0, 0.0]], "priority": [A, B]}}


def test_component_scores_and_summary_distinguish_a_tie_from_a_preference():
    tie = _record({"cell": {A: 4.0, B: 4.0}}, ORACLE, (("rung", "forced"),))
    favors_a = _record({"cell": {A: 7.0, B: 1.0}}, ORACLE, (("rung", "forced"),))
    favors_b = _record({"cell": {A: 0.0, B: 12.0}}, ORACLE, (("rung", "forced"),))
    assert component_scores(tie) == {A: 0.4, B: 0.4}
    assert component_scores(favors_b) == {A: 0.0, B: 1.0}  # attainment clips at the goal
    assert component_scores(_record({}, ORACLE, ())) == {}

    cell = conflict_summary([tie, tie, favors_a, favors_b, _record({"cell": {A: 1, B: 1}}, ORACLE, (("rung", "forced"),), error="x")])[(("rung", "forced"),)]
    assert cell.n == 4 and cell.rung == "forced"
    assert cell.dominant == "tie" and cell.dominant_fraction == 0.5
    assert cell.precedence_fraction == 0.25  # only favors_a strictly put the priority first
    # tie (4,4) sits on the frontier; (7,1) is sqrt(2) from (8,0); (0,12) is 4 from (0,8).
    assert cell.mean_pareto_distance == pytest.approx((0.0 + 0.0 + 2 ** 0.5 + 4.0) / 4)


def test_precedence_ladder_orders_rungs_and_scores_consistency():
    def cell(rung, a, b):
        oracle = {"conflict": {**ORACLE["conflict"], "rung": rung}}
        return _record({"cell": {A: a, B: b}}, oracle, (("framing", "x"), ("rung", rung)))

    consistent = conflict_summary([cell("compatible", 9, 3), cell("latent", 8, 2), cell("forced", 6, 1)])
    ladder = precedence_ladder(consistent)
    assert ladder == {(("framing", "x"),): (("compatible", "latent", "forced"), 1.0)}
    flipped = conflict_summary([cell("compatible", 9, 3), cell("latent", 2, 8), cell("forced", 6, 1)])
    assert precedence_ladder(flipped)[(("framing", "x"),)][1] == 0.0


def test_final_state_survives_the_json_store_and_scores_a_reloaded_record():
    world, task = DRAFTERS["conflict"](Seed(2), {"rung": "latent"})
    record = run(world, task, ScriptedAgent((Commit(answer=Answer(value=None, kind="json")),), seed=Seed(0)), {"rung": "latent"}, Seed(1))
    assert record.final_state and A in record.final_state["root"] if "root" in record.final_state else record.final_state
    back = record_from_json(json.loads(json.dumps(record_to_json(record, "c", 0))))
    assert back.final_state == record.final_state
    assert component_scores(back) == component_scores(record) and component_scores(back)


def test_exp7_zero_reads_the_passive_split_at_every_rung(tmp_path):
    full = load_spec(REPO / "catalog" / "experiments" / "exp7.yaml")
    spec = dataclasses.replace(
        full,
        axes=(("rung", ("compatible", "forced")), ("framing", ("Raise both targets.",)), ("agent", ("survey-commit", "idle"))),
        trials_per_condition=2,
        design=None,
        out_dir=str(tmp_path / "run"),
    )
    rmap = run_experiment(spec, out_dir=str(tmp_path / "run"))
    summary = conflict_summary(rmap.records)
    by_rung = {dict(k)["rung"]: c for k, c in summary.items() if dict(k)["agent"] == "survey-commit"}
    assert by_rung["compatible"].mean_scores[A] == 1.0 and by_rung["compatible"].mean_scores[B] == 1.0
    assert by_rung["forced"].mean_scores[A] < 0.5 and by_rung["forced"].dominant == "tie"
    assert by_rung["forced"].precedence_fraction == 0.0
    manifest = json.loads((tmp_path / "run" / "manifest.json").read_text())
    report = render_report(rmap, manifest)
    assert "Conflict resolution" in report and "precedence consistency across compatible/forced" in report
