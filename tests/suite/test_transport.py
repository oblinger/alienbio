"""Tests for F016 (skeleton decision S3 / coverage gap G3) — cross-compartment
transport: the ``bio.flow.TransportFlux`` amount-conserving flux primitive,
``suite.blocks.TransportBlock`` / ``SpatialLatticeBlock``, and the threading
that keeps flux alive across ``ScenarioRunner``'s per-turn ``WorldImpl`` rebuild.

Three tiers: (1) the engine core — a hand-built two-compartment world
exercising ``TransportFlux`` directly (the acceptance gate: amount invariant
across DIFFERING volumes, gradient relaxes toward equal concentration,
rationing never drives a pool negative); (2) the two skeleton blocks,
materialized/validated/simulated; (3) one end-to-end ``suite.runner.run``
regression guard confirming flux survives ``_world_from_state``'s per-turn
rebuild (F016's key integration risk).
"""

from __future__ import annotations

import dataclasses

import pytest

from alienbio.bio.compartment_tree import CompartmentTreeImpl
from alienbio.bio.conservation import total_quantity
from alienbio.bio.flow import TransportFlux
from alienbio.bio.world import WorldImpl
from alienbio.bio.world_simulator import WorldSimulatorImpl
from alienbio.bio.world_state import WorldStateImpl
from alienbio.suite.agent import Commit, ScriptedAgent, Wait
from alienbio.suite.blocks import SourceBlock, SpatialLatticeBlock, TransportBlock
from alienbio.suite.dist import Constant, Seed
from alienbio.suite.runner import run
from alienbio.suite.skeleton import PoolBinding, Role, Skeleton, SkeletonBlock
from alienbio.suite.types import (
    Answer,
    CarveResult,
    Motif,
    OutcomeObjective,
    Question,
    TaskInstance,
)
from alienbio.suite.verify import SimConfig, simulate

_SIM_CFG = SimConfig(dt=0.05, steps=200, sample_every=50)


# ═══════════════════════════════════════════════════════════════════════════
# Engine core (the acceptance gate) — a hand-built TransportFlux, no skeleton
# ═══════════════════════════════════════════════════════════════════════════


def _two_compartment_sim(
    src_volume: float, dest_volume: float, rate_constant: float, dt: float = 0.05
) -> tuple[CompartmentTreeImpl, WorldSimulatorImpl, WorldStateImpl, int, int]:
    tree = CompartmentTreeImpl()
    a = tree.add_root("a")
    b = tree.add_child(a, "b")
    state = WorldStateImpl(
        tree=tree, num_molecules=1, compartment_ids=["a", "b"], molecule_ids=["x"]
    )
    state.set_volume(a, src_volume)
    state.set_volume(b, dest_volume)
    flux = TransportFlux(
        origin=a, dest=b, stoichiometry={0: 1.0}, driver_molecule=0, rate_constant=rate_constant
    )
    sim = WorldSimulatorImpl(tree=tree, reactions=[], flows=[flux], num_molecules=1, dt=dt)
    return tree, sim, state, a, b


def test_transport_flux_conserves_amount_across_differing_volumes() -> None:
    _, sim, state, a, b = _two_compartment_sim(src_volume=1.0, dest_volume=3.0, rate_constant=0.5)
    state.set(a, 0, 10.0)
    state.set(b, 0, 0.0)

    history = sim.run(state, steps=200, sample_every=10)
    per_index = [{"n": 1.0}]
    totals = [total_quantity(s, per_index)["n"] for s in history]

    assert totals[0] == pytest.approx(10.0)
    for total in totals:
        assert total == pytest.approx(totals[0], abs=1e-9)


def test_transport_flux_gradient_relaxes_toward_equal_concentration() -> None:
    _, sim, state, a, b = _two_compartment_sim(src_volume=1.0, dest_volume=3.0, rate_constant=0.5)
    state.set(a, 0, 10.0)
    state.set(b, 0, 0.0)

    history = sim.run(state, steps=200, sample_every=10)
    final = history[-1]
    # equilibrium: conc_a == conc_b == c, and 1*c + 3*c == 10 => c == 2.5
    assert final.get(a, 0) == pytest.approx(2.5, abs=0.05)
    assert final.get(b, 0) == pytest.approx(2.5, abs=0.05)
    # monotone approach: the gap never widens step to step
    gaps = [abs(s.get(a, 0) - s.get(b, 0)) for s in history]
    assert all(g2 <= g1 + 1e-9 for g1, g2 in zip(gaps, gaps[1:]))


