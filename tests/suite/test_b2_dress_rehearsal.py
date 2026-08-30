"""M45.13 — the zero-model-call dress rehearsal of the whole B2 pipeline, in CI.

A pressure-world sweep over ``pi`` x ``complexity`` driven by the idle
``ScriptedAgent`` through ``run_experiment`` — spec load, grid, drafter,
brief, runner, record store, manifest, aggregate, report — so every seam a
paid run will use is exercised on every CI run, with no API key and no
network. Scripted only: the no-peeking rule forbids a live model on this
substrate, and ``run_experiment`` refuses it.
"""

from __future__ import annotations

import json

from alienbio.suite.experiment import aggregate, load_spec, render_report, run_experiment


def test_b2_pipeline_dress_rehearsal_zero_model_calls(tmp_path):
    spec_path = tmp_path / "b2-rehearsal.yaml"
    spec_path.write_text(
        """\
!experiment
name: b2-rehearsal
task: !q pressure(pi=pi, complexity=complexity)
brief: !q brief(levers=[])
episode: !q episode(max_turns=3, sim_steps=5)
agent: idle
axes: {pi: [0.0, 1.0], complexity: [0, 1]}
trials_per_condition: 3   # what design d=3.0 requires
base_seed: 5
design: !power {target_effect_d: 3.0, primary_contrast: {axis: pi, low: 0.0, high: 1.0}, multiple_comparison: bonferroni}
"""
    )
    spec = load_spec(spec_path)
    out = tmp_path / "out"
    rmap = run_experiment(spec, out_dir=str(out))

    # Four cells, three trials each, all landed, none failed.
    assert len(rmap.cells) == 4
    assert rmap.provenance.failed_trials == 0
    lines = [json.loads(l) for l in (out / "records.jsonl").read_text().splitlines()]
    assert len(lines) == 12
    assert {tuple(sorted(dict(d["condition_key"]))) for d in lines} == {("complexity", "pi")}
    assert all(d["terminal_reason"] == "max_turns" and d["turns"] == 3 for d in lines)
    assert all(d["brief"]["sim_steps"] == 5 for d in lines)
    # The outcome objective scores the world trajectory; the idle agent still
    # gets a real number, and pi=1 shifts the world (the pressure signature).
    scores = {tuple(sorted(dict(d["condition_key"]).items())): d["objective_score"] for d in lines}
    assert all(0.0 <= s <= 1.0 for s in scores.values())

    manifest = json.loads((out / "manifest.json").read_text())
    assert manifest["trials_completed"] == 12 and manifest["model"] is None
    assert manifest["design"]["primary_contrast"]["axis"] == "pi"
    assert manifest["cost_estimate"]["usd"] == 0.0

    report = render_report(rmap, manifest)
    assert "pi=1.0" in report and "complexity=1" in report
    assert "failed: 0" in report and "Design (M46.9" in report
    assert "primary contrast pi: 0.0 -> 1.0" in report

    # The map rebuilt from the store alone matches the returned one.
    rebuilt = aggregate(str(out))
    assert {k: v.stats.mean for k, v in rebuilt.cells.items()} == {k: v.stats.mean for k, v in rmap.cells.items()}
