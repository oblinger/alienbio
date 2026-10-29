"""T091 round 4, investigator B — the runtime / experiment-pipeline findings,
each pinned by its repro: duplicate and empty axes, a resume with no
manifest, the cost ceiling on resume, a torn record line, duplicate YAML
keys, the report verdict, non-finite spellings, the probe signature, the
target-pair shape, inert factory axes, the census, and the idle arm on a
swept agent axis."""

from __future__ import annotations

import dataclasses
import json
import math
import time
from pathlib import Path

import pytest

from alienbio.suite import agents as agents_mod
from alienbio.suite.agents import _survey_commit_agent_factory
from alienbio.suite.brief import _target_id
from alienbio.suite.experiment import ExperimentSpec, aggregate, render_report, run_experiment
from alienbio.suite.expr_experiment import load_experiment
from alienbio.suite.guards import preflight
from alienbio.suite.registration import load_registry
from alienbio.suite.store import (
    StoreError,
    _canonical_json,
    _write_manifest,
    read_manifest,
    read_records,
    record_from_json,
    record_to_json,
)


def _spec(name: str = "t091", **overrides) -> ExperimentSpec:
    kwargs = dict(
        name=name,
        axes=(("rung", ("single", "forced")),),
        drafter="conflict",
        agent="idle",
        trials_per_condition=1,
        base_seed=42,
        fixed_dials={"levers": []},
    )
    kwargs.update(overrides)
    return ExperimentSpec(**kwargs)


# ── B1 / B5 / B10 — the grid's shape, both forms ───────────────────────────


def test_a_repeated_level_an_empty_axis_and_a_repeated_axis_refuse_at_construction():
    with pytest.raises(ValueError, match=r"axis 'rung' repeats level 'single'"):
        _spec(axes=(("rung", ("single", "single")),))
    with pytest.raises(ValueError, match=r"axis 'rung' has no levels"):
        _spec(axes=(("rung", ()),))
    with pytest.raises(ValueError, match=r"axis 'rung' is declared twice"):
        _spec(axes=(("rung", ("single",)), ("rung", ("forced",))))


_EXPR = """!experiment
name: dup
task: !q conflict(rung=rung)
episode: !q episode(max_turns=2, sim_steps=2)
agent: idle
axes:
  rung: {rung}
trials_per_condition: 1
base_seed: 1
"""


def test_the_expr_form_refuses_a_repeated_level_and_a_duplicate_key():
    with pytest.raises(ValueError, match=r"repeats level 'single'"):
        load_experiment("x.yaml", text=_EXPR.format(rung="[single, single]"))
    dup_axis = _EXPR.format(rung="[single]").replace("  rung: [single]\n", "  rung: [single]\n  rung: [forced]\n")
    with pytest.raises(Exception, match=r"duplicate key 'rung' at line \d+"):
        load_experiment("x.yaml", text=dup_axis)
    dup_trials = _EXPR.format(rung="[single]") + "trials_per_condition: 7\n"
    with pytest.raises(Exception, match=r"duplicate key 'trials_per_condition'"):
        load_experiment("x.yaml", text=dup_trials)


def test_the_registry_loads_merge_keys_and_still_refuses_a_duplicate(tmp_path):
    reg = tmp_path / "registrations.yaml"
    reg.write_text(
        "base: &b {osf: abc, filed: 2026-08-31, dials: [pi], drafters: [pressure]}\n"
        "x:\n  <<: *b\n  osf: xyz\n"
    )
    loaded = load_registry(reg)
    assert loaded["x"].osf == "xyz" and loaded["x"].dials == frozenset({"pi"})
    reg.write_text("x: {osf: a, filed: 2026-08-31, dials: [], drafters: []}\nx: {osf: b, filed: 2026-08-31, dials: [], drafters: []}\n")
    with pytest.raises(ValueError, match=r"duplicate key 'x'"):
        load_registry(reg)


# ── B2 — records with no manifest ──────────────────────────────────────────