def test_transport_flux_rations_against_available_amount_never_negative() -> None:
    """A rate_constant far too large to honor in one step must clamp, not overshoot."""
    _, sim, state, a, b = _two_compartment_sim(
        src_volume=1.0, dest_volume=1.0, rate_constant=1000.0, dt=1.0
    )
    state.set(a, 0, 1.0)
    state.set(b, 0, 0.0)

    new_state = sim.step(state)
    assert new_state.get(a, 0) == pytest.approx(0.0, abs=1e-9)
    assert new_state.get(a, 0) >= 0.0
    assert new_state.get(b, 0) == pytest.approx(1.0, abs=1e-9)


def test_transport_flux_first_order_law_moves_even_at_equal_concentration() -> None:
    """The gradient law would floor to 0 at equal concentration; first_order doesn't."""
    tree = CompartmentTreeImpl()
    a = tree.add_root("a")
    b = tree.add_child(a, "b")
    state = WorldStateImpl(
        tree=tree, num_molecules=1, compartment_ids=["a", "b"], molecule_ids=["x"]
    )
    state.set(a, 0, 5.0)
    state.set(b, 0, 5.0)

    flux = TransportFlux(
        origin=a,
        dest=b,
        stoichiometry={0: 1.0},
        driver_molecule=0,
        rate_constant=0.1,
        rate_law="first_order",
    )
    sim = WorldSimulatorImpl(tree=tree, reactions=[], flows=[flux], num_molecules=1, dt=1.0)
    new_state = sim.step(state)
    assert new_state.get(a, 0) == pytest.approx(4.5)
    assert new_state.get(b, 0) == pytest.approx(5.5)


def test_transport_flux_rejects_unknown_rate_law() -> None:
    with pytest.raises(ValueError):
        TransportFlux(origin=0, dest=1, stoichiometry={0: 1.0}, driver_molecule=0, rate_law="bogus")


# ═══════════════════════════════════════════════════════════════════════════
# TransportBlock — materialize / validate / simulate / provenance
# ═══════════════════════════════════════════════════════════════════════════


def _build_transport_skeleton(rate: float = 2.0) -> tuple[Skeleton, WorldImpl, str]:
    """Source (rate=0, inert — only here to give the pool an OUT port for
    ``validate()``) pool-bound to a ``TransportBlock`` moving the shared
    species from ``cellA`` (volume 1) to ``cellB`` (volume 3)."""
    source = SourceBlock.make("source", container="cellA", rate=Constant(0.0))
    transport = TransportBlock.make(
        "xport",
        port="pool",
        container="cellA",
        dest_container="cellB",
        rate=Constant(rate),
        rate_law="gradient",
        src_volume=1.0,
        dest_volume=3.0,
    )
    root = SkeletonBlock(
        name="root",
        role=Role.TRANSPORT,
        children=(source, transport),
        pool_bindings=(PoolBinding("source.out", "xport.pool"),),
    )
    skeleton = Skeleton(root=root)
    world = skeleton.materialize(Seed(1))
    mol_name = next(iter(world.chemistry.molecules))
    return skeleton, world, mol_name


def _stamp_source_concentration(world: WorldImpl, mol_name: str, value: float) -> WorldImpl:
    """Rebuild ``world`` with ``cellA`` stamped to ``value`` — the same
    replace-and-reconstruct idiom ``suite.runner._world_from_state`` uses,
    exercised here to also prove ``flows`` round-trips through a fresh
    ``WorldImpl`` construction."""
    stamped = tuple(
        dataclasses.replace(c, concentrations={mol_name: value}) if c.id == "cellA" else c
        for c in world.compartments
    )
    return WorldImpl(world.chemistry, stamped, flows=world.flows)


def test_transport_block_materializes_and_validates() -> None:
    skeleton, _world, _mol = _build_transport_skeleton()
    assert skeleton.validate() is None


def test_transport_block_records_provenance_with_a_flow_id() -> None:
    skeleton, _world, _mol = _build_transport_skeleton()
    xport = next(c for c in skeleton.root.children if c.name == "xport")
    assert len(xport.provenance) == 1
    prov = xport.provenance[0]
    assert prov.container_id == "cellA"
    assert prov.flow_id  # non-empty: this block's causal handle is a flow, not a reaction
    assert prov.reaction_id == ""


def test_transport_block_moves_species_across_the_boundary_conservingly() -> None:
    _skeleton, base_world, mol_name = _build_transport_skeleton(rate=2.0)
    world = _stamp_source_concentration(base_world, mol_name, 5.0)
    timeline = simulate(world, _SIM_CFG)

    mol_ids = timeline.states[-1].molecule_ids
    assert mol_ids is not None
    per_index = [{"n": 1.0} for _ in mol_ids]
    totals = [total_quantity(s, per_index)["n"] for s in timeline.states]
    assert all(total == pytest.approx(totals[0], abs=1e-6) for total in totals)

    final = timeline.states[-1]
    assert final.compartment_ids is not None
    ci_dest = final.compartment_ids.index("cellB")
    mj = final.molecule_ids.index(mol_name)  # type: ignore[union-attr]
    assert final.get(ci_dest, mj) > 0.0


