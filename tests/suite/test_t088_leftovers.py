"""T088 leftovers round — the module-doc findings the eight fix rounds left.

1. ``manifest.json`` wrote bare ``Infinity``/``NaN`` for a spec carrying a
   non-finite float; the reader now decodes the strict spelling back.
2. The failure census's abort counts read the abort step's prose for a tag
   it never carried, so they were always empty; ``parse_failures`` and
   ``aborted`` never reached the record.
3. A probe's context had no ``compartments`` (the observation the act saw).
4. The Expr ``llm`` head built its own agent and ignored the trial dials.
5. A death's release was placed against the frozen sizes, so a release
   compartment emptied by this step's own deaths dropped it; a flux blocked by
   a dead receiver stopped silently.
7. A reload after a resume aggregated in file order, not run order.
8. An ``on_trial`` failure at ``concurrency > 1`` left in-flight records
   unlanded.
9. ``trials_per_condition``, ``base_seed``, ``memory``, ``token_ceiling`` and
   the forgetting fields were never validated on the spec.
10. ``bio report`` regexed the spend out of ``report.txt``.
11. ``alienbio.suite`` imported names it never declared in ``__all__``.
"""

from __future__ import annotations

import ast
import dataclasses
import json
import logging
import threading
from pathlib import Path

import pytest

from alienbio.suite.dist import Seed
from alienbio.suite.experiment import ExperimentSpec, aggregate, record_from_json, record_to_json, run_experiment
from alienbio.suite.spec import spec_from_dict, spec_to_dict


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


def _strict_loads(text: str):
    def refuse(token: str):
        raise ValueError(f"non-strict JSON token {token!r}")

    return json.loads(text, parse_constant=refuse)


# ── 1. the manifest is strict JSON ──────────────────────────────────────────


def test_a_spec_carrying_inf_writes_a_strict_manifest_that_reads_back_equal(tmp_path):
    from alienbio.suite.store import _build_manifest, _write_manifest, read_manifest

    spec = _spec("inf", fixed_dials={"levers": [], "budget": float("inf")}, cost_ceiling_usd=float("inf"))
    path = tmp_path / "manifest.json"
    _write_manifest(path, _build_manifest(spec, 2, "2026-10-28T00:00:00Z"))
    raw = _strict_loads(path.read_text())
    assert raw["spec"]["fixed_dials"]["budget"] == "inf"
    manifest = read_manifest(path)
    assert manifest["spec"]["fixed_dials"]["budget"] == float("inf")
    assert spec_from_dict(manifest["spec"]) == spec


def test_a_finite_manifest_is_byte_identical_to_the_old_writer(tmp_path):
    from alienbio.suite.store import _build_manifest, _write_manifest

    manifest = _build_manifest(_spec("finite"), 2, "2026-10-28T00:00:00Z")
    path = tmp_path / "manifest.json"
    _write_manifest(path, manifest)
    assert path.read_text() == json.dumps(manifest, indent=2)


def test_a_run_and_its_resume_round_trip_a_spec_carrying_inf(tmp_path):
    spec = _spec("inf-run", fixed_dials={"levers": [], "budget": float("inf")})
    out = tmp_path / "run"
    run_experiment(spec, out_dir=str(out))
    _strict_loads((out / "manifest.json").read_text())
    # the drift check reads the decoded spec, so the resume is not refused
    run_experiment(spec, out_dir=str(out), resume=True)
    assert len(aggregate(out).records) == 2


# ── 2. aborts and parse failures reach the record and the census ───────────


def _phase1():
    from alienbio.suite.experiment import DRAFTERS

    levers = ["root/uptake_route_in", "root/uptake_neutral_in"]
    world, task = DRAFTERS["phase1_pressure"](Seed(41).child("draft"), {"levers": levers, "variant": "coupling_withheld"})
    return world, task, {"levers": levers}


def test_parse_exhaustion_lands_on_the_record_and_in_the_census(tmp_path):
    from alienbio.suite.llm_agent import LLMAgent
    from alienbio.suite.runner import run

    world, task, dials = _phase1()
    agent = LLMAgent(lambda directive, context, seed: "not an action", Seed(1), max_retries=2)
    record = run(world, task, agent, dials, Seed(2), max_turns=3)
    assert record.aborted == "parse_exhausted"
    assert record.parse_failures >= 2
    back = record_from_json(json.loads(json.dumps(record_to_json(record, "c", 0))))
    assert (back.aborted, back.parse_failures) == (record.aborted, record.parse_failures)

    from alienbio.suite.mass_trial import aggregate_records
    from alienbio.suite.report_text import render_report

    rmap = aggregate_records([record], (), Seed(0), 1)
    assert "aborted='parse_exhausted': 1" in render_report(rmap, {})


def test_the_token_ceiling_abort_names_itself():
    from alienbio.suite.llm_agent import LLMAgent
    from alienbio.suite.runner import run

    world, task, dials = _phase1()
    agent = LLMAgent(lambda d, c, s: {"action": "wait", "duration": 1.0, "reasoning": []}, Seed(1), token_ceiling=10)
    record = run(world, task, agent, dials, Seed(2), max_turns=3)
    assert record.aborted == "token_ceiling"


