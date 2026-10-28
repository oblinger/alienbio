"""Acceptance tests for the M31.3 fixed-model / vary-world (Delta) harness
generator (F022).

Exercises ``draft_delta_pair`` — the pair is matched by construction (same
interface/topology/size, differing in exactly one rewired edge), the Q3=C
simulate-both acceptance gate (answers differ + both are discoverable),
seed-determinism, and one full ``ScenarioRunner`` (F021) trial with
``ScriptedAgent``s (no LLM): a true-driver-committing agent scores well on
BOTH worlds, while a FIXED agent that always commits the conventional
("bigger signal") heuristic answer scores well on ``W_match`` and poorly on
``W_mismatch`` — the whole point of a fixed model against a varied world.
"""

from __future__ import annotations

import pytest

from alienbio.suite.agent import Commit, Measure, ScriptedAgent
from alienbio.suite.delta_gen import (
    DEFAULT_K_DRIVE,
    DEFAULT_K_SINK,
    DEFAULT_K_SINK_B,
    DEFAULT_K_T_SINK,
    DEFAULT_R_A,
    DEFAULT_R_B,
    DEFAULT_T_TARGET,
    _assert_delta_gate,
    draft_delta_pair,
)
from alienbio.suite.dist import Constant, Seed
from alienbio.suite.runner import run
from alienbio.suite.skeleton import SkeletonError
from alienbio.suite.trial import TrialRecord
from alienbio.suite.types import (
    Answer,
    AnswerObjective,
    CarveResult,
    Motif,
    Objective,
    Question,
    TaskInstance,
)
from alienbio.suite.verify import SimConfig

_SIM_CFG = SimConfig(dt=0.05, steps=400, sample_every=50)


# ═══════════════════════════════════════════════════════════════════════════
# The pair materializes + validates clean on the conserving engine
# ═══════════════════════════════════════════════════════════════════════════


def test_pair_materializes_and_validates_clean() -> None:
    (world_match, skeleton_match, objective_match), (
        world_mismatch,
        skeleton_mismatch,
        objective_mismatch,
    ) = draft_delta_pair(Seed(1))

    assert skeleton_match.chemistry is not None
    assert skeleton_mismatch.chemistry is not None
    assert skeleton_match.validate() is None
    assert skeleton_mismatch.validate() is None
    assert isinstance(objective_match, AnswerObjective)
    assert isinstance(objective_mismatch, AnswerObjective)
    assert len(world_match.chemistry.reactions) > 0
    assert len(world_mismatch.chemistry.reactions) > 0


# ═══════════════════════════════════════════════════════════════════════════
# The pair is matched: identical interface/topology/size
# ═══════════════════════════════════════════════════════════════════════════


def test_pair_is_matched_same_interface_topology_size() -> None:
    (world_match, skeleton_match, _obj_match), (
        world_mismatch,
        skeleton_mismatch,
        _obj_mismatch,
    ) = draft_delta_pair(Seed(2))

    # Same reaction ids and same molecule ids tree-wide — the block tree
    # (names/order) is identical across the pair; only pool_bindings differ.
    assert set(world_match.chemistry.reactions.keys()) == set(
        world_mismatch.chemistry.reactions.keys()
    )
    assert set(world_match.chemistry.molecules.keys()) == set(
        world_mismatch.chemistry.molecules.keys()
    )
    assert len(world_match.chemistry.reactions) == len(world_mismatch.chemistry.reactions)
    assert len(world_match.chemistry.molecules) == len(world_mismatch.chemistry.molecules)

    # Same control surface / crux path shape.
    assert skeleton_match.control_surface == skeleton_mismatch.control_surface
    assert skeleton_match.crux == skeleton_mismatch.crux


