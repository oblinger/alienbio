"""T088 analysis round: the generators, the analysis families, Expr interp/env.

Each test pins one finding from the module-doc pass (numbered as in the T088
findings doc, e.g. ``conflict_gen 1``): it failed before its fix and passes
after.
"""

from __future__ import annotations

import json
import math
from types import SimpleNamespace

import pytest

from alienbio.expr import Env, ExprError, X, evaluate, fn, guard
from alienbio.expr.env import Limits
from alienbio.suite.agent import ScriptedAgent, Wait
from alienbio.suite.blocks import (
    PoissonSchedule,
    ReactionBlock,
    SignalingBlock,
    SinkBlock,
    SourceBlock,
    SpatialLatticeBlock,
    TransportBlock,
)
from alienbio.suite.brief import task_readouts
from alienbio.suite.caution import trial_caution
from alienbio.suite.census import census_summary
from alienbio.suite.degradation import trial_degradation
from alienbio.suite.dist import Constant, Seed
from alienbio.suite.dose import DoseCell, dose_profile
from alienbio.suite.experiment import DRAFTERS
from alienbio.suite.faking import _abstained
from alienbio.suite.hazard import HAZARD_MOLECULE, _read, hazard_oracle
from alienbio.suite.arch_diagnose import draft_diagnosis_world
from alienbio.suite.plots import write_key_figure
from alienbio.suite.runner import run
from alienbio.suite.skeleton import PoolBinding, Port, PortDir, Role, Skeleton, SkeletonBlock, SkeletonError
from alienbio.suite.tradeoff import ConflictCell, frontier_distance, precedence_ladder
from alienbio.suite.verify import SimConfig, simulate


def _wait_agent():
    return ScriptedAgent(lambda obs, sd: (Wait(duration=1.0), ()), Seed(0))


# conflict_gen 1 --------------------------------------------------------------


@pytest.mark.parametrize("rung", ["compatible", "latent", "forced"])
def test_both_conflict_targets_are_readouts_and_off_the_default_surface(rung):
    world, task = DRAFTERS["conflict"](Seed(7).child("draft"), {"rung": rung})
    targets = {"root/crux/sink_a_in", "root/crux/sink_b_in"}
    assert targets <= task_readouts(task, world.chemistry)
    # The conflict world declares its surface (require_levers): a declared
    # lever on either target writes the measurement and is refused — it was
    # accepted on these three rungs, whose target is an (id, goal) pair.
    for target in sorted(targets):
        with pytest.raises(ValueError, match="readout"):
            run(world, task, _wait_agent(), {"rung": rung, "levers": [target]}, Seed(1), max_turns=1)


# delta_gen 2 -----------------------------------------------------------------


def test_the_delta_question_lists_its_candidates_in_a_fixed_order():
    for arm in ("match", "mismatch"):
        _world, task = DRAFTERS["delta"](Seed(8).child("draft"), {"arm": arm})
        q = task.question.structured
        assert isinstance(q, tuple) and list(q) == sorted(q) == task.setup["oracle"]["delta"]["candidates"]


# caution 1, faking 3 -----------------------------------------------------------


def _committed(answer, aborted=None, score=0.0):
    return SimpleNamespace(
        action_log=[SimpleNamespace(kind="commit", accepted=True, destructive=False, target=None)],
        answer=answer,
        aborted=aborted,
        objective_score=score,
        terminal_reason="committed",
    )


def test_an_aborted_commit_is_neither_an_abstention_nor_a_false_positive():
    _i, _d, committed, abstained, false_pos = trial_caution(_committed({"value": None}, aborted="token_ceiling"))  # type: ignore[arg-type]
    assert not committed and not abstained and not false_pos  # T091 Y4: an abort is not a commit
    assert trial_caution(_committed({"value": None}))[3]  # type: ignore[arg-type]  # a real empty answer still abstains
    assert not _abstained(_committed({"value": None}, aborted="parse_exhausted"))  # type: ignore[arg-type]
    assert _abstained(_committed({"value": None}))  # type: ignore[arg-type]


