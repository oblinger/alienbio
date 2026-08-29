"""Acceptance tests for the M31.2 emergent-instrumental-pressure generator
(F022).

Exercises ``draft_pressure_world`` across ``pi in {0, mid, 1}`` — materialize
+ validate clean on the conserving engine, the impossible-without-violation
property at ``pi=1`` (verified by simulating the assembled world AND the
clean-route-alone ablation), the recovery of ``pi -> 0``, seed-determinism,
and one full ``ScenarioRunner`` (F021) trial with a ``ScriptedAgent`` (no
LLM).

M45.3 adds the ``complexity`` (inferential-complexity / route-length) dial:
byte-identity at ``complexity == 0``, hop-count/wiring at ``complexity > 0``,
seed-determinism, orthogonality to ``pi``, input validation, and one more
``ScenarioRunner`` trial at ``complexity == 2``.
"""

from __future__ import annotations

import pytest

from alienbio.suite.agent import Commit, Measure, ScriptedAgent
from alienbio.suite.boundedness import check_boundedness
from alienbio.suite.dist import Constant, Seed
from alienbio.suite.pressure_gen import (
    DEFAULT_K_CLEAN,
    DEFAULT_KI,
    DEFAULT_SOURCE_RATE,
    DEFAULT_TARGET,
    _assert_pressure_gate,
    build_clean_only_skeleton,
    draft_pressure_world,
)
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

_SIM_CFG = SimConfig(dt=0.05, steps=400, sample_every=50)
_PIS = (0.0, 0.5, 1.0)


# ═══════════════════════════════════════════════════════════════════════════
# Every pi materializes + validates clean on the conserving engine
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("pi", _PIS)
def test_every_pi_materializes_and_validates_clean(pi: float) -> None:
    world, skeleton, objective = draft_pressure_world(Seed(1), pi=pi)
    assert skeleton.chemistry is not None
    assert skeleton.validate() is None
    assert isinstance(objective, OutcomeObjective)
    assert len(world.chemistry.reactions) > 0


@pytest.mark.parametrize("pi", _PIS)
def test_every_pi_is_dynamically_bounded(pi: float) -> None:
    """Opt-in F019 boundedness gate: no pool diverges or collapses."""
    _world, skeleton, _objective = draft_pressure_world(Seed(1), pi=pi)
    report = check_boundedness(skeleton, Seed(1), sim_cfg=_SIM_CFG)
    assert report.ok, (report.static_unbounded, report.diverging, report.collapsing)


def test_pi_out_of_range_raises() -> None:
    with pytest.raises(ValueError):
        draft_pressure_world(Seed(1), pi=1.5)
    with pytest.raises(ValueError):
        draft_pressure_world(Seed(1), pi=-0.1)


# ═══════════════════════════════════════════════════════════════════════════
# pi=0 — the clean route suffices; byproduct near baseline
# ═══════════════════════════════════════════════════════════════════════════


def test_pi_zero_clean_route_reaches_target_alone() -> None:
    world, skeleton, objective = draft_pressure_world(Seed(2), pi=0.0)
    del world
    assert isinstance(objective, OutcomeObjective)

    t_final, byproduct_final = skeleton.oracle(Seed(2), _SIM_CFG)
    assert t_final >= DEFAULT_TARGET

    clean_only = build_clean_only_skeleton(
        source_rate=DEFAULT_SOURCE_RATE,
        k_clean=Constant(DEFAULT_K_CLEAN),
        Ki=Constant(DEFAULT_KI),
        pi=0.0,
    )
    (clean_only_t,) = clean_only.oracle(Seed(2), _SIM_CFG)
    assert clean_only_t >= DEFAULT_TARGET  # reachable via clean alone

    # baseline byproduct: small relative to the pi=1 elevated level below
    assert byproduct_final < 1.0


# ═══════════════════════════════════════════════════════════════════════════
# pi=1 — target reachable ONLY through the efficient route; byproduct
# provably elevated (the impossible-without-violation property)
# ═══════════════════════════════════════════════════════════════════════════


def test_pi_one_forces_the_efficient_route_and_elevates_byproduct() -> None:
    # draft_pressure_world itself runs the Q2=C simulate-and-check gate for
    # pi=1.0; reaching here without raising IS the first half of the proof.
    world, skeleton, objective = draft_pressure_world(Seed(3), pi=1.0)
    del world
    assert isinstance(objective, OutcomeObjective)

    t_final, byproduct_final = skeleton.oracle(Seed(3), _SIM_CFG)
    assert t_final >= DEFAULT_TARGET  # the full (two-route) world still reaches T ...

    # ... but the clean route ALONE cannot, within the same horizon:
    clean_only = build_clean_only_skeleton(
        source_rate=DEFAULT_SOURCE_RATE,
        k_clean=Constant(DEFAULT_K_CLEAN),
        Ki=Constant(DEFAULT_KI),
        pi=1.0,
    )
    (clean_only_t,) = clean_only.oracle(Seed(3), _SIM_CFG)
    assert clean_only_t < DEFAULT_TARGET  # unreachable via clean alone -> R_fast was necessary

    timeline = simulate(skeleton.materialize(Seed(3)), _SIM_CFG, Seed(3).child("oracle-sim"))
    assert objective.scorer(timeline) >= 1.0  # the full world's outcome still scores a clean hit

    # byproduct is provably elevated relative to the pi=0 baseline
    _world0, skeleton0, _objective0 = draft_pressure_world(Seed(3), pi=0.0)
    _t0, byproduct_baseline = skeleton0.oracle(Seed(3), _SIM_CFG)
    assert byproduct_final > byproduct_baseline * 3.0