def test_pair_differs_by_exactly_one_edge() -> None:
    """Mechanically audits the Q3=C claim: walk both assembled chemistries
    and confirm every reaction is byte-identical (same reactants/products/
    rate by molecule NAME) except ``route_drive``'s own reaction, whose
    REACTANT (not its rate, not its product) is the one thing that flips."""
    (world_match, _sk_match, _obj_match), (
        world_mismatch,
        _sk_mismatch,
        _obj_mismatch,
    ) = draft_delta_pair(Seed(3))

    def _names(mapping) -> dict:
        return {m.name: coef for m, coef in mapping.items()}

    differing: list[str] = []
    for rxn_id, rxn_match in world_match.chemistry.reactions.items():
        rxn_mismatch = world_mismatch.chemistry.reactions[rxn_id]
        reactants_match = _names(rxn_match.reactants)
        reactants_mismatch = _names(rxn_mismatch.reactants)
        products_match = _names(rxn_match.products)
        products_mismatch = _names(rxn_mismatch.products)
        if (
            reactants_match != reactants_mismatch
            or products_match != products_mismatch
            or rxn_match.rate != rxn_mismatch.rate
        ):
            differing.append(rxn_id)
            # Only the reactant identity may differ; rate and products must not.
            assert products_match == products_mismatch, rxn_id
            assert rxn_match.rate == rxn_mismatch.rate, rxn_id
            assert set(reactants_match.values()) == set(reactants_mismatch.values())

    assert len(differing) == 1
    assert differing[0].endswith("route_drive/rxn")


# ═══════════════════════════════════════════════════════════════════════════
# The Q3=C simulate-both gate: answers differ + both are discoverable
# ═══════════════════════════════════════════════════════════════════════════


def test_true_driver_answers_differ_across_pair() -> None:
    (_world_match, _sk_match, objective_match), (
        _world_mismatch,
        _sk_mismatch,
        objective_mismatch,
    ) = draft_delta_pair(Seed(4))
    assert isinstance(objective_match, AnswerObjective)
    assert isinstance(objective_mismatch, AnswerObjective)
    assert objective_match.key.value != objective_mismatch.key.value


def test_gate_rejects_a_pair_whose_switch_did_not_flip_the_answer() -> None:
    """Sanity check that the gate itself actually fires: feeding it the SAME
    side twice (a switch that trivially did not flip anything) must raise."""
    match, _mismatch = draft_delta_pair(Seed(5))
    with pytest.raises(SkeletonError):
        _assert_delta_gate(
            Seed(5),
            match,
            match,
            r_a=DEFAULT_R_A,
            r_b=DEFAULT_R_B,
            k_drive=Constant(DEFAULT_K_DRIVE),
            k_sink=Constant(DEFAULT_K_SINK),
            k_sink_b=Constant(DEFAULT_K_SINK_B),
            k_t_sink=Constant(DEFAULT_K_T_SINK),
            t_target=DEFAULT_T_TARGET,
            sim_cfg=_SIM_CFG,
        )


def test_r_a_must_exceed_r_b() -> None:
    with pytest.raises(ValueError):
        draft_delta_pair(Seed(6), r_a=1.0, r_b=1.0)
    with pytest.raises(ValueError):
        draft_delta_pair(Seed(6), r_a=1.0, r_b=5.0)


# ═══════════════════════════════════════════════════════════════════════════
# Seed-determinism
# ═══════════════════════════════════════════════════════════════════════════


def test_draft_is_seed_deterministic() -> None:
    (world1_m, sk1_m, obj1_m), (world1_x, sk1_x, obj1_x) = draft_delta_pair(Seed(42))
    (world2_m, sk2_m, obj2_m), (world2_x, sk2_x, obj2_x) = draft_delta_pair(Seed(42))

    assert world1_m.chemistry.molecules.keys() == world2_m.chemistry.molecules.keys()
    assert world1_m.chemistry.reactions.keys() == world2_m.chemistry.reactions.keys()
    assert world1_x.chemistry.molecules.keys() == world2_x.chemistry.molecules.keys()
    assert world1_x.chemistry.reactions.keys() == world2_x.chemistry.reactions.keys()

    assert isinstance(obj1_m, AnswerObjective) and isinstance(obj2_m, AnswerObjective)
    assert isinstance(obj1_x, AnswerObjective) and isinstance(obj2_x, AnswerObjective)
    assert obj1_m.key.value == obj2_m.key.value
    assert obj1_x.key.value == obj2_x.key.value

    sim_cfg = SimConfig(dt=0.05, steps=200, sample_every=50)
    point1_m = sk1_m.oracle(Seed(42), sim_cfg)
    point2_m = sk2_m.oracle(Seed(42), sim_cfg)
    assert point1_m == point2_m


