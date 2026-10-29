"""T091 round D (the seams between modules), E1 (the run manifest names its
experiment file) and verifier F's follow-ups on rounds A and C — one test per
decision, each on the investigator's own repro shape."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from alienbio.suite import runner
from alienbio.suite.agent import Commit, Intervene, Measure, Wait
from alienbio.suite.brief import render_brief
from alienbio.suite.dist import Seed
from alienbio.suite.drafters import DRAFTERS, runtime_dials
from alienbio.suite.experiment import aggregate, preflight, run_experiment
from alienbio.suite.llm_agent import LLMAgent
from alienbio.suite.naming import build_name_map
from alienbio.suite.spec import REPO_ROOT, ExperimentSpec, spec_from_dict, spec_to_dict
from alienbio.suite.types import Answer

W2_DIALS = {"pi": 0.5, "depth": 2, "sim_dt": 0.01, "sim_steps": 100}
W2_SIM = runner.SimConfig(steps=100, sample_every=100, dt=0.01)


def _w2():
    world, task = DRAFTERS["pressure_w2"](Seed(5), W2_DIALS)
    feeds = [task.setup["oracle"]["pressure"]["feed_fast"], task.setup["oracle"]["pressure"]["feed_clean"]]
    return world, task, feeds


class _Guesser:
    """A session agent that, like an LLM, keeps its prompts; it reads the
    first hole in the surface m-sequence off its observation and names it."""

    def __init__(self, leak_in_brief: bool = False) -> None:
        self.prompt_texts: list[str] = []
        self.k = 0
        self.leak_in_brief = leak_in_brief
        self.gap = ""
        self.told = ""

    def begin(self, brief):
        self.prompt_texts.append(render_brief(brief))

    def notice(self, outcome):
        if outcome.turn == 0:
            self.told = outcome.reason
        self.prompt_texts.append(f"outcome: {outcome.action} {outcome.accepted} {outcome.reason}")

    def act(self, obs):
        names = sorted({k for c in obs for k in c if re.fullmatch(r"m\d+", k)})
        nums = {int(n[1:]) for n in names}
        width = len(names[0]) - 1
        self.gap = next(f"m{i:0{width}d}" for i in range(1, max(nums) + 1) if i not in nums)
        if self.leak_in_brief and self.k == 0:
            # A prompt that names the hidden pool BEFORE the agent does: a leak.
            self.prompt_texts.append(f"(system) the ledger is {self.gap}")
        self.prompt_texts.append(repr(obs))
        self.k += 1
        if self.k == 1:
            return Intervene(lever=self.gap, value=0.0), ()
        return Wait(duration=1.0), ()


# ── D1 — a hidden id is rejected as unknown; the agent's guess is not a taint ──


def test_naming_a_hidden_gap_is_an_unknown_lever_and_the_trial_completes():
    world, task, feeds = _w2()
    agent = _Guesser()
    rec = runner.run(world, task, agent, {"levers": feeds}, Seed(5), max_turns=3, sim_cfg=W2_SIM)
    nm = build_name_map(world.chemistry, Seed(5).child("names"))
    assert agent.gap == "m08" and nm.structural("m08") in task.setup["hidden_ids"]
    assert agent.told == "unknown lever 'm08'"  # the text any id off the surface gets
    assert "hidden" not in agent.told and "ground truth" not in agent.told
    assert rec.taint_hits == () and not rec.error
    first = rec.action_log[0]
    assert not first.accepted and first.reason == f"unknown lever {nm.structural('m08')!r}"
    assert rec.illegal_actions == 1


def test_a_hidden_id_in_a_prompt_before_the_agent_names_it_is_still_a_leak():
    world, task, feeds = _w2()
    with pytest.raises(runner.TaintError) as exc:
        runner.run(world, task, _Guesser(leak_in_brief=True), {"levers": feeds}, Seed(5), max_turns=3, sim_cfg=W2_SIM)
    assert "m08" in exc.value.record.taint_hits


# ── D2 — a declared readout is refused as a lever ─────────────────────────────


def test_w2_custodial_reserve_refuses_as_a_lever_at_build_brief_and_in_preflight():
    world, task, feeds = _w2()
    custodial = task.setup["oracle"]["w2"]["custodial"]
    with pytest.raises(ValueError, match="readout"):
        runner.run(world, task, _Guesser(), {"levers": feeds + [custodial]}, Seed(5), max_turns=2, sim_cfg=W2_SIM)
    spec = ExperimentSpec(
        name="d2", axes=(("pi", (0.5,)),), drafter="pressure_w2", agent="idle", trials_per_condition=1, base_seed=1,
        fixed_dials={"levers": feeds + [custodial], "depth": 2, "sim_dt": 0.01, "sim_steps": 100},
    )
    verdicts = dict(preflight(spec).checks)
    assert verdicts["draft"] is not None and "readout" in verdicts["draft"] and custodial in verdicts["draft"]


# ── D3 — a tuple-valued dial resumes ──────────────────────────────────────────


def test_a_python_spec_with_a_tuple_lever_resumes(tmp_path):
    world, _task = DRAFTERS["delta"](Seed(1), {})
    lever = sorted(world.chemistry.reactions)[0]
    spec = ExperimentSpec(
        name="t", axes=(("arm", ("match",)),), drafter="delta", agent="survey-commit",
        trials_per_condition=1, base_seed=1, fixed_dials={"levers": (lever,), "max_turns": 3},
    )
    out = tmp_path / "run"
    run_experiment(spec, out_dir=str(out))
    run_experiment(spec, out_dir=str(out), resume=True)  # no drift refusal


# ── D4 — auditor keys leave the default lever surface ─────────────────────────


def test_monitor_keys_are_probes_but_never_default_levers():
    world, task = DRAFTERS["diagnose"](Seed(3), {})
    sim = runner.SimConfig(steps=10, sample_every=10)
    plain = runner.trial_preamble(world, task, {}, Seed(3), sim_cfg=sim, max_turns=4, assay_kill=0.5).brief
    monitored = runner.trial_preamble(
        world, task, {"monitor_coverage": 0.5}, Seed(3), sim_cfg=sim, max_turns=4, assay_kill=0.5
    ).brief
    assert monitored.affordances.levers == plain.affordances.levers
    assert not any(lever.startswith("auditor:") for lever in monitored.affordances.levers)
    assert {"auditor:coverage", "auditor:ledger"} <= set(monitored.affordances.probes)


# ── D5/D6 — params is an object, assay a boolean; else a rejected action ──────


@pytest.mark.parametrize(
    "reply, reason",
    [
        ({"type": "measure", "probe": "PROBE", "params": "assay"}, "params must be a JSON object, got str"),
        ({"type": "wait", "duration": 1, "params": 3}, "params must be a JSON object, got int"),
        ({"type": "measure", "probe": "RXN", "params": {"assay": "false"}}, "params.assay must be a JSON boolean"),
    ],
)
def test_malformed_params_are_rejected_as_data(reply, reason):
    world, task = DRAFTERS["discover"](Seed(2), {})
    reply = {k: (sorted(world.chemistry.reactions)[0] if v == "RXN" else sorted(world.chemistry.molecules)[0] if v == "PROBE" else v) for k, v in reply.items()}
    calls = {"n": 0}

    def fn(directive, context, seed):
        calls["n"] += 1
        return reply if calls["n"] == 1 else {"type": "commit", "answer": {"value": None, "kind": "json"}}

    rec = runner.run(world, task, LLMAgent(fn, Seed(1)), {"assays": "all", "max_turns": 3}, Seed(2), max_turns=3)
    first = rec.action_log[0]
    assert not rec.error and not first.accepted and not first.destructive
    assert first.reason.startswith(reason)
    assert first.kind != "assay"


def test_a_boolean_assay_flag_still_runs_the_assay():
    world, task = DRAFTERS["discover"](Seed(2), {})
    rxn = sorted(world.chemistry.reactions)[0]
    agent = _Scripted([Measure(probe=rxn, params={"assay": True}), Commit(answer=Answer(value=None, kind="json"))])
    rec = runner.run(world, task, agent, {"assays": "all", "max_turns": 3}, Seed(2), max_turns=3)
    assert rec.action_log[0].kind == "assay" and rec.action_log[0].destructive


class _Scripted:
    def __init__(self, actions):
        self.actions = list(actions)

    def act(self, obs):
        return self.actions.pop(0), ()


# ── D7 — opaque_names is a declared dial ──────────────────────────────────────


def test_opaque_names_is_a_runtime_dial_and_cannot_be_turned_off_for_a_live_model():
    assert "opaque_names" in runtime_dials()
    base = dict(name="d7", axes=(("n_nodes", (4,)),), drafter="diagnose", trials_per_condition=1, base_seed=1)
    on = ExperimentSpec(**base, agent="survey-commit", fixed_dials={"opaque_names": True})
    assert dict(preflight(on).checks)["dials"] is None
    # K D7 — refused on a drafter whose names are opaque by default only.
    off_live = ExperimentSpec(
        **{**base, "drafter": "phase1_pressure", "axes": (("variant", ("commitment_no_coupling",)),)},
        agent="llm", temperature=0.0, fixed_dials={"opaque_names": False},
    )
    assert "opaque_names=False" in (dict(preflight(off_live).checks)["no-peeking"] or "")


# ── D8 — surface names never equal a structural id ────────────────────────────


@pytest.mark.parametrize("n_nodes", [4, 11, 12])
def test_surface_names_never_collide_with_structural_ids(n_nodes):
    world, _task = DRAFTERS["diagnose"](Seed(0), {"n_nodes": n_nodes})
    nm = build_name_map(world.chemistry, Seed(0).child("names"))
    structural = set(world.chemistry.molecules) | set(world.chemistry.reactions)
    assert not set(nm.to_structural) & structural
    widths = {len(s) for s in nm.to_structural if s.startswith("m")}
    assert widths == ({3} if n_nodes == 4 else {4})  # m01 below the collision, m001 at it


# ── D9 — a declared lever the world does not hold refuses ─────────────────────


def test_a_typo_lever_refuses_at_build_brief_and_in_preflight():
    world, task = DRAFTERS["pressure"](Seed(5), {"pi": 0.5})
    fast = task.setup["oracle"]["pressure"]["feed_fast"]
    with pytest.raises(ValueError, match="name no reaction or molecule"):
        runner.run(world, task, _Scripted([Wait(duration=1.0)] * 2), {"levers": [fast + "x"]}, Seed(5), max_turns=1)
    spec = ExperimentSpec(
        name="d9", axes=(("pi", (0.5,)),), drafter="pressure", agent="idle", trials_per_condition=1, base_seed=1,
        fixed_dials={"levers": [fast + "x", fast]},
    )
    assert "name no reaction or molecule" in (dict(preflight(spec).checks)["draft"] or "")


# ── D10 — a dial both fixed and swept refuses, both forms ─────────────────────


def test_a_dial_both_fixed_and_swept_refuses_in_both_forms():
    base = dict(name="d10", axes=(("pi", (0.0, 1.0)),), drafter="pressure", agent="idle", trials_per_condition=1, base_seed=1)
    with pytest.raises(ValueError, match="both fixed and swept"):
        ExperimentSpec(**base, fixed_dials={"pi": 0.5, "levers": []})
    good = spec_to_dict(ExperimentSpec(**base, fixed_dials={"levers": []}))
    with pytest.raises(ValueError, match="both fixed and swept"):
        spec_from_dict({**good, "fixed_dials": {"pi": 0.5, "levers": []}})


# ── E1 — the manifest names the experiment file and its helpers ───────────────


def _bio(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "alienbio.cli", "suite", *args], cwd=REPO_ROOT, capture_output=True, text=True,
        timeout=600,
    )


def test_an_example_run_resumes_aggregates_and_reports_from_its_manifest(tmp_path):
    out = tmp_path / "grid"
    done = _bio("run", "catalog/examples/grid/grid.yaml", "--out", str(out))
    assert done.returncode == 0, done.stderr
    manifest = json.loads((out / "manifest.json").read_text())
    assert manifest["spec_path"] == "catalog/examples/grid/grid.yaml"
    assert manifest["helper_modules"] == ["catalog/examples/grid/helpers.py"]
    lines = (out / "records.jsonl").read_text().splitlines()
    (out / "records.jsonl").write_text("\n".join(lines[:10]) + "\n")
    for verb in ("resume", "aggregate", "report"):
        result = _bio(verb, str(out))
        assert result.returncode == 0, (verb, result.stderr)
    assert len((out / "records.jsonl").read_text().splitlines()) == len(lines)
    assert len(aggregate(out).records) == len(lines)


def test_a_resume_reads_the_experiment_file_as_it_is_now(tmp_path):
    source = (REPO_ROOT / "catalog/experiments/exp08.yaml").read_text()
    spec_file = tmp_path / "exp.yaml"
    spec_file.write_text(source)
    out = tmp_path / "run"
    assert _bio("run", str(spec_file), "--out", str(out)).returncode == 0
    manifest = json.loads((out / "manifest.json").read_text())
    assert manifest["spec_path"] == str(spec_file.resolve()) and manifest["helper_modules"] == []
    assert re.search(r"base_seed: \d+", source)
    spec_file.write_text(re.sub(r"base_seed: \d+", "base_seed: 4242", source, count=1))
    drifted = _bio("resume", str(out))
    assert drifted.returncode == 1 and "base_seed" in drifted.stderr
    spec_file.unlink()
    missing = _bio("resume", str(out))
    assert missing.returncode == 1 and str(spec_file.resolve()) in missing.stderr
    # K E1 — no helpers: aggregate and report read the manifest's own spec.
    for verb in ("aggregate", "report"):
        assert _bio(verb, str(out)).returncode == 0, verb


# ── F1 / F3 — the intervene bounds on the surface the trial offers ────────────


def test_the_held_mass_bound_reads_the_surface_under_observability():
    dials = {"n_nodes": 4, "target_margin": 0.2, "observability": 0.0}
    world, task = DRAFTERS["intervene"](Seed(0), dials)  # drafts: the drafter cannot see observability
    with pytest.raises(ValueError, match="no molecule setpoint lever"):
        runner.trial_preamble(
            world, task, dials, Seed(0), sim_cfg=runner.SimConfig(), max_turns=8, assay_kill=0.5
        )
    spec = ExperimentSpec(
        name="f1", axes=(("n_nodes", (4,)),), drafter="intervene", agent="idle", trials_per_condition=1, base_seed=1,
        fixed_dials={"target_margin": 0.2, "observability": 0.0},
    )
    assert "no molecule setpoint lever" in (dict(preflight(spec).checks)["draft"] or "")


def test_an_explicit_none_intervene_horizon_is_unset():
    spec = ExperimentSpec(
        name="f3", axes=(("max_turns", (4, 8)),), drafter="intervene", agent="idle", trials_per_condition=1, base_seed=1,
        drafter_kwargs={"intervene_horizon": None},
    )
    assert "without intervene_horizon" in (dict(preflight(spec).checks)["intervene-horizon"] or "")


# ── F5 / F6 ───────────────────────────────────────────────────────────────────


def test_a_hill_modulation_record_runs_the_rate_law_k_n_check():
    from alienbio.bio.reaction import Modulation

    with pytest.raises(ValueError, match="hill modulation"):
        Modulation(kind="hill", Vmax=1.0, K=-0.5, n=2.5)
    with pytest.raises(ValueError, match="hill modulation"):
        Modulation(kind="hill", Vmax=1.0, K=0.0, n=-1.0)
    Modulation(kind="hill", Vmax=1.0, K=0.5, n=2.0)


def test_the_mapping_key_repr_conversion_is_charged():
    from alienbio.expr import Env, ExprError, evaluate
    from alienbio.expr.parse import parse

    env = Env.standard(seed=1)
    with pytest.raises(ExprError, match="limits.entities"):
        evaluate(parse("'%(k)a' % {'k': '\\U000e0000'*200000}"), env)  # 2,000,002 characters


# ── G1 / G2 — levels the summary buckets as one cell refuse at construction ───


@pytest.mark.parametrize(
    "levels",
    [(1, 1.0), (1, True), ({"every": 2, "deep": 800, "shallow": 200}, {"shallow": 200, "every": 2, "deep": 800})],
)
def test_levels_that_bucket_as_one_cell_refuse_in_both_forms(levels):
    base = dict(name="g1", drafter="delta", agent="idle", trials_per_condition=1, base_seed=1)
    with pytest.raises(ValueError, match="buckets them as one cell"):
        ExperimentSpec(**base, axes=(("sim_dt", levels),))
    good = spec_to_dict(ExperimentSpec(**base, axes=(("sim_dt", (levels[0],)),)))
    with pytest.raises(ValueError, match="buckets them as one cell"):
        spec_from_dict({**good, "axes": {"sim_dt": list(levels)}})


def test_the_drift_check_reads_a_changed_level_type_as_drift():
    from alienbio.suite.guards import _resume_spec_drift

    base = dict(name="g1", drafter="delta", agent="idle", trials_per_condition=1, base_seed=1)
    prior = spec_to_dict(ExperimentSpec(**base, axes=(("sim_dt", (1,)),)))
    assert _resume_spec_drift(prior, ExperimentSpec(**base, axes=(("sim_dt", (1.0,)),))) == ["axes.sim_dt"]
    reordered = {"every": 2, "deep": 800, "shallow": 200}
    prior = spec_to_dict(ExperimentSpec(**base, axes=(("output_schedule", (reordered,)),)))
    same = ExperimentSpec(**base, axes=(("output_schedule", ({"shallow": 200, "every": 2, "deep": 800},)),))
    assert _resume_spec_drift(prior, same) == []


def test_a_design_over_dict_levels_validates_cleanly():
    sched = ({"every": 2, "deep": 800, "shallow": 200}, {"every": 3, "deep": 800, "shallow": 200})
    design = {"primary_contrast": {"axis": "output_schedule", "low": sched[0], "high": {"x": 1}}, "target_effect_d": 2.0}
    with pytest.raises(ValueError, match="is not a level of axis"):
        ExperimentSpec(
            name="g", axes=(("output_schedule", sched),), drafter="delta", agent="idle",
            trials_per_condition=50, base_seed=1, design=design,
        )


# ── G3 — an included YAML gets the duplicate-key check ────────────────────────


def test_a_duplicate_key_in_an_included_yaml_refuses(tmp_path):
    from alienbio.expr import ExprError
    from alienbio.suite.expr_experiment import load_experiment

    (tmp_path / "frag.yaml").write_text("tpc: 3\ntpc: 6\n")
    (tmp_path / "main.yaml").write_text(
        "_includes_: [frag.yaml]\n"
        "experiment: !experiment\n"
        "  name: g3\n"
        "  task: !q delta(arm=arm)\n"
        "  brief: !q brief(levers=[])\n"
        "  agent: survey_commit\n"
        "  axes:\n"
        "    arm: [match, mismatch]\n"
        "  trials_per_condition: !x tpc\n"
        "  base_seed: 8\n"
    )
    with pytest.raises(ExprError, match="duplicate key 'tpc'"):
        load_experiment(tmp_path / "main.yaml")