def test_a_scripted_record_writes_neither_field():
    from alienbio.suite.trial import TrialRecord

    fields = {f.name for f in dataclasses.fields(TrialRecord)}
    assert {"parse_failures", "aborted"} <= fields
    line = record_to_json(TrialRecord(task_id="t", condition_key=(), final_timeline=_timeline(), deliberation_trace=_trace(), action_log=(), objective_score=0.0), "c", 0)
    assert "parse_failures" not in line and "aborted" not in line


def _timeline():
    from alienbio.suite.types import Timeline

    return Timeline(times=(), states=())


def _trace():
    from alienbio.suite.deliberation import DeliberationTrace

    return DeliberationTrace()


# ── 3. a probe sees the observation the act sees ────────────────────────────


def test_an_every_turn_probe_carries_the_acts_observation():
    from alienbio.suite.llm_agent import LLMAgent
    from alienbio.suite.runner import run

    world, task, dials = _phase1()
    dials = {**dials, "probes": [{"text": "What do you see?", "timing": "every_turn"}]}
    contexts: list[dict] = []

    def llm_fn(directive, context, seed):
        contexts.append(context)
        if "probe" in context:
            return "an answer"
        return {"type": "wait", "duration": 1.0, "reasoning": "waiting"}

    run(world, task, LLMAgent(llm_fn, Seed(1), memory="full"), dials, Seed(2), max_turns=2)
    probes = [c for c in contexts if "probe" in c]
    acts = [c for c in contexts if "probe" not in c]
    assert probes and len(probes) == len(acts)
    for probe, act in zip(probes, acts):
        assert probe["compartments"] == act["compartments"]
        assert {k: v for k, v in probe.items() if k != "probe"} == act


# ── 4. the Expr llm head and the AGENTS entry build through one factory ────


def test_the_expr_llm_head_honours_the_trial_dials(monkeypatch):
    import alienbio.suite.llm_agent as llm_mod
    from alienbio.suite.expr_experiment import llm

    monkeypatch.setattr(llm_mod, "default_anthropic_llm_fn", lambda model, **kw: (lambda d, c, s: None))
    agent = llm(model="claude-sonnet-5")(Seed(1), {"memory": 3, "compact_at": 2, "max_tokens": 64})
    assert (agent.memory, agent.compact_at, agent.max_tokens) == (3, 2, 64)


# ── 5. population release placement, and a blocked flux is logged ─────────


def _pop_state(n_comp: int, n_mol: int):
    from alienbio.bio.compartment_tree import CompartmentTreeImpl
    from alienbio.bio.world_state import WorldStateImpl

    tree = CompartmentTreeImpl()
    ids = [tree.add_root("c0")]
    for i in range(1, n_comp):
        ids.append(tree.add_child(ids[0], f"c{i}"))
    state = WorldStateImpl(
        tree=tree, num_molecules=n_mol,
        compartment_ids=[f"c{i}" for i in range(n_comp)],
        molecule_ids=[f"m{j}" for j in range(n_mol)],
    )
    return tree, state


def _pop_step(tree, state, laws, n_mol, dt):
    from alienbio.bio.world_simulator import WorldSimulatorImpl

    return WorldSimulatorImpl(tree=tree, reactions=[], flows=[], num_molecules=n_mol, dt=dt, population_laws=laws).step(state)


def test_a_release_into_a_compartment_its_own_deaths_empty_stays_in_the_dying_one():
    from alienbio.bio.population import PerCapitaDeath

    tree, state = _pop_state(2, 2)
    state.set_multiplicity(0, 10.0)
    state.set(0, 0, 1.0)
    state.set_multiplicity(1, 1.0)  # alive at the start, dies out this step
    laws = [
        PerCapitaDeath(compartment=1, rate_constant=5.0),
        PerCapitaDeath(compartment=0, rate_constant=0.1, release_compartment=1, release_resource=1, release_stoich=1.0),
    ]
    out = _pop_step(tree, state, laws, 2, 1.0)
    assert out.get_multiplicity(1) == 0.0
    assert out.amount(0, 1) == pytest.approx(1.0)  # placed against the post-pass size


def test_same_pass_gains_do_not_fund_same_pass_draws():
    """Documented: a growth draw is rationed against the pool before the
    pass; a death's release this step does not raise that ceiling."""
    from alienbio.bio.population import PerCapitaDeath, PerCapitaGrowth

    tree, state = _pop_state(2, 1)
    state.set_multiplicity(0, 1.0)
    state.set_multiplicity(1, 10.0)
    state.set(0, 0, 0.0)  # the resource pool starts empty
    grow = PerCapitaGrowth(compartment=0, resource_compartment=0, resource=0, stoich=1.0, rate_constant=1.0)
    die = PerCapitaDeath(compartment=1, rate_constant=0.1, release_compartment=0, release_resource=0, release_stoich=1.0)
    out = _pop_step(tree, state, [grow, die], 1, 1.0)
    assert out.get_multiplicity(0) == pytest.approx(1.0)  # no growth from the release
    assert out.amount(0, 0) == pytest.approx(1.0)  # the release landed


