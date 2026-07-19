"""Unit + integration tests for the F014 skeleton block library (``suite/blocks.py``).

Two tiers: (1) per-block unit tests that call ``realize`` directly (bypassing
the full recursive ``Skeleton`` machinery — a block's ``realize`` is a plain
``(seed, ns, bound) -> Fragment`` function, so it's testable standalone) to
check emitted reactions, provenance, and the F012 conservation gate in
isolation; (2) one end-to-end integration test that composes
``Source + ConflictCrux + Pressure``, materializes, validates, and oracles.
"""

from __future__ import annotations

import pytest

from alienbio.bio.atom import get_atom
from alienbio.bio.conservation import (
    check_conservation,
    is_boundary_reaction,
    molecule_quantity,
    total_quantity,
    validate_conservation,
)
from alienbio.bio.molecule import MoleculeImpl
from alienbio.infra.mk import mk
from alienbio.suite.blocks import (
    ConflictCruxBlock,
    PoissonSchedule,
    PressureBlock,
    ReactionBlock,
    SinkBlock,
    SourceBlock,
    sweep_conflict_frontier,
)
from alienbio.suite.dist import Constant, Seed
from alienbio.suite.skeleton import (
    Port,
    PortDir,
    PoolBinding,
    Role,
    Skeleton,
    SkeletonBlock,
    SkeletonError,
)
from alienbio.suite.types import Timeline
from alienbio.suite.verify import SimConfig, simulate


# ═══════════════════════════════════════════════════════════════════════════
# ReactionBlock — the primitive
# ═══════════════════════════════════════════════════════════════════════════


def test_reaction_block_realize_emits_one_reaction_with_provenance() -> None:
    a = mk.M("A")
    b = mk.M("B")
    block = ReactionBlock(
        name="convert",
        role=Role.CRUX,
        ports=(Port("in", None, PortDir.IN), Port("out", None, PortDir.OUT)),
        rate=Constant(0.25),
    )
    fragment = block.realize(Seed(1), "root/convert", {"in": a, "out": b})

    assert len(fragment.reactions) == 1
    rxn = next(iter(fragment.reactions.values()))
    assert dict(rxn.reactants) == {a: 1.0}
    assert dict(rxn.products) == {b: 1.0}
    assert rxn.rate == 0.25
    assert not is_boundary_reaction(rxn)  # nonempty reactants AND products

    assert len(fragment.provenance) == 1
    prov = fragment.provenance[0]
    assert prov.reaction_id in fragment.reactions
    assert prov.container_id == "cell"

    assert set(fragment.molecules) == {"A", "B"}


def test_reaction_block_rate_is_sampled_from_the_dist_hole_deterministically() -> None:
    a, b = mk.M("A"), mk.M("B")
    block = ReactionBlock(
        name="convert",
        role=Role.CRUX,
        ports=(Port("in", None, PortDir.IN), Port("out", None, PortDir.OUT)),
        rate=Constant(3.5),
    )
    f1 = block.realize(Seed(7), "ns", {"in": a, "out": b})
    f2 = block.realize(Seed(7), "ns", {"in": a, "out": b})
    r1 = next(iter(f1.reactions.values()))
    r2 = next(iter(f2.reactions.values()))
    assert r1.rate == r2.rate == 3.5


def test_reaction_block_respects_stoich_overrides() -> None:
    a, b = mk.M("A"), mk.M("B")
    block = ReactionBlock(
        name="combine",
        role=Role.CRUX,
        ports=(Port("in", None, PortDir.IN), Port("out", None, PortDir.OUT)),
        stoich={"in": 2.0},
        rate=Constant(1.0),
    )
    fragment = block.realize(Seed(1), "ns", {"in": a, "out": b})
    rxn = next(iter(fragment.reactions.values()))
    assert dict(rxn.reactants) == {a: 2.0}
    assert dict(rxn.products) == {b: 1.0}


def test_reaction_block_balanced_atoms_pass_the_f012_gate() -> None:
    """An internal (non-boundary) reaction whose reactant/product atom
    composition matches passes ``validate_conservation`` cleanly."""
    carbon = get_atom("C")
    a = mk.M("A", atoms={carbon: 1})
    b = mk.M("B", atoms={carbon: 1})
    block = ReactionBlock(
        name="convert",
        role=Role.CRUX,
        ports=(Port("in", None, PortDir.IN), Port("out", None, PortDir.OUT)),
        rate=Constant(1.0),
    )
    fragment = block.realize(Seed(1), "ns", {"in": a, "out": b})
    chem = mk.C("chem", list(fragment.molecules.values()), list(fragment.reactions.values()))
    validate_conservation(chem)  # must not raise