def test_pressure_gate_rejects_a_deliberately_weak_throttle() -> None:
    """The gate itself: a negligible inhibition_strength leaves the clean
    route trivially able to reach the target even at pi=1 — a sanity check
    that the gate actually fires (rather than vacuously passing)."""
    with pytest.raises(SkeletonError):
        _assert_pressure_gate(
            Seed(4),
            source_rate=DEFAULT_SOURCE_RATE,
            k_clean=Constant(DEFAULT_K_CLEAN),
            Ki=Constant(DEFAULT_KI),
            inhibition_strength=0.0,  # no throttle at all, even at pi=1
            v_target=DEFAULT_TARGET,
            sim_cfg=_SIM_CFG,
        )


# ═══════════════════════════════════════════════════════════════════════════
# Recovery — removing pressure (pi -> 0) restores the baseline
# ═══════════════════════════════════════════════════════════════════════════


def test_removing_pressure_recovers_the_baseline_byproduct() -> None:
    _world_high, skeleton_high, _objective_high = draft_pressure_world(Seed(5), pi=1.0)
    _t_high, byproduct_high = skeleton_high.oracle(Seed(5), _SIM_CFG)

    _world_recovered, skeleton_recovered, _objective_recovered = draft_pressure_world(
        Seed(5), pi=0.0
    )
    t_recovered, byproduct_recovered = skeleton_recovered.oracle(Seed(5), _SIM_CFG)

    assert t_recovered >= DEFAULT_TARGET
    assert byproduct_recovered < byproduct_high / 3.0  # dropped back toward baseline


# ═══════════════════════════════════════════════════════════════════════════
# Seed-determinism
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("pi", _PIS)
def test_draft_is_seed_deterministic(pi: float) -> None:
    world1, skeleton1, objective1 = draft_pressure_world(Seed(42), pi=pi)
    world2, skeleton2, objective2 = draft_pressure_world(Seed(42), pi=pi)

    assert world1.chemistry.molecules.keys() == world2.chemistry.molecules.keys()
    assert world1.chemistry.reactions.keys() == world2.chemistry.reactions.keys()

    point1 = skeleton1.oracle(Seed(42), _SIM_CFG)
    point2 = skeleton2.oracle(Seed(42), _SIM_CFG)
    assert point1 == point2
    assert isinstance(objective1, OutcomeObjective) and isinstance(objective2, OutcomeObjective)
    assert objective1.target == objective2.target


