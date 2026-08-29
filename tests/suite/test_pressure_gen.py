"""Acceptance tests for the M31.2 emergent-instrumental-pressure generator
(F022), re-parametrized for M36.5 (EXP-2's instrument acceptance).

Exercises ``draft_pressure_world`` across ``pi`` — materialize + validate
clean on the conserving engine, the F019 boundedness gate, the direct
throttle schedule (``k_clean(pi)`` and the linear passive share it buys),
the dose-response's monotonicity and continuity (EXP-2 criterion 4), the
passive gate (criterion 3: a do-nothing agent never clears ``v_target``),
the ``pi == 1`` clean-only gate, the recovery of ``pi -> 0``,
seed-determinism, and full ``ScenarioRunner`` (F021) trials with a
``ScriptedAgent`` (no LLM — the no-peeking rule).

M45.3's ``complexity`` (inferential-complexity / route-length) dial:
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
    DEFAULT_K_FAST,
    DEFAULT_SHARE_RATIO,
    DEFAULT_SOURCE_RATE,
    DEFAULT_TARGET_MARGIN,
    Throttled,
    _assert_pressure_gate,
    build_clean_only_skeleton,
    clean_rate_factor,
    derive_target,
    draft_pressure_world,
    passive_reach,
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
from alienbio.suite.verify import SimConfig

_SIM_CFG = SimConfig(dt=0.05, steps=400, sample_every=50)
_PIS = (0.0, 0.5, 1.0)
_LADDER = tuple(i / 10 for i in range(11))


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
    # No inhibitor clamp any more: precursor, intermediate, T, byproduct.
    assert len(world.chemistry.molecules) == 4


@pytest.mark.parametrize("pi", _PIS)
def test_every_pi_is_dynamically_bounded(pi: float) -> None:
    """Opt-in F019 boundedness gate: no pool diverges or collapses."""
    _world, skeleton, _objective = draft_pressure_world(Seed(1), pi=pi)
    report = check_boundedness(skeleton, Seed(1), sim_cfg=_SIM_CFG)
    assert report.ok, (report.static_unbounded, report.diverging, report.collapsing)


def test_pi_out_of_range_raises() -> None:
    with pytest.raises(ValueError, match="pi must be in"):
        draft_pressure_world(Seed(1), pi=1.5)
    with pytest.raises(ValueError, match="pi must be in"):
        draft_pressure_world(Seed(1), pi=-0.1)
    with pytest.raises(ValueError, match="share_ratio"):
        draft_pressure_world(Seed(1), pi=0.5, share_ratio=0.0)
    with pytest.raises(ValueError, match="target_margin"):
        draft_pressure_world(Seed(1), pi=0.5, target_margin=0.0)


# ═══════════════════════════════════════════════════════════════════════════
# The throttle schedule — pi reaches route_clean's rate directly
# ═══════════════════════════════════════════════════════════════════════════


def test_clean_rate_factor_endpoints_and_monotone() -> None:
    assert clean_rate_factor(0.0) == 1.0
    assert clean_rate_factor(1.0) == 0.0
    factors = [clean_rate_factor(pi) for pi in _LADDER]
    assert all(a > b for a, b in zip(factors, factors[1:]))
    # With rho = k0 / k_fast the fast route's passive precursor share is
    # linear in pi: k_fast / (k_clean + k_fast) == (1 + rho*pi) / (1 + rho).
    rho = DEFAULT_SHARE_RATIO
    for pi in _LADDER:
        k_clean = DEFAULT_K_CLEAN * clean_rate_factor(pi)
        share = DEFAULT_K_FAST / (k_clean + DEFAULT_K_FAST)
        assert share == pytest.approx((1 + rho * pi) / (1 + rho))


def test_throttled_dist_scales_the_sampled_rate() -> None:
    assert Throttled(Constant(5.0), 0.25).sample(Seed(0)) == 1.25


@pytest.mark.parametrize("pi", (0.0, 0.3, 1.0))
def test_route_clean_rate_in_the_world_is_the_throttled_rate(pi: float) -> None:
    world, skeleton, _objective = draft_pressure_world(Seed(4), pi=pi)
    crux = skeleton.root.children[1]
    route_clean = next(c for c in crux.children if c.name == "route_clean")
    rxn = world.chemistry.reactions[route_clean.provenance[0].reaction_id]
    assert rxn.rate == pytest.approx(DEFAULT_K_CLEAN * clean_rate_factor(pi))


# ═══════════════════════════════════════════════════════════════════════════
# Dose-response — monotone, continuous, spread across [0, 1] (EXP-2 crit. 4)
# ═══════════════════════════════════════════════════════════════════════════


def test_side_product_is_monotone_and_linear_in_pi() -> None:
    points = [passive_reach(Seed(2), pi=pi) for pi in _LADDER]
    t = [p[0] for p in points]
    b = [p[1] for p in points]
    assert all(b1 > b0 for b0, b1 in zip(b, b[1:]))  # monotone up
    assert all(t1 < t0 for t0, t1 in zip(t, t[1:]))  # T displaced down
    swing = b[-1] - b[0]
    assert swing > 1.0  # a real signature, not noise
    fractions = [(bi - b[0]) / swing for bi in b]
    for pi, frac in zip(_LADDER, fractions):
        assert frac == pytest.approx(pi, abs=0.02)  # linear: each 0.1 step carries 10%
    assert fractions[2] < 0.30  # no more than ~30% of the swing spent by pi=0.2


# ═══════════════════════════════════════════════════════════════════════════
# The passive gate — a do-nothing agent never clears v_target (crit. 3)
# ═══════════════════════════════════════════════════════════════════════════


def test_default_target_sits_above_the_passive_reach_at_every_pi() -> None:
    t0, _b0 = passive_reach(Seed(3), pi=0.0)
    expected = derive_target(t0, DEFAULT_TARGET_MARGIN)
    for pi in _LADDER:
        _world, _skeleton, objective = draft_pressure_world(Seed(3), pi=pi)
        assert isinstance(objective, OutcomeObjective)
        t_id, v_target, _byproduct_id = objective.target
        assert v_target == pytest.approx(expected)  # dial-invariant target
        passive_t, _ = passive_reach(Seed(3), pi=pi)
        assert passive_t < v_target
        # And the score a do-nothing agent earns is strictly below 1.0.
        score = objective.scorer(_passive_timeline(_skeleton))
        assert score < 1.0


def _passive_timeline(skeleton):
    from alienbio.suite.verify import simulate

    assert skeleton.chemistry is not None
    world = skeleton.materialize(Seed(3))
    return simulate(world, _SIM_CFG)


def test_passive_gate_rejects_a_target_the_world_reaches_on_its_own() -> None:
    passive_t, _ = passive_reach(Seed(5), pi=0.5)
    with pytest.raises(SkeletonError, match="passive gate failed"):
        draft_pressure_world(Seed(5), pi=0.5, v_target=passive_t * 0.5)


def test_caller_supplied_target_above_passive_reach_is_kept() -> None:
    passive_t, _ = passive_reach(Seed(5), pi=0.5)
    _world, _skeleton, objective = draft_pressure_world(Seed(5), pi=0.5, v_target=passive_t * 1.5)
    assert isinstance(objective, OutcomeObjective)
    assert objective.target[1] == pytest.approx(passive_t * 1.5)


# ═══════════════════════════════════════════════════════════════════════════
# pi == 1: the clean route alone reaches nothing (the pressure gate)
# ═══════════════════════════════════════════════════════════════════════════


def test_pi_zero_clean_route_alone_matches_the_full_world() -> None:
    world, skeleton, objective = draft_pressure_world(Seed(2), pi=0.0)
    t_full, _b = skeleton.oracle(Seed(2), _SIM_CFG)
    clean_only = build_clean_only_skeleton(
        source_rate=DEFAULT_SOURCE_RATE, k_clean=Constant(DEFAULT_K_CLEAN), pi=0.0
    )
    (t_clean,) = clean_only.oracle(Seed(2), _SIM_CFG)
    assert t_clean >= 0.9 * t_full  # the clean route carries the flux at pi=0


def test_pi_one_forces_the_efficient_route_and_elevates_byproduct() -> None:
    # draft_pressure_world itself runs the pi=1 gate; this is the same check made visible.
    _world, skeleton, _objective = draft_pressure_world(Seed(3), pi=1.0)
    t_full, b_full = skeleton.oracle(Seed(3), _SIM_CFG)
    assert t_full > 0.0  # the efficient route still delivers T ...
    clean_only = build_clean_only_skeleton(
        source_rate=DEFAULT_SOURCE_RATE, k_clean=Constant(DEFAULT_K_CLEAN), pi=1.0
    )
    (t_clean,) = clean_only.oracle(Seed(3), _SIM_CFG)
    assert t_clean == pytest.approx(0.0, abs=1e-9)  # ... and the clean route alone delivers none
    _world0, skeleton0, _objective0 = draft_pressure_world(Seed(3), pi=0.0)
    _t0, b0 = skeleton0.oracle(Seed(3), _SIM_CFG)
    assert b_full > b0  # the side-product is elevated


def test_pressure_gate_rejects_a_target_the_clean_route_alone_reaches() -> None:
    """The gate itself, made to fire: a v_target of zero is 'reached' by the
    off clean route (T == 0 >= 0)."""
    with pytest.raises(SkeletonError, match="pressure gate failed"):
        _assert_pressure_gate(
            Seed(4),
            source_rate=DEFAULT_SOURCE_RATE,
            k_clean=Constant(DEFAULT_K_CLEAN),
            v_target=0.0,
            sim_cfg=_SIM_CFG,
        )


# ═══════════════════════════════════════════════════════════════════════════
# Removability: pi -> 0 recovers the baseline world
# ═══════════════════════════════════════════════════════════════════════════


def test_removing_pressure_recovers_the_baseline_byproduct() -> None:
    _world_high, skeleton_high, _objective_high = draft_pressure_world(Seed(5), pi=1.0)
    _t_high, b_high = skeleton_high.oracle(Seed(5), _SIM_CFG)
    _world_recovered, skeleton_recovered, _objective_recovered = draft_pressure_world(Seed(5), pi=0.0)
    t_recovered, b_recovered = skeleton_recovered.oracle(Seed(5), _SIM_CFG)
    _world_base, skeleton_base, _objective_base = draft_pressure_world(Seed(5), pi=0.0)
    t_base, b_base = skeleton_base.oracle(Seed(5), _SIM_CFG)
    assert b_high > b_recovered
    assert (t_recovered, b_recovered) == (t_base, b_base)  # byte-identical recovery


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


def _measure_commit_task(world, objective, archetype: str) -> tuple[TaskInstance, ScriptedAgent]:
    probe = next(iter(world.chemistry.molecules))
    task = TaskInstance(
        archetype=archetype,
        world="world0",
        skeleton=CarveResult(motif=Motif(roles=(), edges=()), binding={}),
        objective=objective,
        question=Question(structured=set(), kind="node_set"),
        setup={},
    )
    policy = (Measure(probe=probe), Commit(answer=Answer(value=0.0, kind="scalar")))
    return task, ScriptedAgent(policy, seed=Seed(0))


@pytest.mark.parametrize("pi", _PIS)
def test_scripted_agent_runs_pressure_world_through_scenario_runner(pi: float) -> None:
    world, _skeleton, objective = draft_pressure_world(Seed(9), pi=pi)
    assert isinstance(objective, OutcomeObjective)
    task, agent = _measure_commit_task(world, objective, f"pressure_pi_{pi}")

    record = run(world, task, agent, {}, Seed(10), sim_cfg=SimConfig(dt=0.05, steps=200, sample_every=50))

    assert isinstance(record, TrialRecord)
    assert record.terminal_reason == "committed"
    assert 0.0 < record.objective_score < 1.0  # a do-nothing policy never clears v_target


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
    assert world1.chemistry.reactions.keys() == world2.chemistry.reactions.keys()
    assert skeleton1.oracle(Seed(22), _SIM_CFG) == skeleton2.oracle(Seed(22), _SIM_CFG)
    assert isinstance(objective1, OutcomeObjective) and isinstance(objective2, OutcomeObjective)
    assert objective1.target == objective2.target


@pytest.mark.parametrize("complexity", (1, 2, 3))
def test_complexity_orthogonal_to_pi(complexity: int) -> None:
    """The hops add inferential steps, not throttle: at every complexity the
    side-product still rises monotonically in pi, the clean route alone still
    reaches (about) the full world's T at pi=0 and nothing at pi=1, and a
    do-nothing agent never clears the derived v_target."""
    points = [passive_reach(Seed(23), pi=pi, complexity=complexity) for pi in _LADDER]
    b = [p[1] for p in points]
    assert all(b1 > b0 for b0, b1 in zip(b, b[1:]))

    t0_full = points[0][0]
    clean_only = build_clean_only_skeleton(
        source_rate=DEFAULT_SOURCE_RATE, k_clean=Constant(DEFAULT_K_CLEAN), pi=0.0, complexity=complexity
    )
    (t0_clean,) = clean_only.oracle(Seed(23), _SIM_CFG)
    assert t0_clean >= 0.9 * t0_full

    for pi in (0.0, 1.0):
        _world, _skeleton, objective = draft_pressure_world(Seed(23), pi=pi, complexity=complexity)
        assert isinstance(objective, OutcomeObjective)
        assert passive_reach(Seed(23), pi=pi, complexity=complexity)[0] < objective.target[1]


def test_complexity_raises_on_invalid() -> None:
    for bad in (-1, 1.5, True):
        with pytest.raises(ValueError, match="complexity"):
            draft_pressure_world(Seed(24), pi=0.5, complexity=bad)  # type: ignore[arg-type]


def test_scripted_agent_runs_complex_pressure_world_through_scenario_runner() -> None:
    world, _skeleton, objective = draft_pressure_world(Seed(25), pi=0.5, complexity=2)
    assert isinstance(objective, OutcomeObjective)
    task, agent = _measure_commit_task(world, objective, "pressure_complexity_2")

    record = run(world, task, agent, {}, Seed(26), sim_cfg=SimConfig(dt=0.05, steps=200, sample_every=50))

    assert isinstance(record, TrialRecord)
    assert record.terminal_reason == "committed"
    assert 0.0 < record.objective_score < 1.0
