"""T091 round 4, investigator Y — findings 2, 3 and 7: the read-only verbs
read a recorded spec under ``validation="recorded"`` (run-only rules become
notes), a ``dataclasses.replace`` copy names no ``spec_path``, and ``--dry``
previews a resume."""

from __future__ import annotations

import dataclasses
import json

import pytest

import alienbio.suite.llm_agent as llm_agent
from alienbio.commands.suite_cmd import suite_command
from alienbio.suite.experiment import aggregate, preflight, run_experiment, spec_from_manifest
from alienbio.suite.spec import REPO_ROOT, ExperimentSpec, load_spec, spec_from_dict, spec_to_dict
from alienbio.suite.store import read_manifest

NEW_MODEL = "claude-x-20250101"


def _replaced(name: str, **changes) -> ExperimentSpec:
    return dataclasses.replace(load_spec(REPO_ROOT / f"catalog/experiments/{name}.yaml"), **changes)


def _edit_manifest(out, edit) -> None:
    path = out / "manifest.json"
    manifest = json.loads(path.read_text())
    edit(manifest)
    path.write_text(json.dumps(manifest))


# ── Y2 — a rule the run predates is a note on read, a refusal on resume ──────


def test_a_price_mapping_the_table_has_since_gained_aggregates_with_a_note_and_refuses_on_resume(
    tmp_path, monkeypatch, capsys
):
    spec = _replaced("exp08", price_usd_per_mtok={NEW_MODEL: (1, 2)})
    out = tmp_path / "run"
    run_experiment(spec, out_dir=str(out))
    n = len(aggregate(out).records)
    monkeypatch.setitem(llm_agent.MODEL_PRICES_USD_PER_MTOK, NEW_MODEL, (3.0, 15.0))
    recorded = spec_from_manifest(read_manifest(out / "manifest.json"))
    assert recorded.validation == "recorded"
    assert len(recorded.recorded_warnings) == 1 and "published model(s)" in recorded.recorded_warnings[0]
    assert len(aggregate(out).records) == n
    assert suite_command(["report", str(out)]) == 0
    printed = capsys.readouterr().out
    assert printed.startswith("Recorded-spec notes") and NEW_MODEL in printed
    assert (out / "report.txt").read_text().startswith("Recorded-spec notes")
    assert suite_command(["aggregate", str(out)]) == 0
    assert "published model(s)" in capsys.readouterr().err
    assert suite_command(["resume", str(out)]) == 1
    assert "published model(s)" in capsys.readouterr().err
    with pytest.raises(ValueError, match="published model"):
        spec_from_manifest(read_manifest(out / "manifest.json"), current=True)


def test_a_dial_both_fixed_and_swept_in_an_old_manifest_reports_with_a_note_and_refuses_on_resume(tmp_path, capsys):
    out = tmp_path / "run"
    run_experiment(_replaced("exp09"), out_dir=str(out))
    n = len(aggregate(out).records)
    _edit_manifest(out, lambda m: m["spec"]["fixed_dials"].__setitem__("stakes", "low"))
    assert len(aggregate(out).records) == n
    assert suite_command(["report", str(out)]) == 0
    assert "both fixed and swept" in capsys.readouterr().out.split("\n\n")[0]
    assert suite_command(["resume", str(out)]) == 1
    assert "both fixed and swept" in capsys.readouterr().err