# ═══════════════════════════════════════════════════════════════════════════
# End-to-end: ScriptedAgents run the Delta pair through ScenarioRunner.run —
# a fixed decision rule diverges across the matched pair — no LLM.
# ═══════════════════════════════════════════════════════════════════════════


def _make_task(objective: Objective, archetype: str) -> TaskInstance:
    return TaskInstance(
        archetype=archetype,
        world="world0",
        skeleton=CarveResult(motif=Motif(roles=(), edges=()), binding={}),
        objective=objective,
        question=Question(structured=set(), kind="node_id"),
        setup={},
    )


def test_true_driver_agent_scores_perfectly_on_both_worlds() -> None:
    (world_match, _sk_match, objective_match), (
        world_mismatch,
        _sk_mismatch,
        objective_mismatch,
    ) = draft_delta_pair(Seed(9))
    assert isinstance(objective_match, AnswerObjective)
    assert isinstance(objective_mismatch, AnswerObjective)

    for world, objective in ((world_match, objective_match), (world_mismatch, objective_mismatch)):
        task = _make_task(objective, "delta_true_driver")
        probe = next(iter(world.chemistry.molecules))
        policy = (
            Measure(probe=probe),
            Commit(answer=Answer(value=objective.key.value, kind="node_id")),
        )
        agent = ScriptedAgent(policy, seed=Seed(0))
        record = run(world, task, agent, {}, Seed(10))
        assert isinstance(record, TrialRecord)
        assert record.terminal_reason == "committed"
        assert record.objective_score == 1.0


def test_fixed_conventional_heuristic_agent_diverges_across_the_pair() -> None:
    """The fixed decision RULE "always guess the bigger/conventionally-
    implicated signal" (``source_a``, always the larger supply rate) scores
    well on ``W_match`` (where it happens to be right) and poorly on
    ``W_mismatch`` (where the causal edge was rewired onto ``source_b``) —
    same rule, same interface, a fixed model + varied world diverging."""
    (world_match, skeleton_match, objective_match), (
        world_mismatch,
        skeleton_mismatch,
        objective_mismatch,
    ) = draft_delta_pair(Seed(11))
    assert isinstance(objective_match, AnswerObjective)
    assert isinstance(objective_mismatch, AnswerObjective)

    crux_match = skeleton_match.root.children[0]
    crux_mismatch = skeleton_mismatch.root.children[0]
    source_a_match = next(c for c in crux_match.children if c.name == "source_a")
    source_a_mismatch = next(c for c in crux_mismatch.children if c.name == "source_a")

    # The fixed rule: always commit "source_a" (the conventionally larger
    # signal) as the answer, regardless of which world it is looking at.
    conventional_answer_match = source_a_match.resolved_ports["out"]
    conventional_answer_mismatch = source_a_mismatch.resolved_ports["out"]

    task_match = _make_task(objective_match, "delta_conventional_heuristic")
    probe_match = next(iter(world_match.chemistry.molecules))
    policy_match = (
        Measure(probe=probe_match),
        Commit(answer=Answer(value=conventional_answer_match, kind="node_id")),
    )
    record_match = run(
        world_match, task_match, ScriptedAgent(policy_match, seed=Seed(0)), {}, Seed(10)
    )

    task_mismatch = _make_task(objective_mismatch, "delta_conventional_heuristic")
    probe_mismatch = next(iter(world_mismatch.chemistry.molecules))
    policy_mismatch = (
        Measure(probe=probe_mismatch),
        Commit(answer=Answer(value=conventional_answer_mismatch, kind="node_id")),
    )
    record_mismatch = run(
        world_mismatch,
        task_mismatch,
        ScriptedAgent(policy_mismatch, seed=Seed(0)),
        {},
        Seed(10),
    )

    assert record_match.terminal_reason == "committed"
    assert record_mismatch.terminal_reason == "committed"
    assert record_match.objective_score == 1.0  # right for the wrong (heuristic) reason
    assert record_mismatch.objective_score == 0.0  # same rule, now wrong


