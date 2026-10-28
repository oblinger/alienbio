"""Acceptance tests for the M31.1 conflict-ladder generator (F022).

Exercises ``draft_conflict_world`` across all four rungs — materialize +
validate clean on the conserving engine, the rung's qualitative tradeoff shape
(single/compatible/latent/forced), seed-determinism, and one full
``ScenarioRunner`` (F021) trial with a ``ScriptedAgent`` (no LLM).
"""

from __future__ import annotations

import pytest

from alienbio.suite.agent import Commit, Measure, ScriptedAgent
from alienbio.suite.conflict_gen import (
    DEFAULT_TARGET,
    RUNGS,
    _S_MULTIPLIER,
    _assert_forced_gate,
    build_conflict_skeleton,
    closed_form_frontier,
    draft_conflict_world,
)
from alienbio.suite.dist import Constant, Seed
from alienbio.suite.runner import run
from alienbio.suite.skeleton import SkeletonError
from alienbio.suite.trial import TrialRecord
from alienbio.suite.types import (
    Answer,
    CarveResult,
    Motif,
    OutcomeObjective,
    Question,
    TaskInstance,
)
from alienbio.suite.verify import SimConfig, simulate


# ═══════════════════════════════════════════════════════════════════════════
# Every rung materializes + validates clean on the conserving engine
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("rung", RUNGS)
def test_every_rung_materializes_and_validates_clean(rung: str) -> None:
    world, skeleton, objective = draft_conflict_world(Seed(1), rung=rung)
    assert skeleton.chemistry is not None
    assert skeleton.validate() is None
    assert isinstance(objective, OutcomeObjective)
    assert len(world.chemistry.reactions) > 0


# ═══════════════════════════════════════════════════════════════════════════
# single — one live objective, no tradeoff
# ═══════════════════════════════════════════════════════════════════════════


def test_single_rung_has_one_live_objective() -> None:
    world, skeleton, objective = draft_conflict_world(Seed(2), rung="single")
    del world

    point = skeleton.oracle(Seed(2), SimConfig(dt=0.05, steps=400, sample_every=50))
    assert isinstance(point, tuple)
    assert len(point) == 1  # ONE target, not a (V1, V2) pair
    (v1_final,) = point
    assert v1_final >= DEFAULT_TARGET * 0.95  # comfortably clears its own goal

    assert isinstance(objective.target, tuple)
    assert len(objective.target) == 2  # (mol_id, target_value) — a single component


# ═══════════════════════════════════════════════════════════════════════════
# compatible — both targets clear comfortably at the default balanced split
# ═══════════════════════════════════════════════════════════════════════════


def test_compatible_rung_lets_both_targets_be_raised() -> None:
    world, skeleton, objective = draft_conflict_world(Seed(3), rung="compatible")
    del world

    prod_a, prod_b = skeleton.oracle(
        Seed(3), SimConfig(dt=0.05, steps=400, sample_every=50)
    )
    assert prod_a >= DEFAULT_TARGET * 0.95
    assert prod_b >= DEFAULT_TARGET * 0.95


# ═══════════════════════════════════════════════════════════════════════════
# latent — the default (balanced) split looks conflict-free; an asymmetric
# reallocation exposes the hidden tradeoff
# ═══════════════════════════════════════════════════════════════════════════


def test_latent_rung_sits_between_compatible_and_forced() -> None:
    assert _S_MULTIPLIER["compatible"] > _S_MULTIPLIER["latent"] > _S_MULTIPLIER["forced"]

    world, skeleton, objective = draft_conflict_world(Seed(4), rung="latent")
    del world
    sim_cfg = SimConfig(dt=0.05, steps=400, sample_every=50)

    # The naive/default balanced split (kA == kB) hits both targets right at
    # the boundary — looks conflict-free.
    prod_a, prod_b = skeleton.oracle(Seed(4), sim_cfg)
    assert prod_a >= DEFAULT_TARGET * 0.95
    assert prod_b >= DEFAULT_TARGET * 0.95

    # But the tension is only hidden, not absent: skewing the split toward
    # route A starves route B below its target — the same source_rate, same
    # crux, only the (kA, kB) allocation differs.
    source_rate = _S_MULTIPLIER["latent"] * (DEFAULT_TARGET + DEFAULT_TARGET)
    skewed = build_conflict_skeleton(
        source_rate=source_rate, kA=Constant(9.0), kB=Constant(1.0)
    )
    skewed_a, skewed_b = skewed.oracle(Seed(4), sim_cfg)
    assert skewed_a > prod_a  # route A benefited from the reallocation ...
    assert skewed_b < DEFAULT_TARGET * 0.95  # ... at route B's expense


# ═══════════════════════════════════════════════════════════════════════════
# forced — a genuinely forbidding (V1, V2) frontier, verified by the
# simulate-and-check acceptance gate
# ═══════════════════════════════════════════════════════════════════════════


def test_forced_rung_frontier_provably_forbids_both_targets() -> None:
    # draft_conflict_world itself runs the Q2=C simulate-and-check gate for
    # "forced"; reaching here without raising IS the first half of the proof.
    world, skeleton, objective = draft_conflict_world(Seed(5), rung="forced")
    del world
    sim_cfg = SimConfig(dt=0.05, steps=400, sample_every=50)

    prod_a, prod_b = skeleton.oracle(Seed(5), sim_cfg)
    assert not (prod_a >= DEFAULT_TARGET and prod_b >= DEFAULT_TARGET)

    # The closed-form structural bound: every achievable point sums to the
    # source rate, which sits below the combined target — no split can clear
    # both.
    source_rate = _S_MULTIPLIER["forced"] * (DEFAULT_TARGET + DEFAULT_TARGET)
    frontier = closed_form_frontier(source_rate)
    assert all(a + b == pytest.approx(source_rate) for a, b in frontier)
    assert source_rate < DEFAULT_TARGET + DEFAULT_TARGET
    assert not any(a >= DEFAULT_TARGET and b >= DEFAULT_TARGET for a, b in frontier)

    timeline = simulate(skeleton.materialize(Seed(5)), sim_cfg, Seed(5).child("oracle-sim"))
    assert objective.scorer(timeline) < 1.0