def test_a_resume_over_records_with_no_manifest_refuses(tmp_path):
    out = tmp_path / "run"
    run_experiment(_spec(), out_dir=str(out))
    (out / "manifest.json").unlink()
    flight = preflight(_spec(base_seed=999), out_dir=str(out), resume=True)
    assert dict(flight.checks)["resume"] is not None
    assert "no manifest.json" in dict(flight.checks)["resume"] and "drift check cannot run" in dict(flight.checks)["resume"]
    with pytest.raises(ValueError, match="no manifest.json"):
        run_experiment(_spec(base_seed=999), out_dir=str(out), resume=True)


# ── B3 — the cost ceiling on resume ────────────────────────────────────────


class _Paid:
    """A scripted agent that reports $2 of usage per trial (1M input tokens)."""

    def __init__(self, inner):
        self.inner = inner
        self.usage = {"calls": 1, "input_tokens": 1_000_000, "output_tokens": 0,
                      "cache_read_tokens": 0, "cache_write_tokens": 0}

    def act(self, obs):
        return self.inner.act(obs)

    def __getattr__(self, name):
        return getattr(self.inner, name)


def test_a_ceiling_stopped_run_finishes_after_the_ceiling_is_raised(tmp_path, monkeypatch):
    monkeypatch.setitem(agents_mod.AGENTS, "paid", lambda spec: (lambda seed, dials: _Paid(_survey_commit_agent_factory(seed, dials))))
    spec = _spec(agent="paid", trials_per_condition=3, cost_ceiling_usd=5.0)
    out = tmp_path / "run"
    first = run_experiment(spec, out_dir=str(out))
    assert first.provenance.stopped_early and len(first.records) < 6
    spent = sum(1 for _ in read_records(out / "records.jsonl")) * 2.0

    # Below what the records spent: refused, the spend named.
    with pytest.raises(ValueError, match=rf"already spent \${spent:.4f}"):
        run_experiment(dataclasses.replace(spec, cost_ceiling_usd=spent - 1.0), out_dir=str(out), resume=True)
    # concurrency and out_dir are not drift; a raised ceiling finishes the grid.
    raised = dataclasses.replace(spec, cost_ceiling_usd=100.0, concurrency=2, out_dir=str(out))
    assert preflight(raised, out_dir=str(out), resume=True).ok
    done = run_experiment(raised, out_dir=str(out), resume=True)
    assert len(done.records) == 6 and not done.provenance.stopped_early
    manifest = read_manifest(out / "manifest.json")
    assert manifest["cost_ceiling_history"] == [5.0, 100.0]
    assert manifest["cost_ceiling_usd"] == 100.0 and manifest["stopped_reason"] is None


# ── B4 — a torn record line ────────────────────────────────────────────────


def test_a_torn_last_line_is_named_and_refused_before_spend(tmp_path):
    out = tmp_path / "run"
    run_experiment(_spec(), out_dir=str(out))
    records = out / "records.jsonl"
    text = records.read_text()
    records.write_text(text[:-40])  # the last append cut mid-line, no newline
    with pytest.raises(StoreError, match=r"line 2 is not valid JSON .* torn by a crash"):
        list(read_records(records))
    flight = preflight(_spec(), out_dir=str(out), resume=True)
    assert "line 2 is not valid JSON" in str(dict(flight.checks)["records-readable"])
    assert not flight.ok
    # A bad line mid-file is named too, without the torn-tail reading.
    lines = text.splitlines()
    records.write_text("{not json\n" + lines[1] + "\n")
    with pytest.raises(StoreError, match=r"line 1 is not valid JSON") as info:
        list(read_records(records))
    assert "crash" not in str(info.value)


# ── B7 — non-finite spellings round-trip without eating strings ────────────


