"""Verification / simulation harness (reject-sampling over real physics).

This module is a thin **bridge**: it integrates a biology
:class:`~alienbio.bio.world.WorldImpl` forward by delegating to the EXISTING simulator
(:class:`~alienbio.bio.world_simulator.WorldSimulatorImpl`) and reads the trajectory back
into a :class:`~alienbio.suite.types.Timeline` of bio
:class:`~alienbio.protocols.bio.WorldState` snapshots. It does NOT
reimplement integration — the real mass-action physics stays with the existing classes.

F007 coord-PR2: the world is the unified biology :class:`~alienbio.bio.world.WorldImpl`.
It already carries a concrete :class:`~alienbio.bio.chemistry.ChemistryImpl` and a derived,
self-describing initial :class:`~alienbio.bio.world_state.WorldStateImpl` sitting on a
concrete :class:`~alienbio.bio.compartment_tree.CompartmentTreeImpl` — so this bridge just
copies that initial state and integrates it. There is no tree reconstruction and no
positional reload: ``WorldImpl`` builds ``initial_state`` on the same molecule ordering
(``chemistry.molecules.keys()``) that :meth:`WorldSimulatorImpl.from_chemistry` uses, so
the snapshot id axes are already aligned with the simulator indices.

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

from ..bio.world import WorldImpl
from ..bio.world_simulator import WorldSimulatorImpl
from ..bio.world_state import WorldStateImpl
from .dist import Seed
from .pressure import EnvironmentalPressure
from .types import Timeline


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


def simulate(
    world: WorldImpl,
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
    chem = world.chemistry
    for rid, rxn in chem.reactions.items():
        if not isinstance(rxn.rate, (int, float)):
            raise ValueError(
                f"verify supports constant mass-action rates; callable rate on "
                f"reaction {rid!r}"
            )

    # 1. The world already carries a concrete Chemistry and a derived,
    #    self-describing initial WorldState on a concrete CompartmentTree. Copy the
    #    initial state (leave the world's pristine) and reuse its tree — no tree
    #    reconstruction, no positional concentration reload.
    state = world.initial_state.copy()
    tree = state.tree

    # 2. Create the simulator on that same tree. WorldImpl built ``initial_state``
    #    with the molecule order from_chemistry uses (chemistry.molecules.keys()),
    #    so the state indices already align with the simulator's. ``flow_objs``
    #    is the int-resolved, simulator-ready form of ``world.flows`` (F016/S3);
    #    it defaults to empty, so a non-transport world is byte-identical.
    sim = WorldSimulatorImpl.from_chemistry(
        chem, tree, flows=list(world.flow_objs), dt=sim_cfg.dt
    )

    # 3. Integrate with the real physics. ``run`` returns independent copies
    #    (WorldSimulatorImpl.run copies at each sample), and each copy carries the
    #    real id axes from ``initial_state`` — so the history IS the sequence of
    #    self-describing WorldState snapshots (concentrations + multiplicity + real
    #    ids), with no fabricated axes and no lossy re-materialization.
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
    world: WorldImpl,
    perturbation: Callable[[WorldImpl], WorldImpl],
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
