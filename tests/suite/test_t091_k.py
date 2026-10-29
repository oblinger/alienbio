"""T091 verifier K's follow-ups on round D — one test per Pilot decision,
each on K's own repro shape (K1 rejected commits, K2 the runtime lever
text, K3 the taint exemption on the record, E1, G1, F1, F6, D7)."""

from __future__ import annotations

import json

import numpy as np
import pytest

from alienbio.suite import runner
from alienbio.suite.dist import Seed
from alienbio.suite.drafters import DRAFTERS, OPAQUE_SETUP_DRAFTERS, guarded_drafters
from alienbio.suite.experiment import aggregate, preflight, run_experiment
from alienbio.suite.llm_agent import LLMAgent
from alienbio.suite.naming import build_name_map
from alienbio.suite.spec import REPO_ROOT, ExperimentSpec, load_spec
from alienbio.suite.store import _canonical_json, record_from_json, record_to_json
from alienbio.suite.agent import Intervene, Wait

W2_DIALS = {"pi": 0.5, "depth": 2, "sim_dt": 0.01, "sim_steps": 100}
W2_SIM = runner.SimConfig(steps=100, sample_every=100, dt=0.01)
_ABSENT = object()


def _w2():
    world, task = DRAFTERS["pressure_w2"](Seed(5), W2_DIALS)
    oracle = task.setup["oracle"]
    return world, task, [oracle["pressure"]["feed_fast"], oracle["pressure"]["feed_clean"]]


def _scripted_llm(replies):
    """An ``llm_fn`` returning ``replies`` in order, then waits."""
    calls = {"n": 0}

    def fn(directive, context, seed):
        calls["n"] += 1
        return replies[calls["n"] - 1] if calls["n"] <= len(replies) else {"type": "wait", "duration": 1}

    return fn


# ── K1 — a non-object params is a rejected action; a rejected Commit goes on ──


def _commit(params):
    reply = {"type": "commit", "answer": {"value": None, "kind": "json"}}
    if params is not _ABSENT:
        reply["params"] = params
    return reply


@pytest.mark.parametrize("params", [[], "", False, 3])
def test_a_commit_with_non_object_params_is_rejected_and_the_trial_goes_on(params):
    world, task = DRAFTERS["discover"](Seed(2), {})
    final = {"type": "commit", "answer": {"value": None, "kind": "json"}}
    fn = _scripted_llm([_commit(params), {"type": "wait", "duration": 1}, final])
    rec = runner.run(world, task, LLMAgent(fn, Seed(1)), {"max_turns": 5}, Seed(2), max_turns=5)
    first = rec.action_log[0]
    assert not rec.error and not first.accepted and first.kind == "commit"
    assert first.reason == f"params must be a JSON object, got {type(params).__name__}"
    assert rec.illegal_actions == 1 and rec.turns == 3 and rec.terminal_reason == "committed"


def test_a_rejected_commit_never_asserts_an_answer_and_runs_to_the_limit():
    world, task = DRAFTERS["discover"](Seed(2), {})
    fn = _scripted_llm([_commit([]), _commit("")])
    rec = runner.run(
        world, task, LLMAgent(fn, Seed(1)), {"max_turns": 5}, Seed(2), max_turns=5, illegal_action_limit=2
    )
    assert rec.terminal_reason == "illegal_limit" and rec.answer is None and rec.objective_score == 0.0


@pytest.mark.parametrize("params", [None, _ABSENT])
def test_absent_or_null_params_read_as_an_empty_object(params):
    world, task = DRAFTERS["discover"](Seed(2), {})
    wait = {"type": "wait", "duration": 1}
    if params is not _ABSENT:
        wait["params"] = params
    fn = _scripted_llm([wait, _commit(params)])
    rec = runner.run(world, task, LLMAgent(fn, Seed(1)), {"max_turns": 5}, Seed(2), max_turns=5)
    assert all(a.accepted for a in rec.action_log) and rec.illegal_actions == 0
    assert rec.terminal_reason == "committed" and rec.turns == 2


@pytest.mark.parametrize("params", [[], "", False, 3])
def test_every_action_kind_rejects_a_non_object_params(params):
    world, task = DRAFTERS["discover"](Seed(2), {})
    probe = sorted(world.chemistry.molecules)[0]
    fn = _scripted_llm(
        [
            {"type": "wait", "duration": 1, "params": params},
            {"type": "measure", "probe": probe, "params": params},
            _commit(None),
        ]
    )
    rec = runner.run(world, task, LLMAgent(fn, Seed(1)), {"max_turns": 5}, Seed(2), max_turns=5)
    assert [a.accepted for a in rec.action_log] == [False, False, True]