def test_recorded_mode_notes_only_the_run_rules():
    good = spec_to_dict(ExperimentSpec(
        name="y", axes=(("pi", (0.0, 1.0)),), drafter="pressure", agent="idle", trials_per_condition=1,
        base_seed=1, fixed_dials={"levers": []},
    ))
    for broken, phrase in (
        ({**good, "axes": {"pi": []}}, "no levels"),
        ({**good, "axes": {"pi": [1, 1.0]}}, "repeats level"),
        ({**good, "fixed_dials": {"levers": [], "pi": 0.5}}, "both fixed and swept"),
        ({**good, "trials_per_condition": 1, "design": {"target_effect_d": 0.5}}, "design needs"),
    ):
        with pytest.raises(ValueError, match=phrase):
            spec_from_dict(broken)
        assert any(phrase in note for note in spec_from_dict(broken, validation="recorded").recorded_warnings)
    # Unreadable structure refuses in either mode.
    for broken, phrase in (
        ({**good, "axes": {"pi": "0.5"}}, "list of levels"),
        ({**good, "axes": [["pi", [0.0]]]}, "mapping"),
        ({**good, "axes": {"agent": ["no-such-agent"]}}, "unknown agent"),
    ):
        with pytest.raises(ValueError, match=phrase):
            spec_from_dict(broken, validation="recorded")
    assert spec_from_dict(good, validation="recorded").recorded_warnings == ()


def test_a_recorded_spec_never_runs(tmp_path):
    good = spec_to_dict(_replaced("exp09"))
    recorded = spec_from_dict(good, validation="recorded")
    for call in (lambda: preflight(recorded), lambda: run_experiment(recorded, out_dir=str(tmp_path / "r"))):
        with pytest.raises(ValueError, match="validation='run'"):
            call()
    with pytest.raises(ValueError, match="validation must be"):
        spec_from_dict(good, validation="lax")  # type: ignore[arg-type]


def test_a_recorded_helper_outside_the_catalog_refuses(tmp_path):
    out = tmp_path / "run"
    run_experiment(_replaced("exp09"), out_dir=str(out))
    rogue = tmp_path / "rogue.py"
    rogue.write_text("raise SystemExit('executed')\n")
    _edit_manifest(out, lambda m: m.update(spec_path="x.yaml", helper_modules=[str(rogue)]))
    with pytest.raises(ValueError, match="outside the trusted catalog root"):
        aggregate(out)


# ── Y3 — a replaced spec names no yaml; its resume compares the manifest ─────


def test_a_replaced_spec_names_no_spec_path_and_resumes_from_the_cli(tmp_path):
    loaded = load_spec(REPO_ROOT / "catalog/experiments/exp08.yaml")
    assert loaded.source is not None
    spec = dataclasses.replace(loaded, base_seed=loaded.base_seed + 1)
    assert spec.source is None
    out = tmp_path / "run"
    run_experiment(spec, out_dir=str(out))
    manifest = json.loads((out / "manifest.json").read_text())
    assert "spec_path" not in manifest and "helper_modules" not in manifest
    lines = (out / "records.jsonl").read_text().splitlines()
    (out / "records.jsonl").write_text("\n".join(lines[:4]) + "\n")
    assert suite_command(["resume", str(out)]) == 0
    assert len((out / "records.jsonl").read_text().splitlines()) == len(lines)


# ── Y7 — --dry previews a resume; the re-draft note prints without -v ─────────


def test_dry_previews_a_resume_and_the_stamp_note_prints_without_verbose(tmp_path, capsys):
    yaml = REPO_ROOT / "catalog/experiments/exp09.yaml"
    out = tmp_path / "run"
    assert suite_command(["run", str(yaml), "--out", str(out), "--dry"]) == 0
    fresh = capsys.readouterr().out
    assert "resume: skipped (not a resume)" in fresh and "preview: resume" not in fresh
    assert suite_command(["run", str(yaml), "--out", str(out)]) == 0
    capsys.readouterr()
    _edit_manifest(out, lambda m: m.pop("world_scheme"))
    assert suite_command(["run", str(yaml), "--out", str(out), "--dry"]) == 0
    dry = capsys.readouterr().out
    assert "preview: resume" in dry
    assert "resume: ok" in dry and "records-readable: ok" in dry and "out_dir: ok" in dry
    assert "had no world_scheme stamp" in dry
    assert suite_command(["resume", str(out)]) == 0
    assert "had no world_scheme stamp" in capsys.readouterr().out