def test_a_string_nan_stays_a_string_and_a_float_nan_stays_a_float(tmp_path):
    path = tmp_path / "manifest.json"
    _write_manifest(path, {"spec": {"fixed_dials": {"note": "nan", "esc": "\\inf", "x": float("nan"), "y": float("-inf")}}})
    dials = read_manifest(path)["spec"]["fixed_dials"]
    assert dials["note"] == "nan" and dials["esc"] == "\\inf"
    assert math.isnan(dials["x"]) and dials["y"] == float("-inf")

    out = tmp_path / "run"
    rmap = run_experiment(_spec(), out_dir=str(out))
    record = dataclasses.replace(
        rmap.records[0],
        condition_key=(("note", "inf"), ("x", float("inf")), ("z", float("nan"))),
        answer="nan",
    )
    back = record_from_json(json.loads(_canonical_json(record_to_json(record, "c", 0))))
    key = dict(back.condition_key)
    assert key["note"] == "inf" and key["x"] == float("inf") and math.isnan(key["z"])
    assert back.answer == "nan"


def test_a_string_inf_axis_resumes_unchanged(tmp_path):
    spec = _spec(axes=(("task_note", ("inf", "nan")),), fixed_dials={"levers": [], "rung": "single"})
    out = tmp_path / "run"
    run_experiment(spec, out_dir=str(out))
    assert preflight(spec, out_dir=str(out), resume=True).ok
    assert [dict(r.condition_key)["task_note"] for r in aggregate(out).records] == ["inf", "nan"]


# ── B8 — the probe signature ───────────────────────────────────────────────


class _OldProbe:
    def __init__(self, inner):
        self.inner = inner

    def act(self, obs):
        return self.inner.act(obs)

    def probe(self, text):  # the pre-T088 signature
        return "ok"

    def __getattr__(self, name):
        return getattr(self.inner, name)


def test_an_agent_on_the_old_probe_signature_refuses_at_preflight(monkeypatch):
    monkeypatch.setitem(agents_mod.AGENTS, "old-probe", lambda spec: (lambda seed, dials: _OldProbe(_survey_commit_agent_factory(seed, dials))))
    flight = preflight(_spec(agent="old-probe"))
    why = str(dict(flight.checks)["agent"])
    assert "'old-probe'" in why and "(text, observation)" in why and "T088" in why


# ── B9 — a target pair is exactly (str, number) ────────────────────────────


def test_a_list_of_ids_is_not_an_id_goal_pair():
    assert _target_id(["a", "b"]) is None  # two ids: the caller reads each
    assert _target_id(("a", 1.5)) == "a" and _target_id(["a", 2]) == "a"
    assert _target_id(("a", True)) is None and _target_id(("a", 1.0, 2.0)) is None


# ── B11 — a factory axis no agent reads ────────────────────────────────────


def test_a_memory_axis_on_scripted_arms_refuses_as_inert():
    flight = preflight(_spec(axes=(("rung", ("single",)), ("memory", (2, 6)))))
    why = str(dict(flight.checks)["inert-arm"])
    assert "'memory' axis is read by no agent" in why and "idle" in why and "llm" in why


# ── B13 — the census counts grade errors and parse failures ────────────────


def test_the_census_counts_grade_error_and_parse_failures(tmp_path):
    out = tmp_path / "run"
    rmap = run_experiment(_spec(), out_dir=str(out))
    marked = (
        dataclasses.replace(rmap.records[0], grade_error="MalformedAnswer: x", parse_failures=3),
        dataclasses.replace(rmap.records[1], parse_failures=2),
    )
    text = render_report(dataclasses.replace(rmap, records=marked), read_manifest(out / "manifest.json"))
    assert "records with grade_error: 1" in text
    assert "records with parse_failures: 2" in text and "parse_failures (total): 5" in text


# ── fix A's observation — the idle arm on a swept agent axis ───────────────


def test_idle_baseline_adds_idle_to_a_swept_agent_axis_once():
    spec = _spec(agent="survey-commit", axes=(("agent", ("survey-commit", "act-commit")),), idle_baseline=True)
    assert dict(spec.axes)["agent"] == ("survey-commit", "act-commit", "idle")
    assert dataclasses.replace(spec).axes == spec.axes  # idempotent through a rebuild
    plain = _spec(agent="survey-commit", idle_baseline=True)
    assert dict(plain.axes)["agent"] == ("survey-commit", "idle")


def _unused() -> None:  # keep imports honest for linters
    del Path, time