def test_transport_block_is_deterministic_for_a_given_seed() -> None:
    _s1, base1, mol1 = _build_transport_skeleton()
    _s2, base2, mol2 = _build_transport_skeleton()
    assert mol1 == mol2
    w1 = _stamp_source_concentration(base1, mol1, 5.0)
    w2 = _stamp_source_concentration(base2, mol2, 5.0)
    t1 = simulate(w1, _SIM_CFG)
    t2 = simulate(w2, _SIM_CFG)
    for a, b in zip(t1.states, t2.states):
        assert a.as_array().tolist() == b.as_array().tolist()


# ═══════════════════════════════════════════════════════════════════════════
# SpatialLatticeBlock — a thin K-compartment diffusive chain
# ═══════════════════════════════════════════════════════════════════════════


def test_spatial_lattice_stamps_k_compartments_and_wires_neighbor_edges() -> None:
    lattice = SpatialLatticeBlock.make("lattice", k=4, molecule="x", diffusion=Constant(0.3))
    root = SkeletonBlock(name="root", role=Role.TRANSPORT, children=(lattice,))
    skeleton = Skeleton(root=root)
    world = skeleton.materialize(Seed(2))

    assert len(world.compartments) == 4
    assert len(world.flows) == 2 * 3  # 3 neighbor edges, each a reversed pair
    assert skeleton.validate() is None


def test_spatial_lattice_gradient_relaxes_toward_flat_while_conserving_amount() -> None:
    lattice = SpatialLatticeBlock.make(
        "lattice", k=4, molecule="x", diffusion=Constant(0.3), initial={0: 10.0}
    )
    root = SkeletonBlock(name="root", role=Role.TRANSPORT, children=(lattice,))
    world = Skeleton(root=root).materialize(Seed(2))

    timeline = simulate(world, SimConfig(dt=0.05, steps=400, sample_every=50))
    mol_name = next(iter(world.chemistry.molecules))
    mol_ids = timeline.states[-1].molecule_ids
    assert mol_ids is not None
    per_index = [{"n": 1.0} for _ in mol_ids]
    totals = [total_quantity(s, per_index)["n"] for s in timeline.states]
    assert all(total == pytest.approx(totals[0], abs=1e-6) for total in totals)

    final = timeline.states[-1]
    mj = final.molecule_ids.index(mol_name)  # type: ignore[union-attr]
    concs = [final.get(ci, mj) for ci in range(final.num_compartments)]
    assert max(concs) - min(concs) < 1.0  # started at a spread of 10.0


# ═══════════════════════════════════════════════════════════════════════════
# End-to-end: transport survives suite.runner.run's per-turn WorldImpl rebuild
# ═══════════════════════════════════════════════════════════════════════════


def test_transport_persists_across_scenario_runner_turns() -> None:
    """Regression guard for the ``_world_from_state`` flows-carry-forward fix:
    if ``flows`` weren't threaded through the per-turn rebuild, transport
    would silently stop after turn 0 and ``cellB`` would plateau."""
    _skeleton, base_world, mol_name = _build_transport_skeleton(rate=0.3)
    world = _stamp_source_concentration(base_world, mol_name, 5.0)

    task = TaskInstance(
        archetype="transport_probe",
        world="world0",
        skeleton=CarveResult(motif=Motif(roles=(), edges=()), binding={}),
        objective=OutcomeObjective(scorer=lambda trace: 1.0, target=None),
        question=Question(structured=set(), kind="node_set"),
        setup={},
    )
    policy = (
        Wait(duration=1.0),
        Wait(duration=1.0),
        Wait(duration=1.0),
        Commit(answer=Answer(value=0.0, kind="scalar")),
    )
    agent = ScriptedAgent(policy, seed=Seed(0))
    record = run(
        world, task, agent, {}, Seed(11), sim_cfg=SimConfig(dt=0.05, steps=5, sample_every=5)
    )

    assert record.terminal_reason == "committed"
    states = record.final_timeline.states
    dest_concs = []
    for s in states:
        assert s.compartment_ids is not None and s.molecule_ids is not None
        ci = s.compartment_ids.index("cellB")
        mj = s.molecule_ids.index(mol_name)
        dest_concs.append(s.get(ci, mj))

    # Strictly increasing across every sampled point, INCLUDING the last two
    # turn boundaries — if transport had died after turn 0/1, the tail would
    # be flat instead of still climbing.
    assert all(b > a for a, b in zip(dest_concs, dest_concs[1:]))
    assert dest_concs[-1] > dest_concs[-2] > dest_concs[-3]
