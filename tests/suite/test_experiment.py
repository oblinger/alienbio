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
    AGENTS,
    DRAFTERS,
    CostEstimate,
    ExperimentSpec,
    aggregate,
    estimate_cost,
    load_spec,
    record_from_json,
    record_to_json,
    run_experiment,
    spec_from_dict,
    spec_to_dict,
)
from alienbio.suite.llm_agent import cost_usd
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


def test_load_spec_refuses_a_floating_model_alias(tmp_path):
    # M45.11: a run pins a dated generation; an alias would make two runs that
    # name the same id incomparable.
    for alias in ("claude-sonnet-4-latest", "claude-sonnet-4", ""):
        path = _write_spec(tmp_path, model=alias)
        with pytest.raises(ValueError, match="model"):
            load_spec(path)
    spec = load_spec(_write_spec(tmp_path, model="claude-sonnet-4-20250514"))
    assert spec.model == "claude-sonnet-4-20250514"


def test_agent_axis_runs_control_arms_in_one_grid(tmp_path, monkeypatch):
    # M46.8: agent kind as a grid axis — every arm shares the world seeds.
    spec = load_spec(
        _write_spec(tmp_path, axes={"rung": ["single"], "agent": ["idle", "measure-commit"]}, agent="idle")
    )
    draft_seeds: dict[str, list[int]] = {}
    original = DRAFTERS["conflict"]

    def spying(seed, dials, **kwargs):
        draft_seeds.setdefault(str(dials["agent"]), []).append(seed.value)
        return original(seed, dials, **kwargs)

    monkeypatch.setitem(DRAFTERS, "conflict", spying)
    rmap = run_experiment(spec, out_dir=str(tmp_path / "out"))
    assert len(rmap.cells) == 2
    lines = [json.loads(l) for l in (tmp_path / "out" / "records.jsonl").read_text().splitlines()]
    assert {d["agent"] for d in lines} == {"idle", "measure-commit"}
    assert all(d["model"] is None for d in lines)
    # Matched arms: both agent levels drafted their worlds from identical seeds.
    assert draft_seeds["idle"] == draft_seeds["measure-commit"]
    assert len(draft_seeds["idle"]) == 2


def test_agent_axis_with_llm_is_refused_on_a_non_neutral_drafter(tmp_path):
    spec = load_spec(_write_spec(tmp_path, axes={"rung": ["single"], "agent": ["idle", "llm"]}))
    with pytest.raises(ValueError, match="no-peeking"):
        run_experiment(spec, out_dir=str(tmp_path / "out"))


def test_axis_levels_are_validated_at_load(tmp_path):
    with pytest.raises(ValueError, match="agent axis"):
        load_spec(_write_spec(tmp_path, axes={"agent": ["idle", "bogus"]}))
    with pytest.raises(ValueError, match="model"):
        load_spec(_write_spec(tmp_path, axes={"model": ["claude-sonnet-4-latest"]}))


def test_design_refuses_an_underpowered_spec_and_is_recorded(tmp_path):
    # M46.9: a declared design sizes the run; too few trials is refused at load.
    design = {"target_effect_d": 2.0, "primary_contrast": {"axis": "rung", "low": "single", "high": "forced"}}
    with pytest.raises(ValueError, match="trials per condition"):
        load_spec(_write_spec(tmp_path, design=design, trials_per_condition=2))
    with pytest.raises(ValueError, match="not a swept axis"):
        load_spec(_write_spec(tmp_path, design={"target_effect_d": 2.0, "primary_contrast": {"axis": "pi", "low": 0, "high": 1}}, trials_per_condition=9))
    # d=2.0: 2*(2.8016/2)^2 = 3.92 -> 4, +1 = 5 trials per condition.
    spec = load_spec(_write_spec(tmp_path, design=design, trials_per_condition=5))
    assert spec.design is not None and spec.design.required_trials_per_condition == 5
    rmap = run_experiment(spec, out_dir=str(tmp_path / "out"))
    manifest = json.loads((tmp_path / "out" / "manifest.json").read_text())
    assert manifest["design"]["required_trials_per_condition"] == 5
    report = (tmp_path / "out" / "report.txt").read_text()
    assert "Design (M46.9" in report and "(ok)" in report
    assert "primary contrast rung: single -> forced" in report
    assert len(rmap.records) == 10


