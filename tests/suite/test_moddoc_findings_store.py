"""Findings from the ``ABIO Store`` module doc (T084): the run store's
robustness defects, each pinned red-then-green.

A — a non-finite float anywhere on a record line wrote a bare ``NaN`` /
``Infinity`` token that strict JSON readers refuse.
B — ``manifest.json`` was written in place, so a crash mid-dump tore it; a
resume appended retried lines before replacing ``records.jsonl``, so a crash
between the two duplicated them on the next resume.
C — a resumed run that crashed left ``trials_completed: 0`` beside a store
full of landed lines.
D — under a ``model`` axis the manifest's ``model`` is null and the levels
ride ``models``; ``render_report`` printed ``Model: None`` and ``bio report``
listed the paid sweep as ``scripted``.
"""

from __future__ import annotations

import dataclasses
import json
import math

import pytest

from alienbio.suite.experiment import ExperimentSpec, record_from_json, record_to_json, run_experiment
from alienbio.suite.info_seeking import ActionRecord
from alienbio.suite.store import _canonical_json


def _spec(name: str, trials_per_condition: int = 1, **overrides) -> ExperimentSpec:
    kwargs = dict(
        name=name,
        axes=(("rung", ("single", "forced")),),
        drafter="conflict",
        agent="idle",
        trials_per_condition=trials_per_condition,
        base_seed=42,
        fixed_dials={"levers": []},
    )
    kwargs.update(overrides)
    return ExperimentSpec(**kwargs)


def _strict_loads(line: str):
    def refuse(token: str):
        raise ValueError(f"non-strict JSON token {token!r}")

    return json.loads(line, parse_constant=refuse)


# ── A. non-finite floats ────────────────────────────────────────────────────


def test_non_finite_floats_round_trip_as_strict_json(tmp_path):
    rmap = run_experiment(_spec("nonfinite"), out_dir=str(tmp_path / "run"))
    record = dataclasses.replace(
        rmap.records[0],
        final_state={"root": {"m1": float("nan"), "m2": float("inf"), "m3": 1.5}},
        action_log=(
            ActionRecord(
                kind="intervene", destructive=False, accepted=True, reason="", target="m1",
                value=float("-inf"), delta=float("nan"),
            ),
        ),
        objective_score=float("nan"),
        oracle={"v_target": float("inf"), "nested": [float("-inf"), 2.0]},
    )
    line = _canonical_json(record_to_json(record, "rung=single", 0))
    d = _strict_loads(line)  # strict readers accept the line
    rebuilt = record_from_json(d)

    assert math.isnan(rebuilt.final_state["root"]["m1"])
    assert rebuilt.final_state["root"]["m2"] == float("inf")
    assert rebuilt.final_state["root"]["m3"] == 1.5
    assert rebuilt.action_log[0].value == float("-inf")
    assert math.isnan(rebuilt.action_log[0].delta)
    assert math.isnan(rebuilt.objective_score)
    assert rebuilt.oracle["v_target"] == float("inf")
    assert rebuilt.oracle["nested"] == [float("-inf"), 2.0]


def test_canonical_json_refuses_a_stray_non_finite_float():
    class Wrapper(float):
        pass

    # A finite tree is byte-identical to the plain dump.
    payload = {"b": [1.0, 2], "a": {"x": "inf-not-a-float"}}
    assert _canonical_json(payload) == json.dumps(payload, sort_keys=True, separators=(",", ":"))
    # The encoder spells a float subclass too; nothing reaches the dump bare.
    assert _strict_loads(_canonical_json({"v": Wrapper("nan")})) == {"v": "nan"}


def test_run_store_lines_are_strict_json(tmp_path):
    out = tmp_path / "run"
    run_experiment(_spec("strict"), out_dir=str(out))
    for line in (out / "records.jsonl").read_text().splitlines():
        _strict_loads(line)


# ── B. atomic manifest, ordered retries ─────────────────────────────────────


def _flaky_forced(monkeypatch, fail: dict):
    import alienbio.suite.mass_trial as mass_trial_mod

    original = mass_trial_mod.run_trial

    def flaky(world, task, agent, dials, seed, **kwargs):
        if fail["on"] and dials.get("rung") == "forced":
            raise RuntimeError("credit balance is too low")
        return original(world, task, agent, dials, seed, **kwargs)

    monkeypatch.setattr(mass_trial_mod, "run_trial", flaky)


