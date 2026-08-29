"""Acceptance tests for the M46.5/M46.7/M46.11 declarative experiment module
(``suite.experiment``) + the M46.5 additive ``MassTrialRunner`` hooks.

Offline only — ``ScriptedAgent``-driven ("idle" / "measure-commit"), real
conflict-ladder / neutral-substrate worlds, no live model, no network. The
no-peeking guard test below references the agent registry key ``"llm"`` and
the drafter registry key ``"pressure"`` as plain strings inside a spec dict
— never the live-model agent class or generator function names those keys
resolve to — so it does not trip ``tests/suite/test_no_peeking_lint.py``
(a static source-text scan for the real identifiers appearing together).
"""

from __future__ import annotations

import json

import pytest
import yaml

from alienbio.suite.dist import Seed
from alienbio.suite.experiment import (
    ExperimentSpec,
    aggregate,
    load_spec,
    record_from_json,
    record_to_json,
    run_experiment,
    spec_from_dict,
    spec_to_dict,
)
from alienbio.suite.mass_trial import MassTrialRunner
from alienbio.suite.trial import TrialRecord

# ═══════════════════════════════════════════════════════════════════════════
# 1. load_spec — YAML round-trip + validation
# ═══════════════════════════════════════════════════════════════════════════


def _write_spec(tmp_path, **overrides) -> "object":
    payload = {
        "name": "t1",
        "axes": {"rung": ["single", "forced"]},
        "drafter": "conflict",
        "agent": "idle",
        "trials_per_condition": 2,
        "base_seed": 1,
    }
    payload.update(overrides)
    path = tmp_path / "spec.yaml"
    path.write_text(yaml.safe_dump(payload))
    return path


def test_load_spec_round_trips_from_yaml(tmp_path):
    path = _write_spec(tmp_path)
    spec = load_spec(path)

    assert spec.name == "t1"
    assert spec.axes == (("rung", ("single", "forced")),)
    assert spec.drafter == "conflict"
    assert spec.agent == "idle"
    assert spec.trials_per_condition == 2
    assert spec.base_seed == 1

    d = spec_to_dict(spec)
    assert spec_from_dict(d) == spec
    json.dumps(d)  # JSON-able


def test_load_spec_unknown_key_raises_naming_it(tmp_path):
    path = _write_spec(tmp_path, bogus_key="oops")
    with pytest.raises(ValueError, match="bogus_key"):
        load_spec(path)


def test_load_spec_missing_required_key_raises(tmp_path):
    payload = {
        "name": "t1",
        "axes": {"rung": ["single"]},
        "drafter": "conflict",
        # "agent" missing
        "trials_per_condition": 1,
        "base_seed": 1,
    }
    path = tmp_path / "spec.yaml"
    path.write_text(yaml.safe_dump(payload))
    with pytest.raises(ValueError, match="agent"):
        load_spec(path)


# ═══════════════════════════════════════════════════════════════════════════
# 2. run_experiment — end to end, offline (conflict + idle)
# ═══════════════════════════════════════════════════════════════════════════


def _conflict_idle_spec(name: str, trials_per_condition: int = 2, **overrides) -> ExperimentSpec:
    kwargs = dict(
        name=name,
        axes=(("rung", ("single", "forced")),),
        drafter="conflict",
        agent="idle",
        trials_per_condition=trials_per_condition,
        base_seed=42,
    )
    kwargs.update(overrides)
    return ExperimentSpec(**kwargs)


def test_run_experiment_end_to_end(tmp_path):
    spec = _conflict_idle_spec("e2e")
    out_dir = tmp_path / "run1"

    rmap = run_experiment(spec, out_dir=str(out_dir))

    assert len(rmap.cells) == 2
    for summary in rmap.cells.values():
        assert summary.stats.n == 2

    records_path = out_dir / "records.jsonl"
    lines = records_path.read_text().strip().splitlines()
    assert len(lines) == 4

    manifest = json.loads((out_dir / "manifest.json").read_text())
    assert manifest["trials_completed"] == 4
    assert manifest["git_commit"]
    assert len(manifest["spec_sha256"]) == 64
    all(c in "0123456789abcdef" for c in manifest["spec_sha256"])

    assert (out_dir / "map.json").exists()
    assert (out_dir / "map.csv").exists()
    assert (out_dir / "report.txt").exists()

    from alienbio.suite.experiment import render_report

    report = render_report(rmap, manifest)
    assert "rung=single" in report
    assert "rung=forced" in report
    assert "failed: 0" in report


