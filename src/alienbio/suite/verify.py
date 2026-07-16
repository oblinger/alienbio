"""Verification / simulation harness (reject-sampling over real physics).

This module is a thin **bridge**: it integrates a neutral :class:`~alienbio.suite.types.World`
forward by delegating to the EXISTING simulator (:class:`~alienbio.bio.world_simulator.WorldSimulatorImpl`)
and reads the trajectory back into a neutral :class:`~alienbio.suite.types.Trace`. It does NOT
reimplement integration — the real mass-action physics stays with the existing classes.

The molecule -> index ordering is the one established by
:meth:`WorldSimulatorImpl.from_chemistry`: it enumerates ``chemistry.molecules.keys()``. Since
:func:`~alienbio.suite.adapters.from_network` keys the reconstructed molecules by the neutral
species NodeId in ``network.species`` iteration order, that same order is derived here to load
initial concentrations and to read results back — keeping the neutral axes aligned with the
concrete simulator indices.

Only **constant mass-action rates** are supported: a reaction whose ``rate`` is a callable (a
formula rate law) raises :class:`ValueError` rather than being silently downgraded. The
integrator is deterministic, so :func:`simulate` is a pure function of ``(world, sim_cfg)``;
``seed`` is threaded only for stochastic perturbations / predicates.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np

from ..bio.compartment_tree import CompartmentTreeImpl
from ..bio.world_simulator import WorldSimulatorImpl
from ..bio.world_state import WorldStateImpl
from .adapters import from_network
from .dist import Seed
from .types import NodeId, StateVector, Trace, World


@dataclass(frozen=True)
class SimConfig:
    """Integration parameters for :func:`simulate`."""

    dt: float = 0.1
    steps: int = 200
    sample_every: int = 10


@dataclass(frozen=True)
class VerifyResult:
    """The outcome of a :func:`verify` reject-sampling trial."""

    passed: bool          # predicate(baseline, perturbed) result
    discard: bool         # == not passed  (the reject-sampling signal)
    baseline: Trace
    perturbed: Trace


def _build_tree(world: World) -> tuple[CompartmentTreeImpl, dict[NodeId, int]]:
    """Build a concrete compartment tree from ``world.topology``.

    Returns the tree plus a ``compartment NodeId -> CompartmentId(int)`` map. The
    root (``parent is None``) becomes id 0; the rest are added in topological
    order (a parent is always added before its children).
    """
    comps = world.topology.compartments
    roots = [c for c in comps if c.parent is None]
    if len(roots) != 1:
        raise ValueError(
            f"verify requires exactly one root compartment (parent=None); "
            f"found {len(roots)}"
        )

    tree = CompartmentTreeImpl()
    comp_to_int: dict[NodeId, int] = {}
    root = roots[0]
    comp_to_int[root.id] = tree.add_root(root.id)

    remaining = [c for c in comps if c.parent is not None]
    while remaining:
        still = []
        progressed = False
        for c in remaining:
            if c.parent in comp_to_int:
                comp_to_int[c.id] = tree.add_child(comp_to_int[c.parent], c.id)
                progressed = True
            else:
                still.append(c)
        if not progressed:
            raise ValueError(
                "verify: compartment topology is not a tree rooted at the "
                "parent=None node (unreachable or cyclic compartments)"
            )
        remaining = still

    return tree, comp_to_int


def simulate(
    world: World,
    sim_cfg: SimConfig = SimConfig(),
    seed: Seed = Seed(0),
) -> Trace:
    """Integrate ``world`` forward with the real simulator and return a neutral Trace.

    Deterministic: identical ``(world, sim_cfg)`` yield an identical :class:`Trace`.
    ``seed`` is accepted for signature symmetry with :func:`verify` (stochastic
    perturbations / predicates) but the baseline integration ignores it.

    Raises:
        ValueError: if any reaction carries a callable (formula) rate rather than a
            constant mass-action rate constant.
    """
    # Constant rates only: reject callable rate laws loudly (the ID-based world
    # simulator would otherwise silently downgrade them to 1.0).
    for rid, rxn in world.network.reactions.items():
        if not isinstance(rxn.rate, (int, float)):
            raise ValueError(
                f"verify supports constant mass-action rates; callable rate on "
                f"reaction {rid!r}"
            )

    # 1. Reconstruct a concrete Chemistry from the neutral network.
    chem = from_network(world.network)

    # 2. Build the concrete compartment tree + NodeId -> int map.
    tree, comp_to_int = _build_tree(world)

    # 3. Create the simulator. Derive the SAME molecule ordering from_chemistry
    #    uses (it enumerates chemistry.molecules.keys()).
    sim = WorldSimulatorImpl.from_chemistry(chem, tree, dt=sim_cfg.dt)
    mol_ids: list[NodeId] = list(chem.molecules.keys())
    mol_to_int = {name: i for i, name in enumerate(mol_ids)}
    num_molecules = sim.num_molecules

    # 4. Load initial concentrations positionally via the two index maps.
    state = WorldStateImpl(tree=tree, num_molecules=num_molecules)
    for comp_id in world.initial.compartments:
        comp_int = comp_to_int[comp_id]
        for species_id in world.initial.species:
            mol_int = mol_to_int[species_id]
            state.set(comp_int, mol_int, world.initial.get(comp_id, species_id))

    # 5. Integrate with the real physics.
    history = sim.run(state, sim_cfg.steps, sim_cfg.sample_every)

    # 6. Map back to a neutral Trace, reusing the index maps for REAL NodeIds.
    n_comp = tree.num_compartments
    int_to_comp = {v: k for k, v in comp_to_int.items()}
    comp_axis: tuple[NodeId, ...] = tuple(int_to_comp[i] for i in range(n_comp))
    species_axis: tuple[NodeId, ...] = tuple(mol_ids)

    # Sampled step indices mirror WorldSimulatorImpl.run: every ``sample_every``
    # step plus the final state at step ``steps``.
    sampled_steps = [i for i in range(sim_cfg.steps) if i % sim_cfg.sample_every == 0]
    sampled_steps.append(sim_cfg.steps)
    times = tuple(float(s * sim_cfg.dt) for s in sampled_steps)

    states: list[StateVector] = []
    for ws in history:
        data = np.array(
            [
                [ws.get(i, j) for j in range(num_molecules)]
                for i in range(n_comp)
            ],
            dtype=np.float64,
        )
        states.append(
            StateVector(data=data, compartments=comp_axis, species=species_axis)
        )

    return Trace(times=times, states=tuple(states))


def verify(
    world: World,
    perturbation: Callable[[World], World],
    predicate: Callable[[Trace, Trace], bool],
    sim_cfg: SimConfig = SimConfig(),
    seed: Seed = Seed(0),
) -> VerifyResult:
    """Simulate ``world`` and its perturbation, then score with an opaque predicate.

    ``perturbation`` and ``predicate`` are opaque callables — only ever called,
    never inspected. ``predicate(baseline, perturbed)`` returns whether to keep the
    sample; ``discard`` is its negation (the reject-sampling signal).
    """
    baseline = simulate(world, sim_cfg, seed)
    perturbed = simulate(perturbation(world), sim_cfg, seed)
    passed = predicate(baseline, perturbed)
    return VerifyResult(
        passed=passed,
        discard=not passed,
        baseline=baseline,
        perturbed=perturbed,
    )
