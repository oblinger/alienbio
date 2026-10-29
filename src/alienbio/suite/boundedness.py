"""Opt-in boundedness (homeostasis) gate: no pool grows or collapses unbounded (F019).

This module is **additive and opt-in** — nothing in the existing generation/simulation
path imports it, so it does not change any current behavior (mirrors
:mod:`alienbio.bio.conservation`'s F012 posture: callers invoke the gate explicitly;
``Skeleton.materialize`` is untouched).

Conservation (F012) is a purely **static** algebraic property of each reaction; this
module is its **dynamic** sibling — a property of the assembled system's *trajectory*
that a static check can only necessarily bound, never sufficiently. Two layers:

- :func:`static_bounded_fate` — a cheap necessary-condition graph walk: does every pool
  produced/injected by some reaction also have a consuming reaction, sink, or dilution
  term? A pool that is only ever a product (never a reactant, anywhere) is a pure
  accumulator and a structural guarantee of divergence.
- :func:`simulate_boundedness` — because the static check is *necessary, not
  sufficient* (a pool with a genuine consumer can still diverge under nonlinear
  kinetics if inflow outpaces a saturating consumer), run the assembled world with
  :func:`alienbio.suite.verify.simulate` and classify each pool's relative growth over
  a trailing window of the horizon (Q1=A): diverging (grows by more than a factor
  ``theta``), collapsing (shrinks below the symmetric floor ``1/theta``), or bounded.

Both layers only report (:class:`PoolTrajectory`); repairing or redrawing is the
caller's responsibility. ``repair_static`` (a dilution sink per flagged pool) had no
caller in ``src/`` or AUP and was retired in T093.

:func:`check_boundedness` is the one-call convenience a generator opts into: static
layer first (cheap, explanatory), then the dynamic simulate-and-check confirmation.
Every trip (static or dynamic) is logged (log-every-heuristic).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Union, cast

from ..bio.chemistry import ChemistryImpl
from ..bio.world import WorldImpl
from .dist import Seed
from .skeleton import Skeleton
from .verify import SimConfig, simulate

if TYPE_CHECKING:
    from ..bio.world_state import WorldStateImpl

logger = logging.getLogger(__name__)

# Q1=A defaults: relative-growth-over-a-window, both tunable per call.
_DEFAULT_THETA = 10.0
_DEFAULT_WINDOW = 0.25
# Floor for treating a near-zero amount as "started at zero" (denominator guard).
_EPS = 1e-9


@dataclass(frozen=True)
class UnboundedPool:
    """A pool the static walk flags as a pure accumulator (no consuming fate)."""

    name: str
    reason: str


@dataclass(frozen=True)
class PoolTrajectory:
    """One pool's classification over the simulated trailing window.

    ``factor`` is ``amount(final) / amount(window start)`` (both floored at
    :data:`_EPS` to keep the ratio finite); ``classification`` is one of
    ``"diverging"`` / ``"collapsing"`` / ``"bounded"``.
    """

    name: str
    factor: float
    classification: str


@dataclass(frozen=True)
class BoundednessReport:
    """The combined static + dynamic verdict (:func:`check_boundedness`'s return)."""

    static_unbounded: tuple[UnboundedPool, ...] = ()
    dynamic: tuple[PoolTrajectory, ...] = field(default_factory=tuple)

    @property
    def diverging(self) -> tuple[PoolTrajectory, ...]:
        """Pools the dynamic pass classified as diverging."""
        return tuple(t for t in self.dynamic if t.classification == "diverging")

    @property
    def collapsing(self) -> tuple[PoolTrajectory, ...]:
        """Pools the dynamic pass classified as collapsing."""
        return tuple(t for t in self.dynamic if t.classification == "collapsing")

    @property
    def ok(self) -> bool:
        """True iff neither layer found anything unbounded."""
        return not self.static_unbounded and not self.diverging and not self.collapsing


def static_bounded_fate(chemistry: ChemistryImpl) -> list[UnboundedPool]:
    """Flag every pool produced/injected with no consuming reaction, sink, or dilution.

    A pool (molecule) qualifies as an accumulator when it appears as a **product** of
    at least one reaction but never as a **reactant** of any reaction (an internal
    consumer, or a boundary Sink/dilution, ``X -> ∅``) AND a boundary Source
    (``∅ -> X``, a reaction with no reactants) feeds it through some chain of
    reactions — the canonical sourced-only-inflow failure. A terminal product of a
    closed world (``a -> b -> c`` from a seeded ``a``, no source) is bounded by mass
    conservation and is not flagged (T088 boundedness 1). Modifiers (catalysts,
    never stoichiometrically consumed) do not count either way. Population laws
    are not read (a pool drained only by a growth law reads as an accumulator).
    Fail-visibly: names every flagged pool + the reaction(s) that produce it; logs
    every trip.
    """
    produced_by: dict[str, list[str]] = {}
    consumed: set[str] = set()
    for rxn_id, rxn in chemistry.reactions.items():
        for mol in rxn.products:
            produced_by.setdefault(mol.name, []).append(rxn_id)
        for mol in rxn.reactants:
            consumed.add(mol.name)
    # Pools a boundary source feeds, directly or downstream.
    fed: set[str] = {m.name for r in chemistry.reactions.values() if not r.reactants for m in r.products}
    grew = True
    while grew:
        grew = False
        for rxn in chemistry.reactions.values():
            if any(m.name in fed for m in rxn.reactants):
                new = {m.name for m in rxn.products} - fed
                if new:
                    fed |= new
                    grew = True

    unbounded = [
        UnboundedPool(
            name=name,
            reason=(
                f"produced by {sorted(rxns)} with no consuming reaction, sink, "
                "or dilution term"
            ),
        )
        for name, rxns in sorted(produced_by.items())
        if name not in consumed and name in fed
    ]
    for pool in unbounded:
        logger.warning("boundedness: static accumulator pool %r (%s)", pool.name, pool.reason)
    return unbounded


def _total_amount(state: "WorldStateImpl", molecule_index: int) -> float:
    """Sum of a molecule's ``amount`` (extensive count) across every compartment."""
    return sum(state.amount(c, molecule_index) for c in range(state.num_compartments))


def simulate_boundedness(
    world: WorldImpl,
    seed: Seed = Seed(0),
    *,
    theta: float = _DEFAULT_THETA,
    window: float = _DEFAULT_WINDOW,
    sim_cfg: SimConfig = SimConfig(),
) -> BoundednessReport:
    """Simulate ``world`` and classify each pool's trajectory over the trailing window.

    Runs :func:`alienbio.suite.verify.simulate` (deterministic given ``(world,
    sim_cfg)``; ``seed`` only matters if a future caller threads a stochastic
    ``pressure`` through — the baseline path here is byte-identical regardless), then
    for each molecule compares its total ``amount`` (:meth:`WorldStateImpl.amount` —
    the extensive, volume/multiplicity-aware basis) at the start of the trailing
    ``window`` fraction of the simulated time horizon to its amount at the final
    sampled state. A pool that grows by ``>= theta`` is ``"diverging"``; one that
    shrinks to ``<= 1/theta`` of a non-negligible starting amount is ``"collapsing"``
    (symmetric floor, Q1=A); otherwise ``"bounded"``. Every non-bounded trip is logged
    with its pool name and factor (log-every-heuristic).

    Returns a :class:`BoundednessReport` with ``static_unbounded`` empty (this
    function only runs the dynamic layer — see :func:`check_boundedness` for both).
    """
    timeline = simulate(world, sim_cfg, seed)
    if not timeline.states:
        raise ValueError("simulate_boundedness: timeline has no states to classify")

    states = [cast("WorldStateImpl", s) for s in timeline.states]
    mol_ids = states[-1].molecule_ids
    if mol_ids is None:
        raise ValueError(
            "simulate_boundedness requires a self-describing WorldState "
            "(molecule_ids); the final timeline state is pure-int"
        )

    times = timeline.times
    horizon = times[-1] - times[0]
    window_start_time = times[-1] - window * horizon
    window_start_idx = next(
        (i for i, t in enumerate(times) if t >= window_start_time), len(times) - 1
    )

    trajectories: list[PoolTrajectory] = []
    for j, name in enumerate(mol_ids):
        start_amt = _total_amount(states[window_start_idx], j)
        final_amt = _total_amount(states[-1], j)
        denom = max(abs(start_amt), _EPS)
        factor = abs(final_amt) / denom

        if factor >= theta:
            classification = "diverging"
        elif abs(start_amt) > _EPS and factor <= 1.0 / theta:
            classification = "collapsing"
        else:
            classification = "bounded"

        if classification != "bounded":
            logger.warning(
                "boundedness: pool %r %s over trailing window (factor=%.4g, "
                "start=%.4g, final=%.4g)",
                name,
                classification,
                factor,
                start_amt,
                final_amt,
            )
        trajectories.append(PoolTrajectory(name=name, factor=factor, classification=classification))

    return BoundednessReport(dynamic=tuple(trajectories))


def check_boundedness(
    world_or_skeleton: Union[WorldImpl, Skeleton],
    seed: Seed = Seed(0),
    *,
    theta: float = _DEFAULT_THETA,
    window: float = _DEFAULT_WINDOW,
    sim_cfg: SimConfig = SimConfig(),
) -> BoundednessReport:
    """Static necessary-condition reject, then a dynamic simulate-and-check confirmation.

    The one-call convenience a generator opts into (Q3=C, both layers): given either an
    already-materialized :class:`~alienbio.bio.world.WorldImpl` or a
    :class:`~alienbio.suite.skeleton.Skeleton` (materialized here with ``seed``),
    returns a :class:`BoundednessReport` combining :func:`static_bounded_fate` over the
    assembled chemistry with :func:`simulate_boundedness` over the assembled world.
    Deterministic given ``seed`` (materialize and simulate are both pure functions of
    it). NOT called by :meth:`Skeleton.materialize` — purely opt-in; callers (e.g. a
    generator) invoke it explicitly and act on ``report.static_unbounded`` /
    ``report.diverging`` / ``report.collapsing`` themselves (redraw, per F019 Q2=C).
    """
    world = world_or_skeleton.materialize(seed) if isinstance(world_or_skeleton, Skeleton) else world_or_skeleton
    static = static_bounded_fate(world.chemistry)
    dynamic_report = simulate_boundedness(world, seed, theta=theta, window=window, sim_cfg=sim_cfg)
    return BoundednessReport(static_unbounded=tuple(static), dynamic=dynamic_report.dynamic)