def test_idle_baseline_flag_adds_the_matched_idle_arm(tmp_path):
    # M45.7: idle_baseline: true expands the grid with an agent axis of
    # (agent, idle) so every condition has a do-nothing twin under the same seeds.
    spec = load_spec(_write_spec(tmp_path, agent="measure-commit", idle_baseline=True))
    assert ("agent", ("measure-commit", "idle")) in spec.axes
    assert spec_from_dict(spec_to_dict(spec)).axes == spec.axes  # no double expansion
    rmap = run_experiment(spec, out_dir=str(tmp_path / "out"))
    assert len(rmap.cells) == 4
    report = (tmp_path / "out" / "report.txt").read_text()
    assert "Idle baseline (M45.7" in report and "measure-commit=" in report and "idle=" in report
    # A spec whose agent is already idle, or which sweeps agent itself, is left alone.
    assert not any(n == "agent" for n, _ in load_spec(_write_spec(tmp_path, agent="idle", idle_baseline=True)).axes)


def test_control_archetypes_grade_from_ground_truth(tmp_path):
    # M45.8: commit-the-link and describe-the-world on the pressure world —
    # a scripted agent committing the key scores 1.0, a null commit 0.0.
    from alienbio.suite.agent import Commit, ScriptedAgent
    from alienbio.suite.runner import run as run_trial
    from alienbio.suite.types import Answer, AnswerObjective

    for name in ("commit_the_link", "describe_the_world"):
        world, task = DRAFTERS[name](Seed(4), {"pi": 0.5, "complexity": 1})
        assert isinstance(task.objective, AnswerObjective)
        key = task.objective.key.value
        assert key and all(isinstance(k, str) for k in key)
        if name == "commit_the_link":
            assert set(key) <= set(world.chemistry.molecules)
            assert task.question.structured["marked"] in world.chemistry.molecules
        else:
            assert all("->" in edge for edge in key)
            assert len(key) == len(world.chemistry.reactions)

        perfect = ScriptedAgent((Commit(answer=Answer(value=list(key), kind="node_set")),), seed=Seed(0))
        assert run_trial(world, task, perfect, {}, Seed(1)).objective_score == 1.0
        null = ScriptedAgent((Commit(answer=Answer(value=[], kind="node_set")),), seed=Seed(0))
        assert run_trial(world, task, null, {}, Seed(1)).objective_score == 0.0

    # Both are pressure substrates: a live model is refused on them.
    spec = load_spec(_write_spec(tmp_path, drafter="commit_the_link", agent="llm", axes={"pi": [0.5]}))
    with pytest.raises(ValueError, match="no-peeking"):
        run_experiment(spec, out_dir=str(tmp_path / "out"))


def test_record_lines_carry_model_and_memory(tmp_path):
    spec = load_spec(_write_spec(tmp_path))
    run_experiment(spec, out_dir=str(tmp_path / "out"))
    lines = [json.loads(l) for l in (tmp_path / "out" / "records.jsonl").read_text().splitlines()]
    assert lines and all("model" in d and d["memory"] == "full" for d in lines)
    assert all(d["model"] is None for d in lines)  # a scripted run has no model


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


# ═══════════════════════════════════════════════════════════════════════════
# 10. estimate_cost / cost_ceiling_usd (M45.5)
# ═══════════════════════════════════════════════════════════════════════════