def test_a_flux_blocked_by_a_dead_receiver_logs_once(caplog):
    from alienbio.bio.flow import TransportFlux

    tree, state = _pop_state(2, 1)
    state.set(0, 0, 4.0)
    state.set_multiplicity(1, 0.0)
    flux = TransportFlux(origin=0, dest=1, stoichiometry={0: 1.0}, driver_molecule=0, rate_constant=0.5, rate_law="first_order", name="leak")
    with caplog.at_level(logging.WARNING, logger="alienbio.bio.flow"):
        for _ in range(3):
            assert flux.demand(state, tree)[0] == 0.0
    assert len([r for r in caplog.records if "leak" in r.getMessage()]) == 1


# ── 7. a reload after a resume aggregates in run order ─────────────────────


def test_a_reload_sorts_records_back_to_run_order(tmp_path):
    spec = _spec("order", trials_per_condition=2)
    out = tmp_path / "run"
    live = run_experiment(spec, out_dir=str(out))
    lines = (out / "records.jsonl").read_text().strip().splitlines()
    (out / "records.jsonl").write_text("\n".join(reversed(lines)) + "\n")  # a resume's appended shape
    reloaded = aggregate(out)
    assert [r.task_id for r in reloaded.records] == [r.task_id for r in live.records]
    assert [r.condition_key for r in reloaded.records] == [r.condition_key for r in live.records]


# ── 8. on_trial failure under concurrency lands every in-flight record ─────


def test_an_on_trial_failure_at_concurrency_two_lands_the_in_flight_records():
    from alienbio.suite.agents import AGENTS
    from alienbio.suite.experiment import DRAFTERS
    from alienbio.suite.mass_trial import MassTrialRunner

    drafted = []
    lock = threading.Lock()

    def drafter(seed, dials):
        with lock:
            drafted.append(dials["rung"])
        return DRAFTERS["conflict"](seed, dials)

    landed = []

    def on_trial(label, i, record):
        landed.append((label, i))
        if len(landed) == 1:
            raise OSError("disk full")

    with pytest.raises(OSError, match="disk full"):
        MassTrialRunner().run(
            (("rung", ("single", "forced", "compatible", "latent")),), drafter, AGENTS["idle"](None),
            3, Seed(7), extra_dials={"levers": []}, on_trial=on_trial, concurrency=2,
        )
    assert len(landed) == len(drafted) > 1


# ── 9. spec field validation ────────────────────────────────────────────────


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"trials_per_condition": 0}, "trials_per_condition must be a positive int"),
        ({"trials_per_condition": True}, "trials_per_condition must be a positive int"),
        ({"base_seed": 1.5}, "base_seed must be an int"),
        ({"memory": "bogus"}, "invalid memory"),
        ({"memory": -1}, "memory int must be >= 0"),
        ({"token_ceiling": 0}, "token_ceiling must be a positive int"),
        ({"compact_at": 0}, "compact_at must be a positive int"),
        ({"compact_budget": -1}, "compact_budget must be a positive int"),
        ({"history_token_limit": 0}, "history_token_limit must be a positive int"),
    ],
)
def test_bad_spec_fields_refuse_at_construction_in_both_forms(overrides, message):
    with pytest.raises(ValueError, match=message):
        _spec("bad", **overrides)
    good = spec_to_dict(_spec("bad"))
    with pytest.raises(ValueError, match=message):
        spec_from_dict({**good, **overrides})


# ── 10. bio report reads the spend off the manifest ─────────────────────────


def test_run_rows_reads_the_spend_from_the_manifest(tmp_path, monkeypatch):
    import alienbio.report as report_mod

    runs = tmp_path / "runs"
    out = runs / "r"
    run_experiment(_spec("spend"), out_dir=str(out))
    manifest = json.loads((out / "manifest.json").read_text())
    manifest["cost_usd_spent"] = 0.25
    (out / "manifest.json").write_text(json.dumps(manifest))
    (out / "report.txt").write_text("no spend line here\n")
    monkeypatch.setattr(report_mod, "RUNS", runs)
    (row,) = report_mod.run_rows()
    assert row.spend_usd == pytest.approx(0.25)


# ── 11. the package declares every name it imports ──────────────────────────


def test_suite_all_declares_every_public_import():
    import alienbio.suite as suite

    tree = ast.parse(Path(suite.__file__).read_text())
    imported = {
        alias.asname or alias.name
        for node in tree.body
        if isinstance(node, ast.ImportFrom) and node.module != "__future__"
        for alias in node.names
    }
    public = {name for name in imported if not name.startswith("_")}
    assert public <= set(suite.__all__)
    assert len(suite.__all__) == len(set(suite.__all__))
