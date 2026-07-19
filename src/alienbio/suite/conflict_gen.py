"""M31.1 — the multi-objective conflict-ladder generator (F022).

``draft_conflict_world`` composes committed Skeleton blocks (F013/F014) into a
world carrying an *engineered, structural* multi-objective tradeoff: a
:class:`~alienbio.suite.blocks.SourceBlock` feeds a shared ``precursor`` pool
into a :class:`~alienbio.suite.blocks.ConflictCruxBlock` whose two rival routes
raise targets ``V1``/``V2``. One coupling knob — the source's supply rate
``S`` — sweeps a four-rung ladder (Q1=C, the ratified hybrid lean):

- ``single`` — a topology switch: only ``route`` exists (a bare
  :class:`~alienbio.suite.blocks.ReactionBlock`, no crux, no rival route) so
  the task genuinely has one live objective, no tradeoff.
- ``compatible`` — ``S`` set generously above ``v1_target + v2_target``; both
  targets clear comfortably at the default balanced split (``kA == kB``).
- ``latent`` — ``S == v1_target + v2_target`` exactly: the balanced default
  split hits both targets right at the boundary (looks conflict-free), but any
  asymmetric reallocation trades one target off against the other — the
  tension is real but hidden from a policy that never perturbs the split.
- ``forced`` — ``S`` set below ``v1_target + v2_target``: the analytic
  steady-state invariant ``prodA_ss + prodB_ss == S`` (both routes drain their
  own product through the SAME unit sink rate, so the shared-precursor
  balance forces the two routes' steady outputs to sum to exactly the
  source's supply, independent of the ``(kA, kB)`` split — see
  :func:`closed_form_frontier`) makes it PROVABLY impossible for both targets
  to be met at once. A generation-time simulate-and-check gate
  (:func:`_assert_forced_gate`, Q2=C) sweeps several ``(kA, kB)`` allocations
  through the real assembled world and fails loudly if any of them manages to
  satisfy both targets — the same taint-free canary posture as the F012
  homeostasis simulate-and-check sibling.

The crux's own :meth:`~alienbio.suite.blocks.ConflictCruxBlock.ground_truth`
already returns the achieved ``(prodA, prodB)`` point (F014); the closed-form
frontier for a given rung is the line ``{(a, b): a + b == S, a, b >= 0}`` —
:func:`closed_form_frontier` samples it directly, no simulation needed.

The task objective is a two-component ``OutcomeObjective`` (one component per
target): its scorer reads both targets' final concentrations and reduces them
to ONE score via ``min`` — a bottleneck combination, since a genuine joint win
requires BOTH components to clear their target, not just their average.
``single`` returns the same objective shape over its one live target.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from ..bio.world import WorldImpl
from .blocks import ConflictCruxBlock, ReactionBlock, SinkBlock, SourceBlock, sweep_conflict_frontier
from .dist import Constant, Dist, Seed
from .skeleton import (
    Port,
    PortDir,
    PoolBinding,
    Role,
    Skeleton,
    SkeletonBlock,
    SkeletonError,
    final_amount,
)
from .types import Objective, OutcomeObjective, Timeline
from .verify import SimConfig

#: The four conflict-ladder rungs (Q1=C: a topology switch for ``single``, a
#: continuous coupling scalar for the rest — realized here as named cut-points
#: on the source supply rate ``S``).
RUNGS = ("single", "compatible", "latent", "forced")

#: Default per-target goal (``V1`` and ``V2`` share this value so a rung's
#: character comes entirely from ``S``, not from asymmetric targets).
DEFAULT_TARGET = 10.0

#: The default, "naive" route-rate split every rung materializes with —
#: ``latent``'s whole point is that THIS default looks conflict-free.
DEFAULT_KA = 1.0
DEFAULT_KB = 1.0

_SIM_CFG = SimConfig(dt=0.05, steps=400, sample_every=50)

#: ``S`` multipliers relative to ``v1_target + v2_target`` (Q1's continuous
#: coupling knob, realized per the F022 lean as "how strongly the two routes'
#: rates draw from the same shared precursor budget" via the Source rate):
#: generous slack, the exact boundary, and a provable deficit.
_S_MULTIPLIER = {
    "compatible": 4.0,
    "latent": 1.0,
    "forced": 0.4,
}

#: ``single``'s supply margin above its lone target (no rival route to share
#: the budget with, so a modest margin is enough to comfortably clear it).
_SINGLE_MARGIN = 1.2

#: The ``(kA, kB)`` allocations the ``forced`` acceptance gate sweeps — a
#: fixed total "rate effort" split across near-monopoly-to-balanced fractions;
#: the achieved SUM asymptotes to ``S`` regardless of the split (the closed-
#: form invariant), so a small, cheap sweep suffices to canary an escape hatch.
_GATE_TOTAL_RATE = 10.0
_GATE_FRACTIONS = (0.01, 0.25, 0.5, 0.75, 0.99)


@dataclass(frozen=True)
class _SingleRouteCrux(ReactionBlock):
    """CRUX (single-route config, Q1=C topology switch): one ``in -> out``
    route, no rival — genuinely one objective, no shared-precursor tradeoff.

    A local subclass (not a ``blocks.py`` edit — F014 is committed) adding the
    one thing :class:`~alienbio.suite.blocks.ReactionBlock` lacks:
    ``ground_truth`` reading its own resolved ``out`` port's final amount, so
    ``single`` exposes the SAME ``Skeleton.oracle()`` shape (a tuple) as the
    two-route rungs — a 1-tuple here instead of a 2-tuple.
    """

    def ground_truth(self, timeline: Timeline) -> tuple[float]:
        if not self.resolved_ports:
            raise SkeletonError(
                f"{self.name!r} has unresolved ports; call materialize() first"
            )
        return (final_amount(timeline, self.resolved_ports["out"]),)


def _component_score(final: float, target: float) -> float:
    """1.0 once ``final`` clears ``target``; else a bounded falloff below it.

    Mirrors :func:`alienbio.suite.arch_intervene.make_target_scorer`'s falloff
    shape, but is one-sided (overshooting the target costs nothing) since a
    conflict rung's whole point is "reach at least both targets", not hit them
    on the nose.
    """
    if final >= target:
        return 1.0
    return 1.0 / (1.0 + (target - final))


def _make_single_scorer(v1_id: str, v1_target: float) -> Callable[[Timeline], float]:
    def scorer(timeline: Timeline) -> float:
        return _component_score(final_amount(timeline, v1_id), v1_target)

    return scorer


def _make_pair_scorer(
    v1_id: str, v1_target: float, v2_id: str, v2_target: float
) -> Callable[[Timeline], float]:
    def scorer(timeline: Timeline) -> float:
        s1 = _component_score(final_amount(timeline, v1_id), v1_target)
        s2 = _component_score(final_amount(timeline, v2_id), v2_target)
        return min(s1, s2)

    return scorer


def build_conflict_skeleton(
    *, source_rate: float, kA: Dist[float], kB: Dist[float]
) -> Skeleton:
    """The ``compatible``/``latent``/``forced`` shape: ``Source -> ConflictCrux``.

    Unmaterialized — callers ``materialize()``/``oracle()`` it themselves.
    ``kA``/``kB`` are ``Dist`` holes (Q1=B, per
    :class:`~alienbio.suite.blocks.ConflictCruxBlock`), not raw floats, so this
    doubles as the ``build`` callable
    :func:`~alienbio.suite.blocks.sweep_conflict_frontier` expects — used both
    by :func:`draft_conflict_world` and by the ``forced`` acceptance gate.
    """
    source = SourceBlock.make("source", rate=Constant(source_rate))
    crux = ConflictCruxBlock.make("crux", kA=kA, kB=kB)
    root = SkeletonBlock(
        name="root",
        role=Role.SUPPLY,
        children=(source, crux),
        pool_bindings=(PoolBinding("source.out", "crux.precursor"),),
    )
    return Skeleton(root=root, control_surface=("root/source.out",), crux="root/crux")


def _build_single_skeleton(*, source_rate: float, kA: Dist[float]) -> Skeleton:
    """The ``single`` shape (Q1=C topology switch): ``Source -> one bare route``.

    No :class:`~alienbio.suite.blocks.ConflictCruxBlock`, no rival route —
    ``route`` (a :class:`_SingleRouteCrux`) is the crux directly, wired
    precursor -> out -> an internal sink so the product still has a bounded
    fate (F012 D-f).
    """
    source = SourceBlock.make("source", rate=Constant(source_rate))
    route = _SingleRouteCrux(
        name="route",
        role=Role.CRUX,
        ports=(Port("in", None, PortDir.IN), Port("out", None, PortDir.OUT)),
        rate=kA,
    )
    sink = SinkBlock.make("sink")
    root = SkeletonBlock(
        name="root",
        role=Role.SUPPLY,
        children=(source, route, sink),
        pool_bindings=(
            PoolBinding("source.out", "route.in"),
            PoolBinding("route.out", "sink.in"),
        ),
    )
    return Skeleton(root=root, control_surface=("root/source.out",), crux="root/route")


def closed_form_frontier(
    source_rate: float, n_points: int = 11
) -> tuple[tuple[float, float], ...]:
    """The linear-frontier closed form (Build step 3): the achievable ``(V1,
    V2)`` steady-state line ``{(a, b): a + b == source_rate, a, b >= 0}``.

    Exact because both routes drain their own product through the SAME unit
    sink rate: at steady state ``dP/dt = 0`` forces the precursor's total
    outflow (``(kA + kB) * P_ss``) to equal the source's constant supply
    ``source_rate``, and each route's own steady product equals its own
    inflow (``prodA_ss = kA * P_ss``, ``prodB_ss = kB * P_ss``) since its sink
    drains at the same unit rate — so the split moves with ``(kA, kB)`` but
    the SUM never does. No simulation needed; this is the design invariant
    Q2's structural bound leans on.
    """
    if n_points < 2:
        raise ValueError(f"n_points must be >= 2, got {n_points}")
    return tuple(
        (
            source_rate * i / (n_points - 1),
            source_rate * (n_points - 1 - i) / (n_points - 1),
        )
        for i in range(n_points)
    )


def _assert_forced_gate(
    seed: Seed, source_rate: float, v1_target: float, v2_target: float
) -> None:
    """Q2=C simulate-and-check acceptance gate: materialize + simulate several
    ``(kA, kB)`` allocations and confirm NONE of them satisfies both targets.

    Mirrors the F012 homeostasis simulate-and-check posture: the structural
    bound (:func:`closed_form_frontier`) is the design invariant, but this is
    the generation-time canary that catches an indirection/nonlinearity
    escape hatch the closed form alone would miss.

    Raises:
        SkeletonError: some swept allocation reached both targets at once.
    """
    points = tuple(
        (_GATE_TOTAL_RATE * frac, _GATE_TOTAL_RATE * (1.0 - frac))
        for frac in _GATE_FRACTIONS
    )

    def build(kA: Dist[float], kB: Dist[float]) -> Skeleton:
        return build_conflict_skeleton(source_rate=source_rate, kA=kA, kB=kB)

    achieved = sweep_conflict_frontier(build, seed.child("forced-gate"), points, _SIM_CFG)
    for (kA, kB), (a, b) in zip(points, achieved):
        if a >= v1_target and b >= v2_target:
            raise SkeletonError(
                f"forced rung failed the simulate-and-check gate: allocation "
                f"(kA={kA!r}, kB={kB!r}) reached ({a!r}, {b!r}), both >= "
                f"targets ({v1_target!r}, {v2_target!r}) at source_rate="
                f"{source_rate!r} — an escape hatch opened a tradeoff the "
                "closed-form bound forbids"
            )


def draft_conflict_world(
    seed: Seed = Seed(0),
    *,
    rung: str,
    v1_target: float = DEFAULT_TARGET,
    v2_target: float = DEFAULT_TARGET,
    kA: Optional[Dist[float]] = None,
    kB: Optional[Dist[float]] = None,
    sim_cfg: SimConfig = _SIM_CFG,
) -> tuple[WorldImpl, Skeleton, Objective]:
    """Draft one rung of the M31.1 conflict ladder.

    ``rung`` in :data:`RUNGS`. Builds ``Source -> ConflictCrux`` (or, for
    ``single``, ``Source -> route`` with no rival), sizes the source's supply
    rate off ``rung`` (Q1=C's continuous coupling knob) and ``v1_target`` /
    ``v2_target``, materializes, and returns the world + the (now
    provenance-populated) :class:`~alienbio.suite.skeleton.Skeleton` + a
    two-component :class:`~alienbio.suite.types.OutcomeObjective`
    (one-component for ``single``).

    Deterministic in ``seed``: the block library's own seed-derived rate
    sampling is a no-op here since ``kA``/``kB`` default to ``Constant``
    (and any caller-supplied ``Dist`` is still sampled from the same ``seed``
    every call).

    Raises:
        ValueError: ``rung`` is not one of :data:`RUNGS`.
        SkeletonError: the ``forced`` rung fails its simulate-and-check
            acceptance gate (Q2=C) — an indirection/nonlinearity escape hatch
            let some allocation satisfy both targets at once.
    """
    if rung not in RUNGS:
        raise ValueError(f"rung must be one of {RUNGS}, got {rung!r}")

    resolved_kA = kA if kA is not None else Constant(DEFAULT_KA)
    resolved_kB = kB if kB is not None else Constant(DEFAULT_KB)

    if rung == "single":
        source_rate = _SINGLE_MARGIN * v1_target
        skeleton = _build_single_skeleton(source_rate=source_rate, kA=resolved_kA)
        world = skeleton.materialize(seed)

        route = skeleton.root.children[1]
        v1_id = route.resolved_ports["out"]
        objective: Objective = OutcomeObjective(
            scorer=_make_single_scorer(v1_id, v1_target), target=(v1_id, v1_target)
        )
        return world, skeleton, objective

    source_rate = _S_MULTIPLIER[rung] * (v1_target + v2_target)
    skeleton = build_conflict_skeleton(
        source_rate=source_rate, kA=resolved_kA, kB=resolved_kB
    )
    world = skeleton.materialize(seed)

    if rung == "forced":
        _assert_forced_gate(seed, source_rate, v1_target, v2_target)

    crux = skeleton.root.children[1]
    route_a = next(c for c in crux.children if c.name == "route_a")
    route_b = next(c for c in crux.children if c.name == "route_b")
    v1_id = route_a.resolved_ports["out"]
    v2_id = route_b.resolved_ports["out"]

    objective = OutcomeObjective(
        scorer=_make_pair_scorer(v1_id, v1_target, v2_id, v2_target),
        target=((v1_id, v1_target), (v2_id, v2_target)),
    )
    return world, skeleton, objective