def test_reaction_block_imbalanced_atoms_are_caught_by_the_f012_gate() -> None:
    """A mismatched atom composition on an internal reaction is a real
    conservation violation — the gate must not silently pass it."""
    carbon = get_atom("C")
    a = mk.M("A", atoms={carbon: 2})
    b = mk.M("B", atoms={carbon: 1})
    block = ReactionBlock(
        name="convert",
        role=Role.CRUX,
        ports=(Port("in", None, PortDir.IN), Port("out", None, PortDir.OUT)),
        rate=Constant(1.0),
    )
    fragment = block.realize(Seed(1), "ns", {"in": a, "out": b})
    chem = mk.C("chem", list(fragment.molecules.values()), list(fragment.reactions.values()))
    violations = check_conservation(chem)
    assert len(violations) == 1
    assert violations[0].reaction in fragment.reactions


# ═══════════════════════════════════════════════════════════════════════════
# SourceBlock / SinkBlock — boundary configs of ReactionBlock (Q4=A)
# ═══════════════════════════════════════════════════════════════════════════


def test_source_block_emits_a_boundary_reaction_with_empty_reactants() -> None:
    source = SourceBlock.make("source", rate=Constant(2.0))
    pool = mk.M("pool")
    fragment = source.realize(Seed(1), "root/source", {"out": pool})

    rxn = next(iter(fragment.reactions.values()))
    assert dict(rxn.reactants) == {}
    assert dict(rxn.products) == {pool: 1.0}
    assert is_boundary_reaction(rxn)
    assert rxn.rate == 2.0
    assert source.role is Role.SUPPLY


def test_sink_block_emits_a_boundary_reaction_with_empty_products() -> None:
    sink = SinkBlock.make("sink", rate=Constant(0.5))
    pool = mk.M("pool")
    fragment = sink.realize(Seed(1), "root/sink", {"in": pool})

    rxn = next(iter(fragment.reactions.values()))
    assert dict(rxn.reactants) == {pool: 1.0}
    assert dict(rxn.products) == {}
    assert is_boundary_reaction(rxn)
    assert rxn.rate == 0.5
    assert sink.role is Role.SINK


def test_boundary_blocks_are_exempt_even_when_atoms_are_absent_entirely() -> None:
    """Boundary reactions never need atom composition — they're exempt by
    construction (F012 boundary exemption), independent of conservation."""
    source = SourceBlock.make("source")
    pool = mk.M("pool")  # no atoms at all
    fragment = source.realize(Seed(1), "ns", {"out": pool})
    chem = mk.C("chem", list(fragment.molecules.values()), list(fragment.reactions.values()))
    validate_conservation(chem)  # must not raise: boundary reactions are exempt


# ═══════════════════════════════════════════════════════════════════════════
# ConflictCruxBlock
# ═══════════════════════════════════════════════════════════════════════════


def test_conflict_crux_block_shape() -> None:
    crux = ConflictCruxBlock.make("crux", kA=Constant(2.0), kB=Constant(1.0))
    assert crux.role is Role.CRUX
    assert {c.name for c in crux.children} == {"route_a", "route_b", "sink_a", "sink_b"}
    local_refs = {(pb.a, pb.b) for pb in crux.pool_bindings}
    assert ("self.precursor", "route_a.in") in local_refs
    assert ("self.precursor", "route_b.in") in local_refs
    assert ("route_a.out", "sink_a.in") in local_refs
    assert ("route_b.out", "sink_b.in") in local_refs


def test_conflict_crux_ground_truth_requires_materialize_first() -> None:
    crux = ConflictCruxBlock.make("crux")
    with pytest.raises(SkeletonError):
        crux.ground_truth(Timeline(times=(), states=()))


# ═══════════════════════════════════════════════════════════════════════════
# PressureBlock
# ═══════════════════════════════════════════════════════════════════════════


def test_pressure_block_default_is_a_constant_boundary_drain() -> None:
    pressure = PressureBlock.make("pressure", rate=Constant(0.3))
    pool = mk.M("stressed")
    fragment = pressure.realize(Seed(1), "root/pressure", {"stressed": pool})

    rxn = next(iter(fragment.reactions.values()))
    assert dict(rxn.reactants) == {pool: 1.0}
    assert dict(rxn.products) == {}
    assert is_boundary_reaction(rxn)
    assert rxn.rate == 0.3
    assert pressure.role is Role.PRESSURE
    assert pressure.poisson is None
    assert pressure.insult_times == ()


def test_pressure_block_poisson_schedule_is_seed_deterministic() -> None:
    schedule = PoissonSchedule(lam=0.5, horizon=20.0)
    pool = mk.M("stressed")

    p1 = PressureBlock.make("pressure", poisson=schedule)
    p1.realize(Seed(42), "root/pressure", {"stressed": pool})
    p2 = PressureBlock.make("pressure", poisson=schedule)
    p2.realize(Seed(42), "root/pressure", {"stressed": pool})

    assert p1.insult_times == p2.insult_times
    assert len(p1.insult_times) > 0
    assert all(0.0 < t <= schedule.horizon for t in p1.insult_times)
    assert list(p1.insult_times) == sorted(p1.insult_times)