# ── K2 — at runtime a readout or hidden pool gets the typo text ───────────────


class _Lever:
    def __init__(self, lever):
        self.lever = lever
        self.told = None
        self.k = 0

    def begin(self, brief):
        pass

    def notice(self, outcome):
        if outcome.turn == 0:
            self.told = outcome.reason

    def act(self, obs):
        self.k += 1
        return (Intervene(lever=self.lever, value=0.0) if self.k == 1 else Wait(duration=1.0)), ()


def test_an_intervene_on_the_w2_custodial_reserve_is_an_unknown_lever():
    world, task, feeds = _w2()
    custodial = task.setup["oracle"]["w2"]["custodial"]
    nm = build_name_map(world.chemistry, Seed(5).child("names"))
    spoken = nm.surface(custodial)
    agent = _Lever(spoken)
    rec = runner.run(world, task, agent, {"levers": feeds}, Seed(5), max_turns=2, sim_cfg=W2_SIM)
    assert agent.told == f"unknown lever {spoken!r}"
    assert rec.action_log[0].reason == f"unknown lever {custodial!r}"
    assert "readout" not in agent.told and "measurement" not in rec.action_log[0].reason


@pytest.mark.parametrize("hidden", [True, False])
def test_an_opaque_world_echoes_the_agents_own_structural_token(hidden):
    world, task, feeds = _w2()
    structural = sorted(task.setup["hidden_ids"])[0]
    lever = structural if hidden else structural + "x"  # the pool, and a structural-looking typo
    agent = _Lever(lever)
    runner.run(world, task, agent, {"levers": feeds}, Seed(5), max_turns=2, sim_cfg=W2_SIM)
    assert agent.told == f"unknown lever {lever!r}"


# ── K3 — the agent's own words are exempt, and the record says so ────────────


def test_a_hidden_id_in_the_agents_reasoning_is_exempt_and_recorded():
    world, task, feeds = _w2()
    fn = _scripted_llm([{"type": "wait", "duration": 1, "reasoning": "m08 is missing from the observation"}])
    rec = runner.run(
        world, task, LLMAgent(fn, Seed(1), memory="full"), {"levers": feeds}, Seed(5), max_turns=3, sim_cfg=W2_SIM
    )
    assert rec.taint_hits == () and not rec.error
    assert dict(rec.taint_exempt) == {"m08": 1}  # the reply to prompt 0; prompt 1 on
    line = record_to_json(rec, "c", 0)
    assert line["taint_exempt"] == {"m08": 1}
    assert json.loads(_canonical_json(line))["taint_exempt"] == {"m08": 1}  # strict JSON as written
    assert dict(record_from_json(line).taint_exempt) == {"m08": 1}


def test_a_hidden_id_a_prompt_carries_before_the_agent_names_it_still_refuses():
    world, task, feeds = _w2()
    fn = _scripted_llm([{"type": "wait", "duration": 1, "reasoning": "so m08 it is"}])
    with pytest.raises(runner.TaintError) as exc:
        runner.run(
            world, task, LLMAgent(fn, Seed(1), memory="full"),
            {"levers": feeds, "protocol": "First look at m08."}, Seed(5), max_turns=3, sim_cfg=W2_SIM,
        )
    assert "m08" in exc.value.record.taint_hits


def test_a_clean_trial_writes_no_exemption():
    world, task, feeds = _w2()
    rec = runner.run(
        world, task, LLMAgent(_scripted_llm([]), Seed(1), memory="full"), {"levers": feeds}, Seed(5),
        max_turns=2, sim_cfg=W2_SIM,
    )
    assert rec.taint_exempt == {} and "taint_exempt" not in record_to_json(rec, "c", 0)


# ── E1 — aggregate and report need the yaml only for its helpers ─────────────


def test_a_finished_run_without_helpers_aggregates_after_its_yaml_is_edited_or_deleted(tmp_path):
    source = (REPO_ROOT / "catalog/experiments/exp04-zero.yaml").read_text()
    spec_file = tmp_path / "z.yaml"
    spec_file.write_text(source)
    out = tmp_path / "run"
    run_experiment(load_spec(spec_file), out_dir=str(out))
    spec_file.write_text("this: [is not, an experiment")
    assert aggregate(out).records
    spec_file.unlink()
    assert aggregate(out).records
    from alienbio.suite.experiment import spec_from_manifest
    from alienbio.suite.store import read_manifest

    with pytest.raises(FileNotFoundError, match="z.yaml"):
        spec_from_manifest(read_manifest(out / "manifest.json"), current=True)


# ── G1 — numpy levels resume; two NaN levels are one ──────────────────────────