# ═══════════════════════════════════════════════════════════════════════════
# 3. record_to_json / record_from_json round trip
# ═══════════════════════════════════════════════════════════════════════════


def test_record_json_round_trip(tmp_path):
    spec = _conflict_idle_spec("rt", trials_per_condition=1)
    rmap = run_experiment(spec, out_dir=str(tmp_path / "run"))
    record = rmap.records[0]

    d = record_to_json(record, "rung=single", 0)
    json.dumps(d, default=repr)  # must be dumpable
    rebuilt = record_from_json(d)

    assert rebuilt.objective_score == record.objective_score
    assert rebuilt.terminal_reason == record.terminal_reason
    assert rebuilt.condition_key == record.condition_key
    assert rebuilt.illegal_actions == record.illegal_actions
    assert record.brief is not None and rebuilt.brief is not None
    assert rebuilt.brief.max_turns == record.brief.max_turns
    assert [(a.kind, a.destructive, a.accepted, a.reason) for a in rebuilt.action_log] == [
        (a.kind, a.destructive, a.accepted, a.reason) for a in record.action_log
    ]


# ═══════════════════════════════════════════════════════════════════════════
# 4. Resume — only new trials drafted, FileExistsError without resume
# ═══════════════════════════════════════════════════════════════════════════


def test_resume_only_drafts_new_trials(tmp_path, monkeypatch):
    import alienbio.suite.experiment as experiment_mod

    calls: list[int] = []
    original = experiment_mod.DRAFTERS["conflict"]

    def counting(seed, dials, **kwargs):
        calls.append(1)
        return original(seed, dials, **kwargs)

    monkeypatch.setitem(experiment_mod.DRAFTERS, "conflict", counting)

    out_dir = tmp_path / "resume_run"
    spec1 = _conflict_idle_spec("resume", trials_per_condition=1)
    run_experiment(spec1, out_dir=str(out_dir))
    assert len(calls) == 2  # 2 conditions x 1 trial

    calls.clear()
    spec2 = _conflict_idle_spec("resume", trials_per_condition=2)
    run_experiment(spec2, out_dir=str(out_dir), resume=True)
    assert len(calls) == 2  # only the NEW (index=1) trial per condition

    lines = (out_dir / "records.jsonl").read_text().strip().splitlines()
    assert len(lines) == 4

    with pytest.raises(FileExistsError):
        run_experiment(spec2, out_dir=str(out_dir), resume=False)


# ═══════════════════════════════════════════════════════════════════════════
# 5. fixed_dials — reaches the runner, never the condition_key
# ═══════════════════════════════════════════════════════════════════════════


def test_fixed_dials_reach_brief_not_condition_key(tmp_path):
    spec = _conflict_idle_spec("fixed", trials_per_condition=1, fixed_dials={"max_turns": 2})
    rmap = run_experiment(spec, out_dir=str(tmp_path / "run"))

    assert len(rmap.records) == 2
    for record in rmap.records:
        assert record.brief is not None
        assert record.brief.max_turns == 2
        assert record.turns <= 2
        assert "max_turns" not in dict(record.condition_key)


# ═══════════════════════════════════════════════════════════════════════════
# 6. aggregate(out_dir) from the store alone matches the returned map
# ═══════════════════════════════════════════════════════════════════════════


def test_aggregate_matches_returned_map(tmp_path):
    spec = _conflict_idle_spec("agg", trials_per_condition=3)
    out_dir = tmp_path / "run"
    rmap = run_experiment(spec, out_dir=str(out_dir))

    rebuilt = aggregate(str(out_dir))

    assert set(rebuilt.cells) == set(rmap.cells)
    for key in rmap.cells:
        assert rebuilt.cells[key].stats.mean == rmap.cells[key].stats.mean
        assert rebuilt.cells[key].stats.n == rmap.cells[key].stats.n


