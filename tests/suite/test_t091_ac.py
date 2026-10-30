"""T091 round 4, verifier AC — six follow-ups: the deciding commit is the
first ACCEPTED one (AC1); a replaced catalog spec keeps its helpers (AC2);
drift is named before the seed-scheme stamp (AC3); ``--dry`` previews the
spec the manifest names (AC4); an unknown drafter refuses first (AC5); a
vanished agent or drafter is one note on the read-only verbs (AC6)."""

from __future__ import annotations

import dataclasses
import json
import subprocess
import sys

from alienbio.commands.suite_cmd import suite_command
from alienbio.suite.agent import Commit, Measure, ScriptedAgent
from alienbio.suite.caution import caution_summary, trial_caution
from alienbio.suite.degradation import trial_degradation
from alienbio.suite.dist import Seed
from alienbio.suite.drafters import DRAFTERS
from alienbio.suite.experiment import aggregate, preflight, run_experiment, spec_from_manifest
from alienbio.suite.runner import run
from alienbio.suite.spec import REPO_ROOT, ExperimentSpec, load_spec, spec_from_dict
from alienbio.suite.trial import accepted_commit_index


def _conflict_spec(**changes) -> ExperimentSpec:
    base = ExperimentSpec(
        name="ac", axes=(("rung", ("single", "latent")),), drafter="conflict", agent="idle",
        trials_per_condition=1, base_seed=1, fixed_dials={"levers": []},
    )
    return dataclasses.replace(base, **changes)


def _edit_manifest(out, edit) -> dict:
    path = out / "manifest.json"
    manifest = json.loads(path.read_text())
    edit(manifest)
    path.write_text(json.dumps(manifest))
    return manifest


# ── AC1 — a rejected commit does not decide the trial ────────────────────────


def test_a_rejected_commit_followed_by_an_accepted_one_reads_committed():
    world, task = DRAFTERS["diagnose"](Seed(5), {})
    key = task.objective.key
    probe = sorted(world.chemistry.molecules)[0]
    policy = (Measure(probe), Commit(answer=key, params="not-an-object"), Measure(probe), Commit(answer=key))
    rec = run(world, task, ScriptedAgent(policy, Seed(1)), {}, Seed(2), max_turns=6)
    assert [(a.kind, a.accepted) for a in rec.action_log][-2:] == [("measure", True), ("commit", True)]
    assert accepted_commit_index(rec.action_log) == len(rec.action_log) - 1
    info, _destructive, committed, _abstained, _fp = trial_caution(rec)
    assert committed and info == 2  # both measures, the one after the rejected commit too
    degradation = trial_degradation(rec)
    assert degradation.committed and degradation.investigated == 2
    assert next(iter(caution_summary([rec]).values())).commit_rate == 1.0


def test_only_rejected_commits_never_read_committed():
    world, task = DRAFTERS["diagnose"](Seed(5), {})
    policy = (Commit(answer=task.objective.key, params="not-an-object"),)
    rec = run(world, task, ScriptedAgent(policy, Seed(1)), {}, Seed(2), max_turns=1)
    assert accepted_commit_index(rec.action_log) is None
    assert not trial_caution(rec)[2] and not trial_degradation(rec).committed


# ── AC2 — a replaced catalog spec still aggregates, reports and resumes ──────


def test_a_replaced_catalog_spec_with_helpers_reads_in_a_fresh_process(tmp_path):
    loaded = load_spec(REPO_ROOT / "catalog/examples/agent_loop/agent_loop.yaml")
    spec = dataclasses.replace(loaded, trials_per_condition=1)
    assert spec.source == {"helper_modules": list(loaded.source["helper_modules"])}
    out = tmp_path / "run"
    run_experiment(spec, out_dir=str(out))
    manifest = json.loads((out / "manifest.json").read_text())
    assert "spec_path" not in manifest and manifest["helper_modules"] == list(loaded.source["helper_modules"])
    lines = (out / "records.jsonl").read_text().splitlines()
    (out / "records.jsonl").write_text("\n".join(lines[:1]) + "\n")
    for verb in ("aggregate", "report", "resume"):
        done = subprocess.run(
            [sys.executable, "-m", "alienbio.cli", "suite", verb, str(out)],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=600,
        )
        assert done.returncode == 0, (verb, done.stderr)
    assert len((out / "records.jsonl").read_text().splitlines()) == len(lines)


# ── AC3 — an edited spec is named as drift, not as another seed scheme ───────


def test_an_edited_matched_dial_set_refuses_as_drift(tmp_path):
    spec = _conflict_spec(
        axes=(("rung", ("single", "latent")), ("agent", ("idle", "measure-commit"))), matched_dials=("rung",)
    )
    out = tmp_path / "x"
    run_experiment(spec, out_dir=str(out))
    for edited in (
        dataclasses.replace(spec, matched_dials=()),
        dataclasses.replace(spec, axes=(("rung", ("single", "latent")),)),
    ):
        why = str(preflight(edited, out_dir=str(out), resume=True).refusal)
        assert "differs from the run's manifest" in why and "seed scheme" not in why