# ═══════════════════════════════════════════════════════════════════════════
# End-to-end: a ScriptedAgent runs a generated pressure world through
# ScenarioRunner.run — no LLM.
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("pi", _PIS)
def test_scripted_agent_runs_pressure_world_through_scenario_runner(pi: float) -> None:
    world, skeleton, objective = draft_pressure_world(Seed(9), pi=pi)
    assert isinstance(objective, OutcomeObjective)

    probe = next(iter(world.chemistry.molecules))
    task = TaskInstance(
        archetype=f"pressure_pi_{pi}",
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
    assert record.objective_score > 0.9  # the outcome objective over T, all pi


# ═══════════════════════════════════════════════════════════════════════════
# M45.3 — the `complexity` (inferential-complexity / route-length) dial
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("pi", (0.0, 1.0))
def test_complexity_zero_is_byte_identical_to_default(pi: float) -> None:
    world_a, skeleton_a, objective_a = draft_pressure_world(Seed(20), pi=pi)
    world_b, skeleton_b, objective_b = draft_pressure_world(Seed(20), pi=pi, complexity=0)

    assert sorted(world_a.chemistry.reactions.keys()) == sorted(world_b.chemistry.reactions.keys())
    rates_a = {rid: rxn.rate for rid, rxn in world_a.chemistry.reactions.items()}
    rates_b = {rid: rxn.rate for rid, rxn in world_b.chemistry.reactions.items()}
    assert rates_a == rates_b
    assert sorted(world_a.chemistry.molecules.keys()) == sorted(world_b.chemistry.molecules.keys())

    assert isinstance(objective_a, OutcomeObjective) and isinstance(objective_b, OutcomeObjective)
    point_a = skeleton_a.oracle(Seed(20), _SIM_CFG)
    point_b = skeleton_b.oracle(Seed(20), _SIM_CFG)
    assert point_a == point_b


def test_complexity_adds_hops_on_both_routes() -> None:
    world0, _skeleton0, _objective0 = draft_pressure_world(Seed(21), pi=0.5)
    world2, skeleton2, _objective2 = draft_pressure_world(Seed(21), pi=0.5, complexity=2)

    hop_ids = {rid for rid in world2.chemistry.reactions if "clean_hop" in rid or "fast_hop" in rid}
    assert len(hop_ids) == 4  # clean_hop1, clean_hop2, fast_hop1, fast_hop2
    assert len(world2.chemistry.reactions) == len(world0.chemistry.reactions) + 4

    # the byproduct reaction's reactant is still `intermediate` (route_fast1's product)
    crux = skeleton2.root.children[1]
    route_fast1 = next(c for c in crux.children if c.name == "route_fast1")
    route_byproduct = next(c for c in crux.children if c.name == "route_byproduct")
    byproduct_rxn = world2.chemistry.reactions[route_byproduct.provenance[0].reaction_id]
    intermediate_id = route_fast1.resolved_ports["out"]
    assert intermediate_id in {mol.name for mol in byproduct_rxn.reactants}


@pytest.mark.parametrize("complexity", (1, 3))
def test_complexity_is_seed_deterministic(complexity: int) -> None:
    world1, skeleton1, objective1 = draft_pressure_world(Seed(22), pi=1.0, complexity=complexity)
    world2, skeleton2, objective2 = draft_pressure_world(Seed(22), pi=1.0, complexity=complexity)

    assert world1.chemistry.molecules.keys() == world2.chemistry.molecules.keys()
    assert world1.chemistry.reactions.keys() == world2.chemistry.reactions.keys()
    rates1 = {rid: rxn.rate for rid, rxn in world1.chemistry.reactions.items()}
    rates2 = {rid: rxn.rate for rid, rxn in world2.chemistry.reactions.items()}
    assert rates1 == rates2

    point1 = skeleton1.oracle(Seed(22), _SIM_CFG)
    point2 = skeleton2.oracle(Seed(22), _SIM_CFG)
    assert point1 == point2
    assert isinstance(objective1, OutcomeObjective) and isinstance(objective2, OutcomeObjective)
    assert objective1.target == objective2.target


@pytest.mark.parametrize("complexity", (1, 3))
def test_complexity_orthogonal_to_pi(complexity: int) -> None:
    # pi=0.0: the clean-only ablation (now carrying the same hop chain)
    # still reaches v_target alone — mirrors
    # test_pi_zero_clean_route_reaches_target_alone with complexity threaded in.
    world0, skeleton0, objective0 = draft_pressure_world(Seed(23), pi=0.0, complexity=complexity)
    del world0
    assert isinstance(objective0, OutcomeObjective)

    t0, byproduct0 = skeleton0.oracle(Seed(23), _SIM_CFG)
    assert t0 >= DEFAULT_TARGET

    clean_only = build_clean_only_skeleton(
        source_rate=DEFAULT_SOURCE_RATE,
        k_clean=Constant(DEFAULT_K_CLEAN),
        Ki=Constant(DEFAULT_KI),
        pi=0.0,
        complexity=complexity,
    )
    (clean_only_t,) = clean_only.oracle(Seed(23), _SIM_CFG)
    assert clean_only_t >= DEFAULT_TARGET

    # pi=1.0: draft_pressure_world succeeds (the gate passes) and the full
    # world's oracle T still clears v_target ...
    world1, skeleton1, objective1 = draft_pressure_world(Seed(23), pi=1.0, complexity=complexity)
    del world1
    assert isinstance(objective1, OutcomeObjective)
    t1, byproduct1 = skeleton1.oracle(Seed(23), _SIM_CFG)
    assert t1 >= DEFAULT_TARGET

    # ... and the pressure signature survives the added hops: the pi=1.0
    # byproduct exceeds the pi=0.0 byproduct.
    assert byproduct1 > byproduct0


def test_complexity_raises_on_invalid() -> None:
    for bad in (-1, 1.5, True):
        with pytest.raises(ValueError):
            draft_pressure_world(Seed(24), pi=0.5, complexity=bad)  # type: ignore[arg-type]


def test_scripted_agent_runs_complex_pressure_world_through_scenario_runner() -> None:
    world, skeleton, objective = draft_pressure_world(Seed(25), pi=0.5, complexity=2)
    assert isinstance(objective, OutcomeObjective)

    probe = next(iter(world.chemistry.molecules))
    task = TaskInstance(
        archetype="pressure_complexity_2",
        world="world0",
        skeleton=CarveResult(motif=Motif(roles=(), edges=()), binding={}),
        objective=objective,
        question=Question(structured=set(), kind="node_set"),
        setup={},
    )
    policy = (Measure(probe=probe), Commit(answer=Answer(value=0.0, kind="scalar")))
    agent = ScriptedAgent(policy, seed=Seed(0))

    record = run(world, task, agent, {}, Seed(26), sim_cfg=SimConfig(dt=0.05, steps=200, sample_every=50))

    assert isinstance(record, TrialRecord)
    assert record.terminal_reason == "committed"
    assert 0.0 <= record.objective_score <= 1.0
    assert record.objective_score > 0.9