# ═══════════════════════════════════════════════════════════════════════════
# 7. The no-peeking guard — checked before anything is drafted
# ═══════════════════════════════════════════════════════════════════════════


def test_no_peeking_guard_rejects_llm_on_pressure(tmp_path):
    spec = ExperimentSpec(
        name="peek",
        axes=(("pi", (0.0,)),),
        drafter="pressure",
        agent="llm",
        trials_per_condition=1,
        base_seed=1,
    )
    out_dir = tmp_path / "should_not_be_created"

    with pytest.raises(ValueError, match="no-peeking"):
        run_experiment(spec, out_dir=str(out_dir))

    assert not out_dir.exists()


# ═══════════════════════════════════════════════════════════════════════════
# 8. identify_pathway + measure-commit — the neutral capability substrate
# ═══════════════════════════════════════════════════════════════════════════


def test_identify_pathway_measure_commit_commits(tmp_path):
    spec = ExperimentSpec(
        name="ip",
        axes=(("pathway_length", (3,)),),
        drafter="identify_pathway",
        agent="measure-commit",
        trials_per_condition=1,
        base_seed=7,
    )
    rmap = run_experiment(spec, out_dir=str(tmp_path / "run"))

    assert len(rmap.records) == 1
    assert rmap.records[0].terminal_reason == "committed"


# ═══════════════════════════════════════════════════════════════════════════
# 9. mass_trial additive hooks — extra_dials / skip / on_trial
# ═══════════════════════════════════════════════════════════════════════════


def _tiny_drafter(seed, dials):
    from alienbio.suite.types import (
        AnswerObjective,
        CarveResult,
        GraderSpec,
        Motif,
        Question,
        TaskInstance,
    )
    from alienbio.suite.types import Answer as _Answer
    from alienbio.bio.chemistry import ChemistryImpl
    from alienbio.bio.world import Compartment, WorldImpl
    from alienbio.infra.entity import MockDat

    del seed
    chemistry = ChemistryImpl("chem", atoms={}, molecules={}, reactions={}, dat=MockDat("chem/tiny"))
    compartments = (Compartment(id="root", parent=None, kind="cell", volume=1.0, concentrations={}),)
    world = WorldImpl(chemistry, compartments)
    task = TaskInstance(
        archetype="tiny",
        world="world0",
        skeleton=CarveResult(motif=Motif(roles=(), edges=()), binding={}),
        objective=AnswerObjective(grader=GraderSpec(kind="json"), key=_Answer(value=1, kind="json")),
        question=Question(structured={}, kind="json"),
        setup={},
    )
    return world, task


def _tiny_agent_factory(seed, dials):
    from alienbio.suite.agent import Commit, ScriptedAgent
    from alienbio.suite.types import Answer as _Answer

    return ScriptedAgent((Commit(answer=_Answer(value=1, kind="json")),), seed=seed)


def test_mass_trial_extra_dials_and_hooks():
    seen: list[tuple[str, int, TrialRecord]] = []

    def on_trial(label, i, record):
        seen.append((label, i, record))

    rmap = MassTrialRunner().run(
        [("level", ("a",))],
        _tiny_drafter,
        _tiny_agent_factory,
        trials_per_condition=1,
        base_seed=Seed(1),
        extra_dials={"max_turns": 3},
        on_trial=on_trial,
    )

    assert len(seen) == 1
    record = rmap.records[0]
    assert record.brief is not None
    assert record.brief.max_turns == 3
    assert "max_turns" not in dict(record.condition_key)

    def skip(label, i):
        return record  # reuse the already-produced record, unconditionally

    calls: list[int] = []

    def counting_drafter(seed, dials):
        calls.append(1)
        return _tiny_drafter(seed, dials)

    rmap2 = MassTrialRunner().run(
        [("level", ("a",))],
        counting_drafter,
        _tiny_agent_factory,
        trials_per_condition=1,
        base_seed=Seed(1),
        skip=skip,
    )

    assert len(calls) == 0  # drafter never called: skip supplied the record
    assert rmap2.records == (record,)