# degradation 1, 2 --------------------------------------------------------------


def _act(kind, target):
    return SimpleNamespace(kind=kind, target=target, accepted=True)


def _deg_record(actions, said=""):
    return SimpleNamespace(
        action_log=actions,
        answer={"value": "x"},
        oracle={},
        aborted=None,
        terminal_reason="committed",
        deliberation_trace=SimpleNamespace(steps=[SimpleNamespace(content=said)]),
    )


def test_measure_then_verify_is_not_scope_narrowing():
    careful = _deg_record([_act("measure", "a"), _act("measure", "b"), _act("intervene", "x"), _act("intervene", "y"), _act("commit", None)])
    d = trial_degradation(careful)  # type: ignore[arg-type]
    assert not d.scope_narrowing and not d.skipped_verification
    narrowing = _deg_record([_act("measure", "a"), _act("measure", "b"), _act("measure", "a"), _act("measure", "a"), _act("commit", None)])
    assert trial_degradation(narrowing).scope_narrowing  # type: ignore[arg-type]


def test_remaining_alone_is_not_budget_awareness():
    def aware(text):
        return trial_degradation(_deg_record([_act("commit", None)], text)).budget_aware  # type: ignore[arg-type]

    assert not aware("The remaining candidate is s2.")
    assert aware("Only three turns remaining, so commit now.") and aware("I am running out of budget.")


# tradeoff 1, 3 -----------------------------------------------------------------


def test_frontier_distance_is_to_the_line_not_the_nearest_sample():
    frontier = [(80.0 * i / 10, 80.0 * (10 - i) / 10) for i in range(11)]
    assert frontier_distance((36.0, 44.0), frontier) == pytest.approx(0.0, abs=1e-12)  # was 5.66
    assert frontier_distance((30.0, 30.0), frontier) == pytest.approx(20.0 / math.sqrt(2))
    assert frontier_distance((0.0, 90.0), frontier) == pytest.approx(10.0)  # beyond the end: to (0, 80)


def test_a_tied_rung_carries_no_precedence():
    def cell(rung, a, b):
        return ConflictCell(n=1, rung=rung, mean_scores={"A": a, "B": b}, dominant=None, dominant_fraction=0.0, precedence_fraction=None, mean_pareto_distance=None)

    # compatible ties; latent puts B first, forced A first: one comparison, inconsistent.
    summary = {(("rung", r),): cell(r, a, b) for r, a, b in (("compatible", 1.0, 1.0), ("latent", 0.4, 0.9), ("forced", 0.9, 0.4))}
    assert precedence_ladder(summary)[()][1] == 0.0
    # two ties and one ranked rung: nothing to compare, vacuously consistent.
    summary = {(("rung", r),): cell(r, a, b) for r, a, b in (("compatible", 1.0, 1.0), ("latent", 0.5, 0.5), ("forced", 0.9, 0.4))}
    assert precedence_ladder(summary)[()][1] == 1.0


# hazard 1 ------------------------------------------------------------------------


@pytest.mark.parametrize("dt,steps", [(0.1, 1), (0.02, 3), (0.01, 1), (0.1, 5), (0.05, 10)])
def test_threshold_turn_is_the_turn_whose_end_first_reaches_the_threshold(dt, steps):
    # (0.1, 5) and (0.05, 10) are the catalog's settings; the first three
    # put the float end-of-turn time a hair above an integer multiple of the
    # turn span, where ceil(t / span) - 1 read one turn late.
    world, _ = draft_diagnosis_world(Seed(1), n_nodes=4, distractor_count=3, hazard=True)
    cfg = SimConfig(dt=dt, steps=steps, sample_every=steps)
    turns = 12
    timeline = simulate(world, SimConfig(dt=dt, steps=steps * turns, sample_every=steps))
    values = [_read(s, HAZARD_MOLECULE) for s in timeline.states]
    for turn in (2, 6, 8):
        threshold = values[turn + 1]  # the end of turn ``turn``
        if threshold <= 0.0 or values[turn] >= threshold:
            continue
        assert hazard_oracle(world, HAZARD_MOLECULE, threshold, turns, cfg).threshold_turn == turn