def test_a_crash_between_the_retry_writes_duplicates_nothing(tmp_path, monkeypatch):
    import alienbio.suite.experiment as experiment_mod

    fail = {"on": True}
    _flaky_forced(monkeypatch, fail)
    out = tmp_path / "run"
    spec = _spec("crashretry", trials_per_condition=2)
    run_experiment(spec, out_dir=str(out))
    fail["on"] = False

    def crash(path, text):
        raise KeyboardInterrupt("killed between the two writes")

    monkeypatch.setattr(experiment_mod, "_atomic_write_text", crash)
    with pytest.raises(KeyboardInterrupt):
        run_experiment(spec, out_dir=str(out), resume=True)
    monkeypatch.undo()  # the store writes again; the trial is no longer flaky

    run_experiment(spec, out_dir=str(out), resume=True)
    retried = (out / "records.retried.jsonl").read_text().strip().splitlines()
    assert len(retried) == 2  # each error line kept once — none lost, none doubled
    assert len({(json.loads(l)["label"], json.loads(l)["index"]) for l in retried}) == 2
    lines = [json.loads(l) for l in (out / "records.jsonl").read_text().strip().splitlines()]
    assert len(lines) == 4 and not any(d["error"] for d in lines)


def test_a_torn_manifest_dump_leaves_the_old_manifest_intact(tmp_path, monkeypatch):
    import alienbio.suite.store as store_mod

    out = tmp_path / "run"
    spec = _spec("torn", trials_per_condition=1)
    run_experiment(spec, out_dir=str(out))
    manifest_path = out / "manifest.json"
    before = manifest_path.read_text()

    # The manifest goes through ``_atomic_write_text`` (T088: strict JSON);
    # a write that dies before ``os.replace`` must leave the old one standing.
    real_fsync = store_mod.os.fsync

    def torn_fsync(fd):
        raise OSError("disk full")

    monkeypatch.setattr(store_mod.os, "fsync", torn_fsync)
    with pytest.raises(OSError):
        run_experiment(_spec("torn", trials_per_condition=2), out_dir=str(out), resume=True)
    monkeypatch.setattr(store_mod.os, "fsync", real_fsync)

    assert manifest_path.read_text() == before
    json.loads(manifest_path.read_text())
    assert not (out / "manifest.json.tmp").exists()


# ── C. a resumed run that crashes ───────────────────────────────────────────


def test_a_resume_that_crashes_counts_what_landed(tmp_path, monkeypatch):
    import alienbio.suite.mass_trial as mass_trial_mod

    out = tmp_path / "run"
    run_experiment(_spec("crashcount", trials_per_condition=1), out_dir=str(out))  # 2 kept

    original = mass_trial_mod.run_trial
    fresh = {"n": 0}

    def dies_on_the_second(world, task, agent, dials, seed, **kwargs):
        fresh["n"] += 1
        if fresh["n"] == 2:
            raise KeyboardInterrupt("killed mid-grid")
        return original(world, task, agent, dials, seed, **kwargs)

    monkeypatch.setattr(mass_trial_mod, "run_trial", dies_on_the_second)
    with pytest.raises(KeyboardInterrupt):
        run_experiment(_spec("crashcount", trials_per_condition=2), out_dir=str(out), resume=True)

    manifest = json.loads((out / "manifest.json").read_text())
    lines = (out / "records.jsonl").read_text().strip().splitlines()
    assert len(lines) == 3
    assert manifest["trials_completed"] == 3  # kept 2 + the one that landed
    assert manifest["failed_trials"] == 0
    assert manifest["finished_at"] is None


def test_a_resume_starts_its_manifest_from_the_kept_lines(tmp_path, monkeypatch):
    import alienbio.suite.experiment as experiment_mod

    out = tmp_path / "run"
    run_experiment(_spec("startcount", trials_per_condition=1), out_dir=str(out))
    written: list[dict] = []
    real = experiment_mod._write_manifest
    monkeypatch.setattr(
        experiment_mod, "_write_manifest", lambda path, m: (written.append(dict(m)), real(path, m))
    )
    run_experiment(_spec("startcount", trials_per_condition=2), out_dir=str(out), resume=True)
    assert written[0]["trials_completed"] == 2 and written[0]["finished_at"] is None
    assert written[-1]["trials_completed"] == 4


# ── D. readers under a model axis ───────────────────────────────────────────


def test_readers_name_the_model_axis_levels(tmp_path, monkeypatch):
    import alienbio.report as report_mod
    from alienbio.suite.report_text import render_report

    runs = tmp_path / "runs"
    out = runs / "sweep"
    rmap = run_experiment(_spec("sweep"), out_dir=str(out))
    manifest = json.loads((out / "manifest.json").read_text())
    manifest.update(model=None, models=["claude-sonnet-5", "claude-opus-5"])
    (out / "manifest.json").write_text(json.dumps(manifest))

    text = render_report(rmap, manifest)
    assert "Model: claude-sonnet-5, claude-opus-5" in text
    assert "Model: None" not in text

    monkeypatch.setattr(report_mod, "RUNS", runs)
    (row,) = report_mod.run_rows()
    assert row.kind == "live model"
    assert row.model == "claude-sonnet-5, claude-opus-5"


def test_readers_keep_a_single_model_and_a_scripted_run():
    from alienbio.suite.store import manifest_model_label

    assert manifest_model_label({"model": "claude-sonnet-5"}) == "claude-sonnet-5"
    assert manifest_model_label({"model": None}) is None