# ── AC4 — --dry previews the spec the manifest names ─────────────────────────


def test_dry_on_a_run_dir_previews_the_manifest_spec_and_names_the_yaml_drift(tmp_path, capsys):
    out = tmp_path / "run"
    cascade = REPO_ROOT / "catalog/examples/cascade/cascade.yaml"
    assert suite_command(["run", str(cascade), "--out", str(out)]) == 0
    capsys.readouterr()
    other = REPO_ROOT / "catalog/examples/ecosystem/ecosystem.yaml"
    assert suite_command(["run", str(other), "--out", str(out), "--dry"]) == 0
    dry = capsys.readouterr().out
    assert "preview: verdicts for the spec the manifest names (catalog/examples/cascade/cascade.yaml)" in dry
    assert "preview: drift" in dry and "ecosystem.yaml" in dry
    assert "resume: ok" in dry and "preflight: ok" in dry
    assert suite_command(["resume", str(out)]) == 0
    capsys.readouterr()
    assert suite_command(["run", str(cascade), "--out", str(out), "--dry"]) == 0
    assert "preview: drift" not in capsys.readouterr().out


# ── AC5 — an unknown drafter refuses first; nothing after it runs ────────────


def test_an_unknown_drafter_on_resume_refuses_first_and_skips_every_later_check(tmp_path):
    spec = _conflict_spec()
    out = tmp_path / "x"
    run_experiment(spec, out_dir=str(out))
    manifest = _edit_manifest(out, lambda m: m["spec"].__setitem__("drafter", "gone_drafter"))
    flight = preflight(spec_from_dict(manifest["spec"]), out_dir=str(out), resume=True)
    name, why = flight.checks[0]
    assert name == "drafter" and "unknown drafter 'gone_drafter'" in (why or "")
    assert "unknown drafter 'gone_drafter'" in str(flight.refusal)
    assert set(flight.skipped) == {n for n, _ in flight.checks[1:]}
    assert not any("unknown dial" in (w or "") for _n, w in flight.checks)


def test_the_resume_re_draft_waits_for_every_earlier_check(tmp_path, monkeypatch):
    import alienbio.suite.guards as guards

    spec = _conflict_spec()
    out = tmp_path / "x"
    run_experiment(spec, out_dir=str(out))
    _edit_manifest(out, lambda m: m.pop("world_scheme"))

    def refuse(_spec):
        raise ValueError("an earlier refusal")

    def never(*_a, **_k):
        raise AssertionError("re-drafted after an earlier refusal")

    monkeypatch.setattr(guards, "registration_admission", refuse)
    monkeypatch.setattr(guards, "recorded_worlds_violation", never)
    flight = preflight(spec, out_dir=str(out), resume=True)
    assert "an earlier refusal" in str(flight.refusal)
    assert dict(flight.checks)["resume"] is None
    assert any("re-draft of the recorded conditions skipped" in note for note in flight.notes)
    assert not any("re-drafted identically" in note for note in flight.notes)


# ── AC6 — a vanished agent or drafter is one note on read, a refusal on resume


def test_a_vanished_agent_or_drafter_is_a_note_on_read_and_refuses_on_resume(tmp_path, capsys):
    spec = _conflict_spec()
    base = tmp_path / "base"
    run_experiment(spec, out_dir=str(base))
    cases = {
        "agent": (lambda m: m["spec"].__setitem__("agent", "gone_agent"), "agent 'gone_agent'"),
        "agentaxis": (
            lambda m: m["spec"]["axes"].__setitem__("agent", ["idle", "gone_agent"]),
            "agent 'gone_agent'",
        ),
        "drafter": (lambda m: m["spec"].__setitem__("drafter", "gone_drafter"), "drafter 'gone_drafter'"),
    }
    for name, (edit, who) in cases.items():
        out = tmp_path / name
        out.mkdir()
        for f in ("manifest.json", "records.jsonl"):
            (out / f).write_bytes((base / f).read_bytes())
        manifest = _edit_manifest(out, edit)
        note = f"{who} is no longer registered; its records are kept as recorded"
        assert note in spec_from_manifest(manifest).recorded_warnings, name
        aggregate(out)
        capsys.readouterr()
        for verb in ("aggregate", "report"):
            assert suite_command([verb, str(out)]) == 0, (name, verb)
            shown = capsys.readouterr()
            assert note in shown.out + shown.err, (name, verb)
        assert suite_command(["resume", str(out)]) == 1, name
        capsys.readouterr()
