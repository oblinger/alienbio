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

A reaction runs mass action at its numeric ``rate`` or, when it carries one, its compiled
``rate_law`` (M47.10; a callable ``rate`` is refused by ``ReactionImpl`` itself). The
integrator is deterministic, so :func:`simulate` is a pure function of ``(world, sim_cfg)``;
``seed`` is threaded only for stochastic perturbations / predicates.
"""

from __future__ import annotations

import math
import numbers
from dataclasses import dataclass
from typing import Any, Callable, Optional, Sequence

import numpy as np

from ..bio.flow import TransportFlux
from ..bio.population import CountFlow, PerCapitaDeath, PerCapitaGrowth
from ..bio.world import WorldImpl
from ..bio.world_simulator import WorldSimulatorImpl
from ..bio.world_state import WorldStateImpl
from .dist import Seed
from .pressure import EnvironmentalPressure
from .types import Timeline


@dataclass(frozen=True)
class SimConfig:
    """Integration parameters for :func:`simulate`: ``dt`` a positive finite
    step, ``steps`` and ``sample_every`` positive ints (T088 verify 1:
    ``sample_every = 0`` raised a bare ``ZeroDivisionError`` from
    :func:`simulate`, a negative ``steps`` or non-positive ``dt`` reached the
    simulator as given). A bad field refuses here, naming it."""

    dt: float = 0.1
    steps: int = 200
    sample_every: int = 10

    def __post_init__(self) -> None:
        if isinstance(self.dt, bool) or not isinstance(self.dt, numbers.Real) or not (math.isfinite(self.dt) and self.dt > 0):
            raise ValueError(f"SimConfig.dt must be a positive finite number, got {self.dt!r}")
        for name in ("steps", "sample_every"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, numbers.Integral) or value < 1:
                raise ValueError(f"SimConfig.{name} must be a positive int, got {value!r}")


#: Per-term weights of :func:`step_work`, in work units of about 0.05 µs of
#: CPU each (T091 BA: the AY count charged every term one unit, and the terms
#: cost from 0.06 µs — a pool copied — to 137 µs — a death law whose carry
#: walks every molecule). Each weight is the measured CPU of one term
#: divided by the unit; over 41 measured rows of 33 shapes (T091 BA's twenty
#: and BC's thirteen, with variants) the fitted cost is 0.024-0.070 µs per
#: unit:
#:
#: - ``W_MOLECULE`` — one pool in one compartment: the state copy and the
#:   subnormal flush (0.05 µs).
#: - ``W_COMPARTMENT_STEP`` — one compartment, every step, whatever the
#:   chemistry holds: the simulator's per-compartment loop and the
#:   multiplicity, volume and id lists ``WorldStateImpl.copy`` copies (0.07
#:   µs; T091 BC: a world of 20 000 empty compartments counted 1 unit a step
#:   and cost 1.4 ms). A sample (``sample_every``) copies the state once more;
#:   that copy is never dearer than the step's own, so it is not charged
#:   apart (one molecule x 20 000 compartments sampled every step reads 0.05
#:   µs per unit).
#: - ``W_COMPARTMENT`` — the reaction pass's setup in one compartment (the
#:   active-reaction list and the rationing dicts, 1.2 µs); charged only when
#:   the chemistry has reactions, as ``WorldSimulatorImpl.step`` skips the
#:   pass otherwise.
#: - ``W_REACTION_TERM`` — each of a reaction's ``1 + reactants + products``
#:   in each compartment: the extent, the rationing and the writes walk the
#:   reactants and products (0.6-0.85 µs).
#: - ``W_MODULATOR`` — one modifier read by ``_modulation_factor`` in one
#:   compartment (0.15 µs active, 0.4 µs inert).
#: - ``W_RATE_LAW_NODE`` — one node of a compiled rate-law tree, evaluated by
#:   ``eval_rate`` in one compartment (0.12 µs for algebra, 0.22 µs for a
#:   modulation node).
#: - ``W_FLOW`` + ``W_FLOW_SPECIES`` per species — one transport flux: its
#:   demand, its ration and its per-species writes (2.4 µs for a flux that
#:   moves amount, 0.85 µs for one idle at a zero gradient; weighted between).
#: - ``W_POPULATION_LAW`` — one population law's contribution and ration
#:   (2.2 µs).
#: - ``W_POPULATION_CARRY`` — per law per molecule, once any law moves
#:   content (a death that releases, a growth that draws, a count flow):
#:   ``apply_population_laws`` then walks every molecule for every carry
#:   (0.26-0.47 µs per molecule).
#: - ``W_POPULATION_KEY`` — one molecule of a compartment that count flows
#:   carry movers INTO from elsewhere: ``apply_population_laws`` accounts
#:   every molecule of every such destination — reads it, snaps it and
#:   writes it back (1.3 µs a key; T091 BC: 40 flows from one origin into 40
#:   destinations x 5 000 molecules cost 0.2 µs per unit without it). Charged
#:   once per distinct destination, however many flows reach it.
W_MOLECULE = 1
W_COMPARTMENT_STEP = 2
W_COMPARTMENT = 24
W_REACTION_TERM = 13
W_MODULATOR = 6
W_RATE_LAW_NODE = 3
W_FLOW = 14
W_FLOW_SPECIES = 20
W_POPULATION_LAW = 44
W_POPULATION_CARRY = 7
W_POPULATION_KEY = 30

#: Integration work a spec-built world may cost inside an Expr head
#: (``verify``, ``predict_q``), summed over every simulation the head runs
#: (both heads run two: the base world and its perturbation). One step's
#: work is :func:`step_work`, the weighted sum of what a simulator step
#: loops over (see the ``W_*`` weights). The cap is set so a head at the cap
#: costs about 3 s of CPU on the slowest measured shape per unit (T091 BA:
#: 2.8 s for 2 000 active flows), and stays far above the largest work in
#: use (``catalog/``, ``tests/`` and the scripted examples surveyed: 133 600,
#: the kinetics ``predict_q``, 299x under; AUP uses neither head). A
#: simulation runs outside the evaluation clock: before T091 AY the count
#: left out compartments and fan-in, so a 575-byte spec (1 000 reactions x
#: 1 000 compartments, 20 steps) held a load 72 s of CPU at 3 % of the cap,
#: and before T091 BA a death law counted one unit while walking every
#: molecule, so a 689-byte spec held a load 27 s at 5 % of it.
MAX_EXPR_SIM_WORK = 40_000_000


def _rate_law_nodes(node: Any) -> int:
    """Node count of a compiled rate-law tree (iterative: a spec may build
    a deep one)."""
    count = 0
    stack = [node]
    while stack:
        item = stack.pop()
        count += 1
        if isinstance(item, tuple) and item and item[0] not in ("const", "species", "mod"):
            stack.extend(child for child in item[1:] if isinstance(child, tuple))
    return count


def _moves_content(law: Any) -> bool:
    """True when ``law`` makes ``apply_population_laws`` account amounts:
    a death that releases, a growth that draws its resource, a count flow."""
    if isinstance(law, PerCapitaDeath):
        return law.release_compartment is not None and law.release_resource is not None and law.release_stoich > 0.0
    if isinstance(law, PerCapitaGrowth):
        return law.stoich > 0.0
    return isinstance(law, CountFlow)


def work_terms(world: WorldImpl) -> list[tuple[str, int, int]]:
    """The terms of :func:`step_work` as ``(what, count, weight)``: one
    step's work is ``Σ count x weight``."""
    chem = world.chemistry
    compartments = max(1, len(world.compartments))
    molecules = len(chem.molecules)
    reaction_terms = modulators = law_nodes = 0
    for reaction in chem.reactions.values():
        reaction_terms += 1 + len(reaction.reactants) + len(reaction.products)
        modulators += len(reaction.modifiers)
        if reaction.rate_law is not None:
            law_nodes += _rate_law_nodes(reaction.rate_law)
    flows = list(world.flow_objs)
    laws = list(world.population_law_objs)
    carries = len(laws) * molecules if any(_moves_content(law) for law in laws) else 0
    destinations = {law.dest for law in laws if isinstance(law, CountFlow) and law.dest != law.origin}
    return [
        ("compartments", compartments, W_COMPARTMENT_STEP),
        ("molecules x compartments", molecules * compartments, W_MOLECULE),
        ("compartments with a reaction pass", compartments if chem.reactions else 0, W_COMPARTMENT),
        ("reaction terms (one, each reactant, each product) x compartments", reaction_terms * compartments, W_REACTION_TERM),
        ("modulators x compartments", modulators * compartments, W_MODULATOR),
        ("rate-law nodes x compartments", law_nodes * compartments, W_RATE_LAW_NODE),
        ("flows", len(flows), W_FLOW),
        ("flow species", sum(len(f.stoichiometry) for f in flows if isinstance(f, TransportFlux)), W_FLOW_SPECIES),
        ("population laws", len(laws), W_POPULATION_LAW),
        ("population carries (laws x molecules)", carries, W_POPULATION_CARRY),
        ("count-flow destination keys (destinations x molecules)", len(destinations) * molecules, W_POPULATION_KEY),
    ]