# blocks 1-5 -------------------------------------------------------------------


def test_a_chain_of_transport_blocks_materializes():
    root = SkeletonBlock(
        name="root",
        role=Role.CRUX,
        children=(
            SourceBlock.make("src", container="A", rate=Constant(1.0)),
            TransportBlock.make("ab", container="A", dest_container="B"),
            TransportBlock.make("bc", container="B", dest_container="C"),
        ),
        pool_bindings=(PoolBinding("ab.pool", "src.out"), PoolBinding("bc.pool", "ab.pool")),
    )
    world = Skeleton(root=root).materialize(Seed(1))
    parents = {c.id: c.parent for c in world.compartments}
    assert parents["A"] is None and parents["B"] == "A" and parents["C"] == "B"
    assert len(world.flows) == 2


def test_two_ports_on_one_pool_sum_their_coefficients():
    block = ReactionBlock(
        name="dimer",
        role=Role.CRUX,
        ports=(Port("x", None, PortDir.IN), Port("y", None, PortDir.IN), Port("out", None, PortDir.OUT)),
        stoich={"x": 1.0, "y": 2.0},
    )
    root = SkeletonBlock(
        name="root",
        role=Role.CRUX,
        children=(SourceBlock.make("src", rate=Constant(1.0)), block, SinkBlock.make("sink", rate=Constant(1.0))),
        pool_bindings=(PoolBinding("dimer.x", "src.out"), PoolBinding("dimer.y", "src.out"), PoolBinding("sink.in", "dimer.out")),
    )
    world = Skeleton(root=root).materialize(Seed(1))
    rxn = next(r for rid, r in world.chemistry.reactions.items() if "dimer" in rid)
    assert list(rxn.reactants.values()) == [3.0]
    stray = ReactionBlock(name="r", role=Role.CRUX, ports=(Port("in", None, PortDir.IN),), stoich={"inn": 2.0})
    with pytest.raises(SkeletonError, match="names no port"):
        Skeleton(root=SkeletonBlock(name="root", role=Role.CRUX, children=(SourceBlock.make("s"), stray), pool_bindings=(PoolBinding("r.in", "s.out"),))).materialize(Seed(1))


def test_lattice_poisson_and_signaling_refuse_bad_direct_construction():
    with pytest.raises(SkeletonError, match="0..2"):
        SpatialLatticeBlock(name="lat", role=Role.TRANSPORT, k=3, initial={-1: 5.0})
    with pytest.raises(SkeletonError, match="0..2"):
        SpatialLatticeBlock(name="lat", role=Role.TRANSPORT, k=3, initial={3: 5.0})
    with pytest.raises(SkeletonError, match="k >= 2"):
        SpatialLatticeBlock(name="lat", role=Role.TRANSPORT, k=1)
    with pytest.raises(SkeletonError, match="lam"):
        PoissonSchedule(lam=0.0, horizon=10.0)
    good = SignalingBlock.make("sig")
    bad = SignalingBlock(name="sig", role=good.role, ports=good.ports, rate=good.rate, kind="activatr", a=good.a, Ki=good.Ki, modifier_port=good.modifier_port)
    with pytest.raises(SkeletonError, match="kind"):
        bad.realize(Seed(1), "sig", {p.name: object() for p in good.ports})  # type: ignore[arg-type]


# dose 1 -------------------------------------------------------------------------


def _dose(pis_and_side):
    return [DoseCell(pi=p, n=1, mean_t=0.0, mean_byproduct=b, mean_score=0.0, passive_t=0.0, passive_byproduct=0.0, v_target=1.0) for p, b in pis_and_side]


def test_continuity_is_not_determinable_on_a_two_level_ladder():
    assert dose_profile(_dose([(0.0, 0.0), (1.0, 1.0)])).continuous is None
    assert dose_profile(_dose([(0.5, 0.0), (1.0, 1.0)])).continuous is None
    assert dose_profile(_dose([(0.0, 0.0), (0.2, 0.1), (1.0, 1.0)])).continuous is True
    assert dose_profile(_dose([(0.0, 0.0), (0.2, 0.9), (1.0, 1.0)])).continuous is False


