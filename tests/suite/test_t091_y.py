"""T091 round 4, investigator Y — report-side findings 4, 5, 6 and 8.

Each test failed before its fix. Every LLM here is a fake ``LLMFn``: no key,
no network, no spend.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest

from alienbio.suite.caution import caution_summary, trial_caution
from alienbio.suite.census import pressure_byproduct
from alienbio.suite.degradation import degradation_summary, trial_degradation
from alienbio.suite.dist import Seed
from alienbio.suite.dose import DoseCell, continuity_unread_reason, pressure_final_value
from alienbio.suite.drafters import DRAFTERS
from alienbio.suite.experiment import ExperimentSpec, load_spec, render_report, run_experiment
from alienbio.suite.llm_agent import LLMAgent, UsageMeter
from alienbio.suite.realism import RealismSummary, realism_lines
from alienbio.suite import runner

REPO = Path(__file__).resolve().parents[2]


def _never_called(directive, context, seed):  # the ceiling aborts before any call
    raise AssertionError("the fake LLM was called")


def _aborted_record():
    meter = UsageMeter()
    agent = LLMAgent(_never_called, Seed(1), meter=meter, token_ceiling=10)
    world, task = DRAFTERS["discover"](Seed(5), {})
    return runner.run(world, task, agent, {"budget": "8"}, Seed(5), max_turns=4)


# Y4 -----------------------------------------------------------------------------


def test_an_aborted_trial_is_not_a_commit_in_caution_or_degradation():
    record = _aborted_record()
    assert record.aborted == "token_ceiling" and [a.kind for a in record.action_log] == ["commit"]
    assert not trial_caution(record)[2]
    d = trial_degradation(record)
    assert not d.committed and d.aborted and not d.exhausted
    (cc,) = caution_summary([record]).values()
    assert cc.commit_rate == 0.0 and cc.aborted_rate == 1.0 and cc.abstain_rate == 0.0
    (dc,) = degradation_summary([record]).values()
    assert dc.commit_rate == 0.0 and dc.aborted_rate == 1.0 and dc.exhausted_rate == 0.0


# Y5 -----------------------------------------------------------------------------


def _pressure_record(tmp_path):
    spec = load_spec(REPO / "catalog" / "experiments" / "exp02.yaml")
    spec = dataclasses.replace(spec, axes=(("pi", (0.0,)),), trials_per_condition=1, design=None, out_dir=None, idle_baseline=False)
    rmap = run_experiment(spec, out_dir=str(tmp_path / "run"))
    return next(r for r in rmap.records if (r.oracle or {}).get("pressure"))


def test_a_multi_compartment_pressure_record_refuses_in_pressure_words(tmp_path):
    record = _pressure_record(tmp_path)
    oracle = record.oracle["pressure"]
    (only,) = record.final_state
    one = pressure_byproduct(record)
    assert one == pytest.approx(record.final_state[only][oracle["byproduct"]])
    two = dataclasses.replace(record, final_state={only: dict(record.final_state[only]), "lumen": {oracle["byproduct"]: 1.0}})
    with pytest.raises(ValueError, match=r"^pressure target .*pressure oracle names none") as exc:
        pressure_byproduct(two)
    assert "conflict" not in str(exc.value)
    named = dataclasses.replace(two, oracle={**two.oracle, "pressure": {**oracle, "compartments": {oracle["byproduct"]: "lumen"}}})
    assert pressure_final_value(named, oracle["byproduct"]) == 1.0


# Y6 -----------------------------------------------------------------------------


def test_the_census_names_taint_exempt_ids_and_caution_prints_aborts(tmp_path):
    spec = ExperimentSpec(name="y6", drafter="discover", agent="knockout-commit", axes=(("stakes", ("low", "high")),), trials_per_condition=1, base_seed=3)
    rmap = run_experiment(spec, out_dir=str(tmp_path / "run"))
    manifest = json.loads((tmp_path / "run" / "manifest.json").read_text())
    text = render_report(rmap, manifest)
    assert "records with taint_exempt: 0" in text and " abort " in text
    first, *rest = rmap.records
    marked = dataclasses.replace(rmap, records=(dataclasses.replace(first, taint_exempt={"m03": 2, "r01": 1}), *rest))
    assert "records with taint_exempt: 1 (ids: m03, r01)" in render_report(marked, manifest)


def test_an_all_aborted_run_is_not_a_green_row(tmp_path, monkeypatch):
    import alienbio.report as report
    from alienbio.report import build, render_markdown

    runs = tmp_path / "runs"
    run_dir = runs / "allabort"
    run_dir.mkdir(parents=True)
    (run_dir / "manifest.json").write_text(json.dumps({"trials_completed": 2, "failed_trials": 0, "model": "fake-model", "started_at": "2026-10-29"}))
    (run_dir / "records.jsonl").write_text("\n".join(json.dumps({"aborted": "token_ceiling"}) for _ in range(2)) + "\n")
    monkeypatch.setattr(report, "RUNS", runs)
    rep = build({}, pytest_exit=0, run_examples=False)
    (row,) = rep.runs
    assert row.aborted == 2 and row.passed == 0
    md = render_markdown(rep)
    line = next(l for l in md.splitlines() if "`allabort`" in l)
    assert "✅" not in line and "2 (all aborted)" in line


# Y8 -----------------------------------------------------------------------------


def test_realism_rows_print_comparisons_beside_n():
    lines = realism_lines({(("arm", "a"),): RealismSummary(n=3, wins=2, win_rate=2 / 3, ci=(0.2, 0.9), comparisons=5)})
    header, row = lines[1], lines[2]
    assert "comparisons" in header and row.split()[1:3] == ["3", "5"]


def _dose(pis):
    return [DoseCell(pi=p, n=1, mean_t=0.0, mean_byproduct=p, mean_score=0.0, passive_t=0.0, passive_byproduct=0.0, v_target=1.0) for p in pis]


def test_an_unread_continuity_share_says_why():
    assert continuity_unread_reason(_dose([0.0, 0.05, 0.5, 1.0])) == "no rung within 0.1 of 0.2"
    assert continuity_unread_reason(_dose([0.0, 1.0])) == "no rung within 0.1 of 0.2"
    assert continuity_unread_reason(_dose([0.15, 0.5, 1.0])) == "nearest rung pi=0.15 is an end rung"
    assert continuity_unread_reason(_dose([0.0])) == "one rung"
    assert continuity_unread_reason(_dose([0.0, 0.2, 1.0])) is None