def step_work(world: WorldImpl) -> int:
    """The work one simulator step does on ``world``: the weighted sum of
    :func:`work_terms` (see :data:`MAX_EXPR_SIM_WORK`)."""
    return sum(count * weight for _, count, weight in work_terms(world))


def sim_work(world: WorldImpl, cfg: SimConfig) -> int:
    """The integration work of one simulation of ``world`` under ``cfg``."""
    return int(cfg.steps) * max(1, step_work(world))


def check_sim_work(head: str, worlds: Sequence[Any], cfg: Any) -> None:
    """Refuse simulations of ``worlds`` under ``cfg`` whose summed work is past
    :data:`MAX_EXPR_SIM_WORK`, naming the head, the work per simulation, the
    weighted terms of the world that carries the most, and the cap: the
    listed factors multiply and sum to the reported total. Anything that is
    not a world, or a ``cfg`` that is not a ``SimConfig``, is skipped: the
    simulator's own validation owns that verdict."""
    if not isinstance(cfg, SimConfig):
        return
    real = [w for w in worlds if isinstance(w, WorldImpl)]
    if not real:
        return
    per_world = [sim_work(w, cfg) for w in real]
    work = sum(per_world)
    if work > MAX_EXPR_SIM_WORK:
        largest = max(range(len(real)), key=lambda i: per_world[i])
        terms = [t for t in work_terms(real[largest]) if t[1]]
        sims = " + ".join(f"{cfg.steps} x {max(1, step_work(w))}" for w in real)
        detail = " + ".join(f"{count} {what} x {weight}" for what, count, weight in terms) or "1 (an empty world)"
        raise ValueError(
            f"{head}: {len(real)} simulation(s) would cost {work} units ({sims} steps x work per step), "
            f"past the cap MAX_EXPR_SIM_WORK={MAX_EXPR_SIM_WORK}; simulation {largest + 1}'s world does "
            f"{max(1, step_work(real[largest]))} per step = {detail} — "
            "a simulation runs outside the evaluation clock; use fewer steps (a larger dt) or a smaller world"
        )


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
    """
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
    #    ``population_law_objs`` is the same for ``world.population_laws`` (F017).
    #    Both default to empty, so a non-transport/non-population world is
    #    byte-identical.
    sim = WorldSimulatorImpl.from_chemistry(
        world.chemistry,
        tree,
        flows=list(world.flow_objs),
        dt=sim_cfg.dt,
        population_laws=list(world.population_law_objs),
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
