"""Verification / simulation harness (reject-sampling over real physics).

This module is a thin **bridge**: it integrates a :class:`~alienbio.suite.types.World`
forward by delegating to the EXISTING simulator (:class:`~alienbio.bio.world_simulator.WorldSimulatorImpl`)
and reads the trajectory back into a :class:`~alienbio.suite.types.Timeline` of bio
:class:`~alienbio.protocols.bio.WorldState` snapshots. It does NOT
reimplement integration — the real mass-action physics stays with the existing classes.

F007: ``world.network`` is a biology :class:`~alienbio.bio.chemistry.ChemistryImpl` (the
unified protocol model), so the simulator runs on it **directly** — the old
``from_network`` reconstruction bridge is gone. The molecule -> index ordering is the one
established by :meth:`WorldSimulatorImpl.from_chemistry` (it enumerates
``chemistry.molecules.keys()``); that same order is derived here to load initial
concentrations and to read results back, keeping each ``WorldState`` snapshot's real
id axes aligned with the concrete simulator indices.

Only **constant mass-action rates** are supported: a reaction whose ``rate`` is a callable (a
formula rate law) raises :class:`ValueError` rather than being silently downgraded. The
integrator is deterministic, so :func:`simulate` is a pure function of ``(world, sim_cfg)``;
``seed`` is threaded only for stochastic perturbations / predicates.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Optional

import numpy as np

from ..bio.compartment_tree import CompartmentTreeImpl
from ..bio.world_simulator import WorldSimulatorImpl
from ..bio.world_state import WorldStateImpl
from .dist import Seed
from .pressure import EnvironmentalPressure
from .types import NodeId, Timeline, World


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
    baseline: Timeline
    perturbed: Timeline


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
    pressure: Optional[EnvironmentalPressure] = None,
) -> Timeline:
    """Integrate ``world`` forward with the real simulator and return a Timeline.

    Deterministic: identical ``(world, sim_cfg)`` yield an identical :class:`Timeline`.
    ``seed`` is accepted for signature symmetry with :func:`verify` (stochastic
    perturbations / predicates); the baseline integration ignores it unless a
    stochastic ``pressure`` (``jitter > 0``) is supplied.

    ``pressure`` (M32.4) is an optional, **removable** environmental-pressure
    perturbation. When ``None`` the integration is byte-identical to the
    unperturbed baseline. When supplied, the natural trajectory is computed
    exactly as before and a displacement overlay ``exp(coef * p_t)`` is applied
    to the sampled states; the overlay relaxes toward zero after the pressure's
    ``remove_at`` step, so the reported state recovers toward the unperturbed
    trajectory (see :mod:`alienbio.suite.pressure`).

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

    # 1. The world already carries a concrete Chemistry (unified protocol model).
    chem = world.network

    # 2. Build the concrete compartment tree + NodeId -> int map + ordered
    #    real compartment-id axis (index i labels the i-th flat-array compartment).
    tree, comp_to_int = _build_tree(world)
    n_comp = tree.num_compartments
    int_to_comp = {v: k for k, v in comp_to_int.items()}
    comp_axis: tuple[NodeId, ...] = tuple(int_to_comp[i] for i in range(n_comp))

    # 3. Create the simulator. Derive the SAME molecule ordering from_chemistry
    #    uses (it enumerates chemistry.molecules.keys()).
    sim = WorldSimulatorImpl.from_chemistry(chem, tree, dt=sim_cfg.dt)
    mol_ids: list[NodeId] = list(chem.molecules.keys())
    mol_to_int = {name: i for i, name in enumerate(mol_ids)}
    num_molecules = sim.num_molecules

    # 4. Load initial concentrations positionally via the two index maps.
    #    Build the state *self-describing* (real id axes) so every ``run`` history
    #    copy surfaces real compartment/molecule ids without fabrication.
    state = WorldStateImpl(
        tree=tree,
        num_molecules=num_molecules,
        compartment_ids=list(comp_axis),
        molecule_ids=list(mol_ids),
    )
    for comp_id in world.initial.compartments:
        comp_int = comp_to_int[comp_id]
        for species_id in world.initial.species:
            mol_int = mol_to_int[species_id]
            state.set(comp_int, mol_int, world.initial.get(comp_id, species_id))

    # 5. Integrate with the real physics. ``run`` returns independent copies
    #    (WorldSimulatorImpl.run copies at each sample), and each copy carries the
    #    real id axes set above — so the history IS the sequence of self-describing
    #    WorldState snapshots (concentrations + multiplicity + real ids), with no
    #    fabricated axes and no lossy re-materialization.
    history = sim.run(state, sim_cfg.steps, sim_cfg.sample_every)

    # 6. Sampled step indices mirror WorldSimulatorImpl.run: every ``sample_every``
    #    step plus the final state at step ``steps``.
    sampled_steps = [i for i in range(sim_cfg.steps) if i % sim_cfg.sample_every == 0]
    sampled_steps.append(sim_cfg.steps)
    times = tuple(float(s * sim_cfg.dt) for s in sampled_steps)

    states: list[WorldStateImpl] = list(history)

    # 7. M32.4 removable environmental pressure: apply the displacement overlay
    #    on top of the (unchanged) natural trajectory. Absent pressure leaves
    #    ``states`` untouched, so the timeline is byte-identical to the baseline.
    if pressure is not None:
        p_traj = pressure.overlay(sim_cfg.steps, seed)
        scaled: list[WorldStateImpl] = []
        for step, ws in zip(sampled_steps, states):
            factor = math.exp(pressure.coef * float(p_traj[step]))
            ws_scaled = ws.copy()
            ws_scaled.from_array(np.asarray(ws.as_array(), dtype=np.float64) * factor)
            scaled.append(ws_scaled)
        states = scaled

    return Timeline(times=times, states=tuple(states))


def verify(
    world: World,
    perturbation: Callable[[World], World],
    predicate: Callable[[Timeline, Timeline], bool],
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