def test_estimate_cost_scripted_spec_is_zero():
    spec = _conflict_idle_spec("est-scripted")
    estimate = estimate_cost(spec)
    assert isinstance(estimate, CostEstimate)
    assert estimate.llm_trials == 0
    assert estimate.usd == 0.0
    assert estimate.model is None


def test_estimate_cost_agent_axis_matches_hand_computed_formula():
    spec = ExperimentSpec(
        name="est-axis",
        axes=(("rung", ("single", "forced")), ("agent", ("idle", "llm"))),
        drafter="conflict",
        agent="idle",
        trials_per_condition=2,
        base_seed=1,
        model="claude-sonnet-4-20250514",
        price_usd_per_mtok=(1.0, 2.0),
        expected_turns=4,
        expected_prompt_tokens=100,
        expected_output_tokens=10,
    )
    estimate = estimate_cost(spec)

    # 1 "llm" agent-axis level x 2 "rung" levels x 2 trials_per_condition.
    assert estimate.llm_trials == 1 * 2 * 2
    assert estimate.turns_per_trial == 4

    # memory defaults to "full": sum_{t=0}^{3} 100 * (1 + t/2).
    input_per_trial = sum(100 * (1 + t / 2) for t in range(4))
    output_per_trial = 10 * 4
    expected_input_tokens = round(input_per_trial * estimate.llm_trials)
    expected_output_tokens = round(output_per_trial * estimate.llm_trials)
    assert estimate.input_tokens == expected_input_tokens
    assert estimate.output_tokens == expected_output_tokens

    expected_usd = cost_usd(expected_input_tokens, expected_output_tokens, (1.0, 2.0))
    assert estimate.usd == pytest.approx(expected_usd)
    assert estimate.model == "claude-sonnet-4-20250514"


def test_estimate_cost_unknown_model_without_override_raises():
    spec = ExperimentSpec(
        name="est-unknown",
        axes=(),
        drafter="identify_pathway",
        agent="llm",
        trials_per_condition=1,
        base_seed=1,
        model="totally-unknown-model-20260101",
    )
    with pytest.raises(ValueError, match="no published price"):
        estimate_cost(spec)


def test_load_spec_rejects_negative_cost_ceiling(tmp_path):
    path = _write_spec(tmp_path, cost_ceiling_usd=-1.0)
    with pytest.raises(ValueError, match="cost_ceiling_usd"):
        load_spec(path)


def test_cost_ceiling_stops_the_run_after_first_trial(tmp_path, monkeypatch):
    from alienbio.suite.agent import Commit as _Commit
    from alienbio.suite.types import Answer as _Answer

    class _BigUsageAgent:
        def act(self, observation):
            del observation
            return _Commit(answer=_Answer(value=[], kind="ordered_path")), ()

        @property
        def usage(self):
            return {
                "calls": 1,
                "input_tokens": 1_000_000,
                "output_tokens": 0,
                "cache_read_tokens": 0,
                "cache_write_tokens": 0,
            }

    def big_usage_agent_builder(spec):
        def factory(seed, dials):
            del seed, dials
            return _BigUsageAgent()

        return factory

    monkeypatch.setitem(AGENTS, "idle", big_usage_agent_builder)

    spec = ExperimentSpec(
        name="ceiling",
        axes=(("rung", ("single",)),),
        drafter="conflict",
        agent="idle",
        trials_per_condition=2,
        base_seed=1,
        price_usd_per_mtok=(3.0, 15.0),
        cost_ceiling_usd=2.0,
    )
    out_dir = tmp_path / "run"
    rmap = run_experiment(spec, out_dir=str(out_dir))

    assert rmap.provenance.stopped_early is True
    assert len(rmap.records) == 1

    manifest = json.loads((out_dir / "manifest.json").read_text())
    assert manifest["stopped_reason"] == "cost_ceiling"
    assert manifest["cost_usd_spent"] >= 2.0

    lines = (out_dir / "records.jsonl").read_text().strip().splitlines()
    assert len(lines) == 1