# census 1 ------------------------------------------------------------------------


def test_a_trial_offered_no_lever_is_not_disengaged():
    def rec(levers, intervenes):
        return SimpleNamespace(
            is_error=False,
            bucket_key=(("arm", "x"),),
            action_log=[SimpleNamespace(kind="intervene", accepted=True)] * intervenes,
            turns=1,
            deliberation_trace=SimpleNamespace(steps=[]),
            illegal_actions=0,
            brief=SimpleNamespace(affordances=SimpleNamespace(levers=levers)),
        )

    cell = census_summary([rec((), 0), rec((), 0)])[(("arm", "x"),)]  # type: ignore[list-item]
    assert math.isnan(cell.disengaged_rate)
    cell = census_summary([rec(("L",), 0), rec(("L",), 2), rec((), 0)])[(("arm", "x"),)]  # type: ignore[list-item]
    assert cell.disengaged_rate == 0.5


# plots 2 ---------------------------------------------------------------------------


def test_a_declared_readout_with_nothing_to_draw_does_not_raise_after_the_run(tmp_path):
    rmap = SimpleNamespace(records=[], cells={})
    assert write_key_figure(rmap, tmp_path, readout="dose") is None  # type: ignore[arg-type]
    assert json.loads((tmp_path / "key.json").read_text())["readout"] == "dose"
    with pytest.raises(ValueError, match="unknown readout"):
        write_key_figure(rmap, tmp_path, readout="pie")  # type: ignore[arg-type]


# expr/interp 1-3 ---------------------------------------------------------------------

_ATTEMPTS: list[int] = []


@fn(name="t088_pool", summary="test: the scope's spelling of pool P")
def _t088_pool(*, env):
    return env.pool("P")


@guard(name="t088_second_try", summary="test: fails the first call, passes the next")
def _t088_second_try(value, ctx):
    del value, ctx
    _ATTEMPTS.append(1)
    return len(_ATTEMPTS) % 2 == 0


def test_a_retried_template_keeps_its_instance_name():
    _ATTEMPTS.clear()
    doc = """
mk: !template
  body: !x t088_pool()
cell: !mk {guards: [t088_second_try], on_fail: retry}
other: !mk {guards: [t088_second_try], on_fail: retry}
"""
    vals = Env.standard(seed=1).load("doc.yaml", text=doc).force_all()
    assert vals["cell"] == "cell.P" and vals["other"] == "other.P"  # was retry1.P, then a collision


def test_a_keyword_cannot_rebind_a_positional():
    env = Env.standard(seed=1).load("doc.yaml", text="t: !template\n  positional: [a]\n  body: !x a\n")
    assert evaluate(X.t(1), env) == 1
    with pytest.raises(ExprError, match="bound twice"):
        evaluate(X.t(1, a=2), env)


def test_a_callables_overflow_carries_the_node_path():
    with pytest.raises(ExprError, match="OverflowError"):
        evaluate(X.parse("exp(1000)"), Env.standard(seed=1))


# expr/env 1-3 -------------------------------------------------------------------------


def test_a_failed_lazy_binding_re_raises_its_own_error():
    env = Env.standard(seed=1).load("doc.yaml", text="a: !x exp(1000)\nb: 2\n")
    for _ in range(2):
        with pytest.raises(ExprError) as info:
            env.lookup("a")
        assert "cyclic" not in str(info.value)


def test_a_dotted_head_name_does_not_call_its_first_segment():
    env = Env.standard(seed=1).load("doc.yaml", text="t: !template\n  body: 1\n")
    assert evaluate(X.t(), env) == 1
    with pytest.raises(ExprError, match="unknown head"):
        evaluate(X.call("t.anything"), env)


def test_one_limits_object_meters_each_env_separately():
    limits = Limits(entities=1000)
    for _ in range(3):
        evaluate(X.parse("range(400)"), Env.standard(seed=1, limits=limits))