def test_pressure_block_poisson_schedule_differs_across_seeds() -> None:
    schedule = PoissonSchedule(lam=0.5, horizon=20.0)
    pool = mk.M("stressed")

    p1 = PressureBlock.make("pressure", poisson=schedule)
    p1.realize(Seed(1), "root/pressure", {"stressed": pool})
    p2 = PressureBlock.make("pressure", poisson=schedule)
    p2.realize(Seed(2), "root/pressure", {"stressed": pool})

    assert p1.insult_times != p2.insult_times


# ═══════════════════════════════════════════════════════════════════════════
# Integration — Source + ConflictCrux + Pressure, end to end
# ═══════════════════════════════════════════════════════════════════════════


def _build(
    kA: Constant, kB: Constant, *, source_rate: float = 5.0, pressure_rate: float = 0.2
) -> Skeleton:
    source = SourceBlock.make("source", rate=Constant(source_rate))
    crux = ConflictCruxBlock.make("crux", kA=kA, kB=kB)
    pressure = PressureBlock.make("pressure", rate=Constant(pressure_rate))
    root = SkeletonBlock(
        name="root",
        role=Role.SUPPLY,
        children=(source, crux, pressure),
        pool_bindings=(
            PoolBinding("source.out", "crux.precursor"),
            PoolBinding("crux.precursor", "pressure.stressed"),
        ),
    )
    return Skeleton(root=root, control_surface=("root/source.out",), crux="root/crux")


_SIM_CFG = SimConfig(dt=0.05, steps=400, sample_every=50)


def test_integration_materialize_validate_oracle_round_trip() -> None:
    skeleton = _build(Constant(1.0), Constant(1.0))
    world = skeleton.materialize(Seed(100))

    # source, route_a, route_b, sink_a, sink_b, pressure
    assert len(world.chemistry.reactions) == 6
    # precursor, prodA, prodB
    assert len(world.chemistry.molecules) == 3

    assert skeleton.validate() is None

    point = skeleton.oracle(Seed(100), _SIM_CFG)
    assert isinstance(point, tuple)
    assert len(point) == 2
    prod_a, prod_b = point
    assert prod_a > 0.0
    assert prod_b > 0.0


def test_integration_conservation_canary_holds_across_the_timeline() -> None:
    """The conservation-canary invariant (``total_quantity``) must not drift
    step to step. The block library's auto-minted pools carry no atoms unless
    explicitly given some (there is no hook to inject atoms into an
    externally-shared pool through the ``Skeleton`` API), so this total is
    trivially the zero vector throughout — but it still exercises the real
    ``total_quantity`` machinery end to end and would catch a wiring bug that
    made the total non-invariant."""
    skeleton = _build(Constant(1.0), Constant(1.0))
    world = skeleton.materialize(Seed(101))
    timeline = simulate(world, _SIM_CFG, Seed(101).child("oracle-sim"))

    mol_ids = timeline.states[-1].molecule_ids
    assert mol_ids is not None
    per_index_quantity = [molecule_quantity(world.chemistry.molecules[mid]) for mid in mol_ids]

    totals = [total_quantity(state, per_index_quantity) for state in timeline.states]
    assert all(total == totals[0] for total in totals)


def test_integration_raising_kA_shifts_the_achieved_point_toward_prodA() -> None:
    """Monotone tension (Q1=B): raising route A's rate while holding B fixed
    increases the achieved prodA and decreases the achieved prodB — the
    shared-budget tradeoff reads through the shared precursor pool."""
    seed = Seed(200)
    baseline = _build(Constant(1.0), Constant(1.0)).oracle(seed, _SIM_CFG)
    raised = _build(Constant(3.0), Constant(1.0)).oracle(seed, _SIM_CFG)

    assert raised[0] > baseline[0]
    assert raised[1] < baseline[1]


def test_integration_oracle_is_seed_deterministic() -> None:
    skeleton_a = _build(Constant(1.0), Constant(1.0))
    skeleton_b = _build(Constant(1.0), Constant(1.0))
    assert skeleton_a.oracle(Seed(9)) == skeleton_b.oracle(Seed(9))


def test_sweep_conflict_frontier_traces_multiple_points() -> None:
    def build_for(kA: Constant, kB: Constant) -> Skeleton:
        return _build(kA, kB)

    points = [(1.0, 1.0), (2.0, 1.0), (3.0, 1.0)]
    frontier = sweep_conflict_frontier(build_for, Seed(300), points, _SIM_CFG)

    assert len(frontier) == 3
    prod_a_values = [p[0] for p in frontier]
    assert prod_a_values == sorted(prod_a_values)  # monotone as kA rises
