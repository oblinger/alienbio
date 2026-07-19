"""M31.3 — the fixed-model / vary-world (Delta) harness generator (F022).

``draft_delta_pair`` composes committed Skeleton blocks (F013/F014) into a
MATCHED PAIR of worlds that share the same task structure but carry an
*inverted hidden regularity*: ``W_match`` (the conventional causal direction
holds — the conventional heuristic answers correctly) and ``W_mismatch`` (the
network is rewired so the conventional heuristic answers WRONG, while the
correct answer stays fully derivable from the observable dynamics). Feeding a
FIXED agent/model through both worlds and comparing its scores is the EXP-8
driver for paired-divergence scoring: a fixed decision rule that scores well
on ``W_match`` and poorly on ``W_mismatch`` is exposed as having learned the
heuristic, not the underlying causal structure.

**Q3=C (ratified): one template + an ``invert`` switch + a simulate-both
gate.** Two independently observable signal pools ``source_a``/``source_b``
each drain, ALWAYS, into their own dedicated boundedness sink (``sink_a``/
``sink_b`` — F012 D-f), regardless of ``invert``; ``source_a``'s supply rate
is ALWAYS the larger of the two (``r_a > r_b`` — Q1's fixed "conventionally-
implicated" signal: the one that reads as stronger/leading regardless of
which world you are in). On top of that fixed scaffold, exactly ONE
additional reaction — ``route_drive`` (``driver_pool -> T``) — is wired to
whichever source is the TRUE driver: ``source_a`` when ``invert=False``
(``W_match``, so the conventional heuristic "the bigger signal drives it"
happens to be right) and ``source_b`` when ``invert=True`` (``W_mismatch``,
so that same heuristic is now wrong — the true driver is the smaller,
decoy-looking signal). Because both configurations reuse the exact same
block TREE (same names, same child order, same rates) and every ``PoolBinding``
except ``route_drive``'s own is unconditional, the pair is matched BY
CONSTRUCTION: every reaction id, every molecule id, and every rate is
byte-identical across the pair except the REACTANT of ``route_drive``'s one
reaction — the single edge the ``invert`` switch flips (see
``tests/suite/test_delta_gen.py``'s ``test_pair_differs_by_exactly_one_edge``,
which walks both assembled chemistries and asserts this directly).

Each fixed ``PoolBinding`` deliberately lists the *sink* side first and the
*source* side second (``PoolBinding("sink_a.in", "source_a.out")``, not the
reverse) so that the shared pool's minted molecule id is always derived from
the SOURCE's own name (:func:`alienbio.suite.skeleton._realize_tree`'s
union-find roots a fresh binding on its SECOND ref) — this is what keeps
``source_a``'s and ``source_b``'s own observable identity stable across
``invert`` (a signal's own id never depends on whether it happens to ALSO be
wired to ``T`` this time). ``route_drive``'s own flippable binding
(``PoolBinding("route_drive.in", f"{driver_name}.out")``) then unions its
``in`` port into that SAME already-rooted component, so the driver's pool
gets a SECOND consumer (``route_drive``, in addition to its own always-on
sink) without ever renaming it. ``T`` and every reaction id likewise stay
stable (rooted on ``route_drive``/``sink_t``'s own names, both unconditional).

This is a DIAGNOSIS task (identify the true driver, not reach an outcome), so
the objective is an :class:`~alienbio.suite.types.AnswerObjective` (``node_id``
grader) whose key is the true driver's own molecule id — read directly off
the (post-materialize) skeleton, not re-inferred from raw chemistry, mirroring
:mod:`alienbio.suite.conflict_gen` / :mod:`alienbio.suite.pressure_gen`'s
"ground truth by construction" posture.

**The Q3=C simulate-both acceptance gate** (:func:`_assert_delta_gate`, run
automatically inside :func:`draft_delta_pair`) materializes + simulates BOTH
worlds and asserts, per the taint-free simulate-to-verify posture:

- the two worlds' true-driver answers actually DIFFER (the switch really
  flipped it, not just a no-op rewire);
- neither world is unsolvable: baseline ``T`` clears a floor target in both;
- discoverability: rebuilding either world with the TRUE driver's supply cut
  to zero collapses ``T`` back below that floor (perturbing the driver moves
  ``T``), while cutting the DECOY's supply to zero leaves ``T`` unchanged
  (perturbing the decoy does not) — the true driver, and only the true
  driver, is causally load-bearing for ``T`` in each world.

Raises :class:`~alienbio.suite.skeleton.SkeletonError` (fail visibly) if any
of the above fails to hold for a given rate configuration.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..bio.world import WorldImpl
from .blocks import ReactionBlock, SinkBlock, SourceBlock
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
from .types import Answer, AnswerObjective, GraderSpec, Objective, Timeline
from .verify import SimConfig

#: Default supply rates: ``source_a`` is ALWAYS the larger/"conventionally-
#: implicated" signal (Q1's fixed heuristic target) regardless of ``invert``.
DEFAULT_R_A = 5.0
DEFAULT_R_B = 1.0

#: Default rate for the ``route_drive`` reaction (whichever pool feeds ``T``).
DEFAULT_K_DRIVE = 2.0

#: Default rate for each signal's OWN, always-on boundedness sink
#: (``sink_a``/``sink_b``, F012 D-f) — deliberately small relative to
#: ``DEFAULT_K_DRIVE`` so it barely perturbs the driver's own dynamics; it
#: exists purely so an un-driven (decoy) signal still has a bounded fate.
DEFAULT_K_SINK = 0.05

#: Default rate draining ``T`` (its bounded fate, F012 D-f).
DEFAULT_K_T_SINK = 1.0

#: The floor ``T`` must clear at baseline in EITHER world (comfortably below
#: both driver rates' steady-state contribution) — the "neither world is
#: unsolvable" half of the acceptance gate.
DEFAULT_T_TARGET = 0.5

_SIM_CFG = SimConfig(dt=0.05, steps=400, sample_every=50)

#: Absolute tolerance for "cutting the decoy left T unchanged" — T's dynamics
#: are exactly decoupled from the decoy pool by construction, so any real
#: discrepancy here signals an ODE/config escape hatch, not numerical noise.
_DECOY_TOLERANCE = 1e-3


@dataclass(frozen=True)
class _DeltaCruxBlock(SkeletonBlock):
    """CRUX (M31.3 Delta pattern): two observable signal pools, one inverted
    causal edge to ``T``.

    A **pattern** node (no ``realize`` override; content lives entirely in
    ``children``, per the ``SkeletonBlock`` base), mirroring
    :class:`~alienbio.suite.blocks.ConflictCruxBlock`'s composition style.
    :meth:`make` builds the fixed six-child shape — ``source_a``/``source_b``
    + their own ``sink_a``/``sink_b`` (always bound, giving both signals a
    bounded fate independent of ``invert``), ``route_drive`` (a bare
    :class:`~alienbio.suite.blocks.ReactionBlock`, ``driver -> T``) and
    ``sink_t`` (``T``'s own bounded fate) — identical regardless of
    ``invert``; only ``route_drive.in``'s binding target (``source_a.out`` vs
    ``source_b.out``) flips. ``params["invert"]`` is threaded through so
    :meth:`ground_truth` (and the drafter) can read back which source is
    currently the true driver.
    """

    @classmethod
    def make(
        cls,
        name: str,
        *,
        invert: bool,
        container: Optional[str] = None,
        r_a: Dist[float],
        r_b: Dist[float],
        k_drive: Dist[float],
        k_sink: Dist[float],
        k_t_sink: Dist[float],
        params: Optional[dict] = None,
    ) -> "_DeltaCruxBlock":
        source_a = SourceBlock.make("source_a", container=container, rate=r_a)
        source_b = SourceBlock.make("source_b", container=container, rate=r_b)
        sink_a = SinkBlock.make("sink_a", container=container, rate=k_sink)
        sink_b = SinkBlock.make("sink_b", container=container, rate=k_sink)
        route_drive = ReactionBlock(
            name="route_drive",
            role=Role.CRUX,
            ports=(
                Port("in", container, PortDir.IN),
                Port("out", container, PortDir.OUT),
            ),
            rate=k_drive,
        )
        sink_t = SinkBlock.make("sink_t", container=container, rate=k_t_sink)

        driver_name = "source_b" if invert else "source_a"
        pool_bindings = (
            # sink side first, source side second (see module docstring):
            # keeps each source's OWN resolved id stable regardless of
            # `invert` / whether `route_drive` ALSO joins that component.
            PoolBinding("sink_a.in", "source_a.out"),
            PoolBinding("sink_b.in", "source_b.out"),
            PoolBinding("sink_t.in", "route_drive.out"),
            # The ONE flippable edge: which source's pool ALSO feeds T.
            PoolBinding("route_drive.in", f"{driver_name}.out"),
        )
        return cls(
            name=name,
            role=Role.CRUX,
            children=(source_a, source_b, sink_a, sink_b, route_drive, sink_t),
            pool_bindings=pool_bindings,
            params={**(params or {}), "invert": invert},
        )

    def ground_truth(self, timeline: Timeline) -> tuple[float, float, float]:
        source_a = next((c for c in self.children if c.name == "source_a"), None)
        source_b = next((c for c in self.children if c.name == "source_b"), None)
        route_drive = next((c for c in self.children if c.name == "route_drive"), None)
        if (
            source_a is None
            or source_b is None
            or route_drive is None
            or not source_a.resolved_ports
            or not source_b.resolved_ports
            or not route_drive.resolved_ports
        ):
            raise SkeletonError(
                f"{self.name!r} has unresolved routes; call materialize() first"
            )
        invert = bool(self.params.get("invert", False))
        driver = source_b if invert else source_a
        decoy = source_a if invert else source_b
        t_id = route_drive.resolved_ports["out"]
        driver_id = driver.resolved_ports["out"]
        decoy_id = decoy.resolved_ports["out"]
        return (
            final_amount(timeline, t_id),
            final_amount(timeline, driver_id),
            final_amount(timeline, decoy_id),
        )


def build_delta_skeleton(
    *,
    invert: bool,
    r_a: Dist[float],
    r_b: Dist[float],
    k_drive: Dist[float],
    k_sink: Dist[float],
    k_t_sink: Dist[float],
) -> Skeleton:
    """The Delta shape: ``root -> _DeltaCruxBlock`` (self-contained, no
    top-level source needed — both signals live inside the crux).

    Unmaterialized — callers ``materialize()``/``oracle()`` it themselves.
    Doubles as the shared builder :func:`_draft_delta_world` and
    :func:`_assert_delta_gate` both use (mirroring
    :func:`alienbio.suite.conflict_gen.build_conflict_skeleton`'s role).
    """
    crux = _DeltaCruxBlock.make(
        "crux",
        invert=invert,
        r_a=r_a,
        r_b=r_b,
        k_drive=k_drive,
        k_sink=k_sink,
        k_t_sink=k_t_sink,
    )
    root = SkeletonBlock(name="root", role=Role.SUPPLY, children=(crux,))
    return Skeleton(
        root=root,
        control_surface=("root/crux/source_a.out", "root/crux/source_b.out"),
        crux="root/crux",
    )


def _true_driver_source_name(*, invert: bool) -> str:
    return "source_b" if invert else "source_a"


def _draft_delta_world(
    seed: Seed,
    *,
    invert: bool,
    r_a: Dist[float],
    r_b: Dist[float],
    k_drive: Dist[float],
    k_sink: Dist[float],
    k_t_sink: Dist[float],
) -> tuple[WorldImpl, Skeleton, Objective]:
    """Draft one side of the Delta pair (``invert=False`` -> ``W_match``,
    ``invert=True`` -> ``W_mismatch``)."""
    skeleton = build_delta_skeleton(
        invert=invert,
        r_a=r_a,
        r_b=r_b,
        k_drive=k_drive,
        k_sink=k_sink,
        k_t_sink=k_t_sink,
    )
    world = skeleton.materialize(seed)

    crux = skeleton.root.children[0]
    driver = next(
        c for c in crux.children if c.name == _true_driver_source_name(invert=invert)
    )
    driver_id = driver.resolved_ports["out"]

    objective: Objective = AnswerObjective(
        grader=GraderSpec(kind="node_id"),
        key=Answer(value=driver_id, kind="node_id"),
    )
    return world, skeleton, objective


def _assert_delta_gate(
    seed: Seed,
    match: tuple[WorldImpl, Skeleton, Objective],
    mismatch: tuple[WorldImpl, Skeleton, Objective],
    *,
    r_a: float,
    r_b: float,
    k_drive: Dist[float],
    k_sink: Dist[float],
    k_t_sink: Dist[float],
    t_target: float,
    sim_cfg: SimConfig,
) -> None:
    """Q3=C simulate-both acceptance gate: materialize + simulate BOTH sides
    of the pair and confirm the invert switch genuinely flipped the answer
    and that the true driver (and only the true driver) is discoverable —
    see the module docstring's "simulate-both acceptance gate" section.

    Raises:
        SkeletonError: the two worlds' true-driver answers coincide (the
            switch did not flip anything), a world's baseline ``T`` fails to
            clear ``t_target`` (unsolvable), cutting the identified true
            driver's supply fails to collapse ``T`` back below ``t_target``
            (the identified driver isn't actually load-bearing), or cutting
            the decoy's supply moves ``T`` (the decoy isn't causally inert).
    """
    _world_match, skeleton_match, objective_match = match
    _world_mismatch, skeleton_mismatch, objective_mismatch = mismatch
    assert isinstance(objective_match, AnswerObjective)
    assert isinstance(objective_mismatch, AnswerObjective)

    if objective_match.key.value == objective_mismatch.key.value:
        raise SkeletonError(
            "delta gate: invert did not flip the true driver — both W_match "
            f"and W_mismatch answer {objective_match.key.value!r}"
        )

    for invert, skeleton in ((False, skeleton_match), (True, skeleton_mismatch)):
        t_base, _driver_base, _decoy_base = skeleton.oracle(seed, sim_cfg)
        if t_base < t_target:
            raise SkeletonError(
                f"delta gate: invert={invert!r} world's T only reached "
                f"{t_base!r} < target {t_target!r} at baseline rates — "
                "unsolvable"
            )

        driver_cut = build_delta_skeleton(
            invert=invert,
            r_a=Constant(0.0 if not invert else r_a),
            r_b=Constant(r_b if not invert else 0.0),
            k_drive=k_drive,
            k_sink=k_sink,
            k_t_sink=k_t_sink,
        )
        t_driver_cut, *_ = driver_cut.oracle(seed, sim_cfg)
        if t_driver_cut >= t_target:
            raise SkeletonError(
                f"delta gate: invert={invert!r} — cutting the true driver's "
                f"supply to 0 still reached T={t_driver_cut!r} >= target "
                f"{t_target!r}; the identified driver does not actually "
                "drive T"
            )

        decoy_cut = build_delta_skeleton(
            invert=invert,
            r_a=Constant(r_a if not invert else 0.0),
            r_b=Constant(0.0 if not invert else r_b),
            k_drive=k_drive,
            k_sink=k_sink,
            k_t_sink=k_t_sink,
        )
        t_decoy_cut, *_ = decoy_cut.oracle(seed, sim_cfg)
        if abs(t_decoy_cut - t_base) > _DECOY_TOLERANCE:
            raise SkeletonError(
                f"delta gate: invert={invert!r} — cutting the decoy signal's "
                f"supply moved T from {t_base!r} to {t_decoy_cut!r}; the "
                "decoy is not causally inert, breaking discoverability"
            )


def draft_delta_pair(
    seed: Seed = Seed(0),
    *,
    r_a: float = DEFAULT_R_A,
    r_b: float = DEFAULT_R_B,
    k_drive: Optional[Dist[float]] = None,
    k_sink: Optional[Dist[float]] = None,
    k_t_sink: Optional[Dist[float]] = None,
    t_target: float = DEFAULT_T_TARGET,
    sim_cfg: SimConfig = _SIM_CFG,
) -> tuple[tuple[WorldImpl, Skeleton, Objective], tuple[WorldImpl, Skeleton, Objective]]:
    """Draft the M31.3 Delta pair: ``(W_match, W_mismatch)``, matched by
    construction off ONE ``build_delta_skeleton(seed, invert=...)`` template.

    ``r_a`` is always the larger of the two supply rates (the conventionally-
    implicated, "stronger signal" heuristic target) — ``W_match`` wires it as
    the true driver of ``T``; ``W_mismatch`` rewires ``T``'s one driving edge
    onto ``source_b`` instead, so the same "bigger signal drives it" heuristic
    now answers wrong while the true driver (now the smaller signal) stays
    fully derivable from the observable dynamics.

    Runs :func:`_assert_delta_gate` (Q3=C) before returning: a generation-time
    simulate-both check that the switch really flipped the answer and that
    the true driver (and only the true driver) is discoverable in both
    worlds.

    Deterministic in ``seed``: both sides materialize off the SAME ``seed``
    against the SAME block tree (only ``route_drive``'s own ``PoolBinding``
    differs), so every rate draw lands identically across the pair.

    Raises:
        ValueError: ``r_a`` is not strictly greater than ``r_b``.
        SkeletonError: the Q3=C acceptance gate fails (see
            :func:`_assert_delta_gate`).
    """
    if r_a <= r_b:
        raise ValueError(
            "r_a must be strictly greater than r_b (the conventionally-"
            f"implicated signal is defined as the larger one), got "
            f"r_a={r_a!r}, r_b={r_b!r}"
        )

    resolved_k_drive = k_drive if k_drive is not None else Constant(DEFAULT_K_DRIVE)
    resolved_k_sink = k_sink if k_sink is not None else Constant(DEFAULT_K_SINK)
    resolved_k_t_sink = k_t_sink if k_t_sink is not None else Constant(DEFAULT_K_T_SINK)

    match = _draft_delta_world(
        seed,
        invert=False,
        r_a=Constant(r_a),
        r_b=Constant(r_b),
        k_drive=resolved_k_drive,
        k_sink=resolved_k_sink,
        k_t_sink=resolved_k_t_sink,
    )
    mismatch = _draft_delta_world(
        seed,
        invert=True,
        r_a=Constant(r_a),
        r_b=Constant(r_b),
        k_drive=resolved_k_drive,
        k_sink=resolved_k_sink,
        k_t_sink=resolved_k_t_sink,
    )

    _assert_delta_gate(
        seed,
        match,
        mismatch,
        r_a=r_a,
        r_b=r_b,
        k_drive=resolved_k_drive,
        k_sink=resolved_k_sink,
        k_t_sink=resolved_k_t_sink,
        t_target=t_target,
        sim_cfg=sim_cfg,
    )

    return match, mismatch