def test_forced_gate_rejects_a_deliberately_under_supplied_source() -> None:
    """The gate itself: an ample source_rate relative to tiny targets is
    trivially satisfiable by every swept split — a sanity check that the gate
    actually fires (rather than vacuously passing)."""
    with pytest.raises(SkeletonError):
        # A source_rate the sweep can plainly satisfy both targets under
        # (both targets tiny relative to supply) — the gate must raise.
        _assert_forced_gate(Seed(6), source_rate=100.0, v1_target=1.0, v2_target=1.0)


# ═══════════════════════════════════════════════════════════════════════════
# Seed-determinism
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("rung", RUNGS)
def test_draft_is_seed_deterministic(rung: str) -> None:
    world1, skeleton1, objective1 = draft_conflict_world(Seed(42), rung=rung)
    world2, skeleton2, objective2 = draft_conflict_world(Seed(42), rung=rung)

    assert world1.chemistry.molecules.keys() == world2.chemistry.molecules.keys()
    assert world1.chemistry.reactions.keys() == world2.chemistry.reactions.keys()

    sim_cfg = SimConfig(dt=0.05, steps=200, sample_every=50)
    point1 = skeleton1.oracle(Seed(42), sim_cfg)
    point2 = skeleton2.oracle(Seed(42), sim_cfg)
    assert point1 == point2
    assert objective1.target == objective2.target


# ═══════════════════════════════════════════════════════════════════════════
# End-to-end: a ScriptedAgent runs a generated conflict world through
# ScenarioRunner.run — no LLM.
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("rung", RUNGS)
def test_scripted_agent_runs_conflict_world_through_scenario_runner(rung: str) -> None:
    world, skeleton, objective = draft_conflict_world(Seed(9), rung=rung)
    assert isinstance(objective, OutcomeObjective)

    probe = next(iter(world.chemistry.molecules))
    task = TaskInstance(
        archetype=f"conflict_{rung}",
        world="world0",
        skeleton=CarveResult(motif=Motif(roles=(), edges=()), binding={}),
        objective=objective,
        question=Question(structured=set(), kind="node_set"),
        setup={},
    )
    policy = (Measure(probe=probe), Commit(answer=Answer(value=0.0, kind="scalar")))
    agent = ScriptedAgent(policy, seed=Seed(0))

    record = run(world, task, agent, {}, Seed(10), sim_cfg=SimConfig(dt=0.05, steps=200, sample_every=50))

    assert isinstance(record, TrialRecord)
    assert record.terminal_reason == "committed"
    assert 0.0 <= record.objective_score <= 1.0
    if rung in ("compatible", "latent"):
        assert record.objective_score > 0.9
    if rung == "forced":
        assert record.objective_score < 1.0


# ═══════════════════════════════════════════════════════════════════════════
# T088 conflict_gen 2–3: the default split and the gate's clock
# ═══════════════════════════════════════════════════════════════════════════


def test_latent_default_split_sits_on_the_boundary_for_unequal_targets() -> None:
    """conflict_gen 2: with ``v1 != v2`` a balanced ``kA == kB`` split sent
    S/2 to each route and missed the larger target outright (8 vs 12 → the
    min-of-components score 1/5). The default now splits in the targets'
    ratio, so both products approach their goals from just below, as on
    the equal-target ladder."""
    world, _skeleton, objective = draft_conflict_world(Seed(3), rung="latent", v1_target=8.0, v2_target=12.0)
    timeline = simulate(world, SimConfig(dt=0.05, steps=800, sample_every=100))
    assert objective.scorer(timeline) > 0.999
    world_eq, _, objective_eq = draft_conflict_world(Seed(3), rung="latent")
    rx = world_eq.chemistry.reactions
    assert rx["root/crux/route_a/rxn"].rate == 1.0 == rx["root/crux/route_b/rxn"].rate


def test_forced_gate_runs_on_the_callers_clock(monkeypatch) -> None:
    """conflict_gen 3: ``sim_cfg`` was accepted and never read — the gate
    always simulated on the module's 20 s clock."""
    import alienbio.suite.conflict_gen as cg

    seen: list[SimConfig] = []
    original = cg.sweep_conflict_frontier

    def recording(build, seed, points, sim_cfg):  # type: ignore[no-untyped-def]
        seen.append(sim_cfg)
        return original(build, seed, points, sim_cfg)

    monkeypatch.setattr(cg, "sweep_conflict_frontier", recording)
    clock = SimConfig(dt=0.1, steps=50, sample_every=10)
    draft_conflict_world(Seed(4), rung="forced", sim_cfg=clock)
    assert seen == [clock]


@pytest.mark.parametrize("kwargs", [{"v1_target": 0.0}, {"v2_target": -1.0}, {"v1_target": float("nan")}])
def test_draft_refuses_a_non_positive_target(kwargs) -> None:
    with pytest.raises(ValueError, match=next(iter(kwargs))):
        draft_conflict_world(Seed(5), rung="latent", **kwargs)
