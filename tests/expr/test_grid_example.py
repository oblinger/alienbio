"""M48.9 example 7 — the grid: one neutral world under a full experiment —
two swept axes, a power design, matched world seeds, an automatic idle
baseline, bounded concurrency, the cost dry-run, and the run interrupted,
resumed, aggregated and reported."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from alienbio.expr import Env
from alienbio.suite.experiment import (
    aggregate,
    estimate_cost,
    idle_baseline_comparison,
    load_spec,
    render_report,
    run_experiment,
)

REPO = Path(__file__).resolve().parents[2]
SPEC = REPO / "catalog" / "examples" / "grid" / "grid.yaml"


def test_the_world_is_a_grid_sized_by_both_dials():
    v = Env.standard(seed=17, trusted=True).load(SPEC).force_all()
    world = v["world"]
    rows, steps = 3, 2  # the file's defaults: n_nodes=3, complexity=2
    assert len(world.chemistry.reactions) == rows * (steps + 2)  # chain steps + a source + a sink per row
    assert len(world.chemistry.molecules) == rows * (steps + 1)
    assert v["task"].objective.key.value == "down"


def test_the_spec_declares_the_full_harness():
    spec = load_spec(SPEC)
    assert spec.drafter == "grid"
    assert spec.axes == (("complexity", (1, 3)), ("n_nodes", (2, 4)), ("agent", ("trend-commit", "prior-commit", "idle")))
    assert spec.design is not None and spec.design.primary_contrast == {"axis": "complexity", "low": 1, "high": 3}
    assert spec.trials_per_condition >= spec.design.required_trials_per_condition
    assert spec.matched_dials == ("complexity", "n_nodes")
    assert spec.idle_baseline and spec.concurrency == 2
    est = estimate_cost(spec)
    assert est.llm_trials == 0 and est.usd == 0.0  # scripted agents: the dry run costs nothing


@pytest.fixture(scope="module")
def full_run(tmp_path_factory):
    out = tmp_path_factory.mktemp("grid") / "run"
    rmap = run_experiment(load_spec(SPEC), out_dir=str(out))
    return out, rmap


def test_the_run_fills_the_grid_with_matched_idle_twins(full_run):
    out, rmap = full_run
    assert len(rmap.records) == 2 * 2 * 3 * 3 and rmap.provenance.failed_trials == 0
    assert (out / "records.jsonl").exists() and (out / "manifest.json").exists()
    twins = idle_baseline_comparison(rmap)
    assert len(twins) == 8 and all(n == 3 for *_, n in twins)  # every condition, both live arms against idle, three trials each
    assert all(idle == 0.0 for _, _, _, idle, _ in twins)  # doing nothing answers nothing
    by_agent = {agent: live for _, agent, live, _, _ in twins}
    assert by_agent["prior-commit"] == 1.0  # the textbook prior is right on every cell of this grid
    assert by_agent["trend-commit"] == 0.0  # the unperturbed trend points the wrong way on every cell
    # the twin is the same (condition, trial index) under the other agent: the
    # store line carries the index; matched seeds give both arms one world
    lines = [json.loads(l) for l in (out / "records.jsonl").read_text().splitlines()]
    pairs: dict = {}
    for line in lines:
        cond = tuple((k, v) for k, v in line["condition_key"] if k != "agent")
        pairs.setdefault((cond, line["index"]), set()).add(dict(line["condition_key"])["agent"])
    assert len(pairs) == 12 and all(arms == {"trend-commit", "prior-commit", "idle"} for arms in pairs.values())


def test_an_interrupted_run_resumes_without_redoing_or_dropping_trials(full_run, tmp_path):
    out, rmap = full_run
    lines = (out / "records.jsonl").read_text().splitlines()
    partial = tmp_path / "partial"
    partial.mkdir()
    (partial / "records.jsonl").write_text("\n".join(lines[:10]) + "\n")
    (partial / "manifest.json").write_text((out / "manifest.json").read_text())
    with pytest.raises(FileExistsError):
        run_experiment(load_spec(SPEC), out_dir=str(partial))  # never silently overwrite
    resumed = run_experiment(load_spec(SPEC), out_dir=str(partial), resume=True)
    assert len(resumed.records) == len(rmap.records)
    after = (partial / "records.jsonl").read_text().splitlines()
    assert after[:10] == lines[:10]  # the finished trials are kept, not redone
    assert len(after) == len(lines)


def test_aggregate_and_report_rebuild_from_the_record_store(full_run):
    out, rmap = full_run
    again = aggregate(out)
    assert {k: (c.stats.n, c.stats.mean) for k, c in again.cells.items()} == {k: (c.stats.n, c.stats.mean) for k, c in rmap.cells.items()}
    manifest = json.loads((out / "manifest.json").read_text())
    text = render_report(again, manifest)
    assert "grid-zero" in text and "complexity" in text and "idle" in text.lower()