def _pressure_spec(levels):
    return ExperimentSpec(
        name="g", axes=(("pi", tuple(levels)),), drafter="pressure", agent="idle", trials_per_condition=1,
        base_seed=1, fixed_dials={"max_turns": 2, "sim_steps": 5, "levers": []},
    )


def test_a_numpy_linspace_axis_resumes(tmp_path):
    spec = _pressure_spec(list(np.linspace(0, 1, 3)))
    out = tmp_path / "run"
    run_experiment(spec, out_dir=str(out))
    lines = (out / "records.jsonl").read_text()
    run_experiment(spec, out_dir=str(out), resume=True)  # no drift refusal
    assert (out / "records.jsonl").read_text() == lines


def test_two_nan_levels_refuse():
    with pytest.raises(ValueError, match="repeats level nan"):
        _pressure_spec([float("nan"), float("nan")])


# ── F1 — the held-mass refusal does not depend on the trial seed ──────────────


def test_the_held_mass_bound_under_partial_observability_refuses_at_draft(tmp_path):
    spec = ExperimentSpec(
        name="f1", axes=(("n_nodes", (4,)),), drafter="intervene", agent="idle", trials_per_condition=8,
        base_seed=1, fixed_dials={"target_margin": 0.2, "observability": 0.3},
    )
    verdict = dict(preflight(spec).checks)["draft"] or ""
    assert "observability 0.3" in verdict and "`levers`" in verdict
    out = tmp_path / "run"
    with pytest.raises(ValueError, match="observability 0.3"):
        run_experiment(spec, out_dir=str(out))
    assert not (out / "records.jsonl").exists()  # refused before any trial ran
    world, task = DRAFTERS["intervene"](Seed(0), {"n_nodes": 4, "target_margin": 0.2})
    for s in range(8):
        with pytest.raises(ValueError, match="observability 0.3"):
            runner.trial_preamble(
                world, task, {"observability": 0.3}, Seed(s), sim_cfg=runner.SimConfig(), max_turns=8,
                assay_kill=0.5,
            )


def test_a_declared_molecule_lever_lifts_the_partial_observability_refusal():
    world, task = DRAFTERS["intervene"](Seed(0), {"n_nodes": 4, "target_margin": 0.2})
    molecule = next(m for m in sorted(world.chemistry.molecules) if m != task.setup["oracle"]["intervene"]["target"])
    for s in range(4):
        runner.trial_preamble(
            world, task, {"observability": 0.3, "levers": [molecule]}, Seed(s), sim_cfg=runner.SimConfig(),
            max_turns=8, assay_kill=0.5,
        )


# ── F6 — the length modifiers are charged like %a ─────────────────────────────


@pytest.mark.parametrize("fmt", ["'%(k)la'", "'%(k)ha%(k)ha%(k)ha'", "'%(k)La'", "'%(k)lr'"])
def test_a_repr_conversion_with_a_length_modifier_is_charged(fmt):
    from alienbio.expr import Env, ExprError, evaluate
    from alienbio.expr.parse import parse

    with pytest.raises(ExprError, match="limits.entities"):
        evaluate(parse(fmt + " % {'k': '\\U000e0000'*200000}"), Env.standard(seed=1))


# ── D7 — opaque_names=False refuses only where names are opaque by default ────


def test_opaque_names_false_refuses_only_on_an_opaque_by_default_drafter():
    base = dict(name="d7", axes=(("n_nodes", (4,)),), trials_per_condition=1, base_seed=1, temperature=0.0)
    for off in (False, 0):
        plain = ExperimentSpec(**base, drafter="diagnose", agent="llm", fixed_dials={"opaque_names": off})
        assert dict(preflight(plain).checks)["no-peeking"] is None
    p1 = ExperimentSpec(
        name="d7", axes=(("variant", ("commitment_no_coupling",)),), trials_per_condition=1, base_seed=1,
        temperature=0.0, drafter="phase1_pressure", agent="llm", fixed_dials={"opaque_names": False},
    )
    verdict = dict(preflight(p1).checks)["no-peeking"] or ""
    assert "opaque_names=False" in verdict and "phase1_pressure" in verdict


def test_the_opaque_setup_drafters_set_opaque_names_and_diagnose_does_not():
    for name in sorted(OPAQUE_SETUP_DRAFTERS):
        assert name not in guarded_drafters()
        _world, task = DRAFTERS[name](Seed(1), {"variant": "commitment_no_coupling"})
        assert task.setup.get("opaque_names") is True, name
    _world, task = DRAFTERS["diagnose"](Seed(1), {})
    assert not task.setup.get("opaque_names")