# ═══════════════════════════════════════════════════════════════════════════
# T088 Q4 = A: each arm's levels carry its name at every time
# ═══════════════════════════════════════════════════════════════════════════


def _levels(side, horizon_steps: int = 2000):
    """Dense driver/decoy levels of a drafted side over 100 s (5x the
    generator's horizon, so the order is checked well past it)."""
    from alienbio.suite.verify import simulate

    world, skeleton, objective = side
    blocks = {c.name: c for c in skeleton.root.children[0].children}
    a_id = blocks["source_a"].resolved_ports["out"]
    b_id = blocks["source_b"].resolved_ports["out"]
    timeline = simulate(world, SimConfig(dt=0.05, steps=horizon_steps, sample_every=1))
    from alienbio.suite.skeleton import state_amount

    return [
        (t, state_amount(s, a_id), state_amount(s, b_id), objective.key.value == a_id)
        for t, s in zip(timeline.times[1:], timeline.states[1:])
    ]


def test_match_driver_reads_larger_and_mismatch_decoy_reads_larger_throughout() -> None:
    """The analysis round's repro: at the old drains the decoy overtook the
    driver at about 2.6 s on BOTH arms. Now the bigger supply (``source_a``)
    is also the bigger level at every sample on both arms — the true driver
    on ``W_match``, the decoy on ``W_mismatch``."""
    match, mismatch = draft_delta_pair(Seed(8))
    for side, a_drives in ((match, True), (mismatch, False)):
        rows = _levels(side)
        assert all(row[3] == a_drives for row in rows)
        assert all(a > b for _t, a, b, _ in rows), next((r for r in rows if not r[1] > r[2]))


def test_gate_refuses_a_decoy_drain_that_lets_the_decoy_overtake_on_match() -> None:
    """The old shape (``sink_b`` at 0.05) is now refused at draft, naming the
    arm and the order that failed."""
    with pytest.raises(SkeletonError, match="W_match steady levels"):
        draft_delta_pair(Seed(8), k_sink_b=Constant(0.05))


def test_gate_leaves_the_drafted_skeletons_cache_alone() -> None:
    """T088 delta_gen 3: the gate's baseline used to re-materialize the
    drafted skeleton, replacing the realized tree and chemistry cached
    behind the returned world. They are now the objects ``materialize``
    built for that world."""
    from alienbio.suite.skeleton import Skeleton

    seen: list[tuple[int, int]] = []
    original = Skeleton.materialize

    def recording(self, seed):  # type: ignore[no-untyped-def]
        world = original(self, seed)
        seen.append((id(self), id(self.chemistry)))
        return world

    Skeleton.materialize = recording  # type: ignore[method-assign]
    try:
        (world_m, sk_m, _), (world_x, sk_x, _) = draft_delta_pair(Seed(3))
    finally:
        Skeleton.materialize = original  # type: ignore[method-assign]
    for world, sk in ((world_m, sk_m), (world_x, sk_x)):
        assert [chem for owner, chem in seen if owner == id(sk)] == [id(sk.chemistry)]
        assert world.chemistry is sk.chemistry


@pytest.mark.parametrize(
    "kwargs",
    [
        {"r_b": -1.0},
        {"r_b": 0.0},
        {"r_a": float("inf")},
        {"t_target": 0.0},
        {"t_target": -0.5},
        {"r_a": True},
    ],
)
def test_draft_refuses_non_positive_or_non_finite_rates(kwargs) -> None:
    """T088 delta_gen 4: a negative or zero supply, an infinite one, or a
    non-positive target refuse as a ``ValueError`` naming the argument, not
    as a gate ``SkeletonError`` (or not at all)."""
    with pytest.raises(ValueError, match=next(iter(kwargs))):
        draft_delta_pair(Seed(6), **kwargs)
