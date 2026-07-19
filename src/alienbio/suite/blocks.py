"""Skeleton block library (F014) — the concrete, engine-ready `SkeletonBlock` catalog.

F013 (:mod:`alienbio.suite.skeleton`) built the recursive composition machinery
(``Port`` / ``PoolBinding`` / ``Fragment`` / ``SkeletonBlock`` / ``Skeleton``)
but shipped no concrete blocks — ``SkeletonBlock``'s default ``realize``
returns an empty ``Fragment``. This module supplies the five blocks whose
``realize`` emits real, **constant-rate mass-action** ``ReactionImpl``s (no
S2 rate-modulation, no S3 transport — those are F015/F016):

- :class:`ReactionBlock` — the one primitive. Every ``IN`` port becomes a
  reactant, every ``OUT`` port becomes a product; it emits exactly one
  ``ReactionImpl`` with a constant rate sampled from a ``Dist`` hole.
- :class:`SourceBlock` / :class:`SinkBlock` — boundary *configs* of
  ``ReactionBlock`` (Q4=A): a block with only ``OUT`` ports naturally has
  empty reactants (``∅ -> pool``); only ``IN`` ports naturally has empty
  products (``pool -> ∅``). Neither overrides ``realize`` — one code path.
- :class:`ConflictCruxBlock` — a *pattern* (no ``realize`` override; its
  content lives entirely in its children, per the ``SkeletonBlock`` base) that
  expands into a shared ``precursor`` pool feeding two independent
  ``ReactionBlock`` routes (Q1=B: two separate ``Dist`` holes ``kA``/``kB``,
  not a split ratio) plus two internal sinks draining the routes' products —
  the internal sinks give ``prodA``/``prodB`` a bounded fate (F012 D-f) purely
  within the block, with no extra top-level wiring required. ``ground_truth``
  climbs to the two routes and reads the achieved ``(prodA, prodB)`` point
  (Q2 — the achieved point, not a scalar score); :func:`sweep_conflict_frontier`
  is the companion helper that sweeps ``(kA, kB)`` pairs to trace the frontier.
- :class:`PressureBlock` — a ``SinkBlock``-shaped boundary drain. Default: a
  constant-magnitude drain (Q3 default arm). Opt-in: a :class:`PoissonSchedule`
  param additionally draws a reproducible discrete insult-time schedule from
  ``seed.child(ns).rng()`` at ``realize`` time (byte-identical for a given
  seed) — metadata for a future conditional-policy consumer; it does not
  itself perturb the constant mass-action rate (that seam is S2/F015).

Every block is domain-neutral: biology lives only in opaque ``name`` tags on
molecules/pools; nothing here branches on a biological concept.

F015 S2 (M38.3) adds four **pattern-block** modifiers, now that the world
simulator reads a ``Modulation`` record and multiplies a reaction's rate by a
bidirectional factor (``WorldSimulatorImpl._modulation_factor``). Each turns
what used to be a multi-reaction idiom (e.g. a separate "signal cascade" or an
``S + E -> ES -> P + E`` enzyme mechanism) into ONE ``ReactionImpl`` carrying a
non-consumed modifier species, via the shared :func:`_modulator_fragment`
realize body:

- :class:`SignalingBlock` — a control wire: one linear ``"activator"`` or
  ``"inhibitor"`` modifier (``kind=`` selects which) attached to an
  ``in -> out`` reaction.
- :class:`InhibitionBlock` — a dedicated linear ``"inhibitor"`` config (the
  same attachment ``SignalingBlock(kind="inhibitor")`` already covers, kept
  separate for a single-purpose, no-``kind``-arg block).
- :class:`EnzymeBlock` — a saturating ``"michaelis"`` catalyst modifier on a
  ``substrate -> product`` reaction; no ``ES`` intermediate pool.
- :class:`CooperativeBindingBlock` — a cooperative ``"hill"`` modifier
  (exponent ``n``) on an ``in -> out`` reaction; higher ``n`` sharpens the
  response into a step around ``K``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Mapping, Optional, Sequence, cast

from ..bio.molecule import MoleculeImpl
from ..bio.reaction import Modulation, ReactionImpl
from ..bio.world import NodeId
from ..infra.mk import mk
from .dist import Constant, Dist, Seed
from .skeleton import (
    Fragment,
    Port,
    PortDir,
    PoolBinding,
    Provenance,
    Role,
    Skeleton,
    SkeletonBlock,
    SkeletonError,
    final_amount,
)
from .types import Tags, Timeline
from .verify import SimConfig

_DEFAULT_CONTAINER: NodeId = "cell"


def _container_of(ports: tuple[Port, ...]) -> NodeId:
    """First declared container among ``ports``, else the default single compartment."""
    for port in ports:
        if port.container is not None:
            return port.container
    return _DEFAULT_CONTAINER


@dataclass(frozen=True)
class ReactionBlock(SkeletonBlock):
    """The reaction primitive (Q4=A): every ``IN`` port -> reactant, every
    ``OUT`` port -> product, one constant-rate ``ReactionImpl``.

    ``rate`` is a ``Dist[float]`` hole sampled with the block's own namespaced
    seed (``seed.child("rate")``), so kinetics depend only on tree position,
    never on iteration order. ``stoich`` optionally overrides a port's default
    coefficient of ``1.0`` (keyed by port name) — needed when a reaction isn't
    1:1 (e.g. ``2 A -> B``) and atom-balance depends on the coefficient.

    Boundary configs fall out for free: a block with no ``IN`` ports emits
    ``∅ -> products`` (:class:`SourceBlock`); no ``OUT`` ports emits
    ``reactants -> ∅`` (:class:`SinkBlock`) — no separate code path needed.
    """

    rate: Dist[float] = field(default_factory=lambda: Constant(1.0))
    stoich: Mapping[str, float] = field(default_factory=dict)

    def realize(self, seed: Seed, ns: str, bound: Mapping[str, MoleculeImpl]) -> Fragment:
        reactants: dict[MoleculeImpl, float] = {}
        products: dict[MoleculeImpl, float] = {}
        for port in self.ports:
            molecule = bound[port.name]
            coef = self.stoich.get(port.name, 1.0)
            if port.direction is PortDir.IN:
                reactants[molecule] = coef
            else:
                products[molecule] = coef

        rate = self.rate.sample(seed.child("rate"))
        rxn_id = f"{ns}/rxn"
        container = _container_of(self.ports)
        reaction = cast(ReactionImpl, mk.R(rxn_id, reactants, products, rate=rate))
        molecules = {m.name: m for m in list(reactants) + list(products)}
        return Fragment(
            molecules=molecules,
            reactions={rxn_id: reaction},
            provenance=(Provenance(rxn_id, container),),
        )


@dataclass(frozen=True)
class SourceBlock(ReactionBlock):
    """SUPPLY: a :class:`ReactionBlock` config with only an ``OUT`` port —
    ``∅ -> pool @ base_rate``. Boundary/exempt from the F012 balance gate
    (empty reactants) — see :func:`alienbio.bio.conservation.is_boundary_reaction`.
    """

    @classmethod
    def make(
        cls,
        name: str,
        *,
        port: str = "out",
        container: Optional[NodeId] = None,
        rate: Optional[Dist[float]] = None,
        params: Optional[Tags] = None,
    ) -> "SourceBlock":
        return cls(
            name=name,
            role=Role.SUPPLY,
            ports=(Port(port, container, PortDir.OUT),),
            rate=rate if rate is not None else Constant(1.0),
            params=params or {},
        )


@dataclass(frozen=True)
class SinkBlock(ReactionBlock):
    """SINK: a :class:`ReactionBlock` config with only an ``IN`` port —
    ``pool -> ∅ @ rate``. Boundary/exempt from the F012 balance gate (empty
    products) — the bounded fate that makes a pool homeostatic (F012 D-f).
    """

    @classmethod
    def make(
        cls,
        name: str,
        *,
        port: str = "in",
        container: Optional[NodeId] = None,
        rate: Optional[Dist[float]] = None,
        params: Optional[Tags] = None,
    ) -> "SinkBlock":
        return cls(
            name=name,
            role=Role.SINK,
            ports=(Port(port, container, PortDir.IN),),
            rate=rate if rate is not None else Constant(1.0),
            params=params or {},
        )


@dataclass(frozen=True)
class ConflictCruxBlock(SkeletonBlock):
    """CRUX: a shared ``precursor`` pool feeding two rival consuming routes.

    A **pattern** node — no ``realize`` override; its content is entirely its
    ``children`` (per the ``SkeletonBlock`` base). :meth:`make` builds the
    fixed shape: two :class:`ReactionBlock` routes ``route_a``/``route_b``
    (``precursor -> prodA @ kA``, ``precursor -> prodB @ kB`` — Q1=B, two
    independent ``Dist`` holes, *not* a split ratio; the shared budget reads
    only through the shared ``precursor`` pool) plus two internal
    :class:`SinkBlock`s draining ``prodA``/``prodB`` — giving both a bounded
    fate (F012 D-f) without requiring the parent tree to wire anything beyond
    ``precursor``.

    :meth:`ground_truth` (Q2) climbs to the two routes' realized
    ``resolved_ports`` and returns the achieved ``(prodA, prodB)`` point off
    the simulated ``Timeline`` — the honest ground truth is the point, not a
    scalar score; :func:`sweep_conflict_frontier` traces the frontier by
    varying ``(kA, kB)`` across several materializations.
    """

    @classmethod
    def make(
        cls,
        name: str,
        *,
        precursor_port: str = "precursor",
        container: Optional[NodeId] = None,
        kA: Optional[Dist[float]] = None,
        kB: Optional[Dist[float]] = None,
        params: Optional[Tags] = None,
    ) -> "ConflictCruxBlock":
        route_a = ReactionBlock(
            name="route_a",
            role=Role.CRUX,
            ports=(
                Port("in", container, PortDir.IN),
                Port("out", container, PortDir.OUT),
            ),
            rate=kA if kA is not None else Constant(1.0),
        )
        route_b = ReactionBlock(
            name="route_b",
            role=Role.CRUX,
            ports=(
                Port("in", container, PortDir.IN),
                Port("out", container, PortDir.OUT),
            ),
            rate=kB if kB is not None else Constant(1.0),
        )
        sink_a = SinkBlock.make("sink_a", container=container)
        sink_b = SinkBlock.make("sink_b", container=container)
        return cls(
            name=name,
            role=Role.CRUX,
            ports=(Port(precursor_port, container, PortDir.IN),),
            children=(route_a, route_b, sink_a, sink_b),
            pool_bindings=(
                PoolBinding(f"self.{precursor_port}", "route_a.in"),
                PoolBinding(f"self.{precursor_port}", "route_b.in"),
                PoolBinding("route_a.out", "sink_a.in"),
                PoolBinding("route_b.out", "sink_b.in"),
            ),
            params=params or {},
        )

    def ground_truth(self, timeline: Timeline) -> tuple[float, float]:
        route_a = next((c for c in self.children if c.name == "route_a"), None)
        route_b = next((c for c in self.children if c.name == "route_b"), None)
        if (
            route_a is None
            or route_b is None
            or not route_a.resolved_ports
            or not route_b.resolved_ports
        ):
            raise SkeletonError(
                f"{self.name!r} has unresolved routes; call materialize() first"
            )
        mol_a = route_a.resolved_ports["out"]
        mol_b = route_b.resolved_ports["out"]
        return (final_amount(timeline, mol_a), final_amount(timeline, mol_b))


def sweep_conflict_frontier(
    build: Callable[[Dist[float], Dist[float]], Skeleton],
    seed: Seed,
    points: Sequence[tuple[float, float]],
    sim_cfg: SimConfig = SimConfig(),
) -> tuple[tuple[float, float], ...]:
    """Trace a :class:`ConflictCruxBlock` frontier (Q2's companion helper).

    ``build(kA, kB)`` returns a fresh :class:`Skeleton` wired with those two
    constant rates (typically re-building a ``ConflictCruxBlock.make(...,
    kA=Constant(kA), kB=Constant(kB))`` and its siblings); this sweeps every
    ``(kA, kB)`` pair in ``points`` and returns the achieved ``(prodA, prodB)``
    point for each — the frontier a scorer can later collapse to a scalar
    (``ground_truth`` itself returns only the single achieved point, per Q2).
    """
    return tuple(build(Constant(kA), Constant(kB)).oracle(seed, sim_cfg) for kA, kB in points)


@dataclass(frozen=True)
class PoissonSchedule:
    """Q3 opt-in arm: a Poisson process (rate ``lam``) over ``[0, horizon]``.

    Purely a reproducible-draw config — :func:`_draw_poisson_times` is the
    only thing that samples it, always via ``seed.child(ns).rng()``, so the
    drawn times are byte-identical for a given seed + namespace.
    """

    lam: float
    horizon: float


def _draw_poisson_times(seed: Seed, schedule: PoissonSchedule) -> tuple[float, ...]:
    """Reproducible discrete insult times: exponential inter-arrivals summed to
    ``schedule.horizon``, drawn from ``seed.rng()`` (byte-identical per seed)."""
    rng = seed.rng()
    times: list[float] = []
    t = 0.0
    while True:
        t += float(rng.exponential(1.0 / schedule.lam))
        if t > schedule.horizon:
            break
        times.append(t)
    return tuple(times)


@dataclass(frozen=True)
class PressureBlock(SinkBlock):
    """PRESSURE: a ``SinkBlock``-shaped boundary drain on a ``stressed`` pool.

    Q3 default arm: constant-magnitude drain — the same one ``ReactionBlock``
    code path as any other ``SinkBlock`` (``rate`` is the drain magnitude).
    Q3 opt-in arm: ``poisson``, when set, additionally draws a reproducible
    discrete insult-time schedule from ``seed.child(ns).rng()`` at ``realize``
    time and caches it onto ``insult_times`` (the same frozen-dataclass
    escape hatch :meth:`Skeleton.materialize` uses for derived state) —
    metadata for a future conditional-policy consumer; it does not itself
    perturb the constant mass-action rate fed to ``ReactionImpl`` (rate
    modulation is the S2/F015 seam, out of scope here).
    """

    poisson: Optional[PoissonSchedule] = None
    insult_times: tuple[float, ...] = ()

    @classmethod
    def make(
        cls,
        name: str,
        *,
        port: str = "stressed",
        container: Optional[NodeId] = None,
        rate: Optional[Dist[float]] = None,
        poisson: Optional[PoissonSchedule] = None,
        params: Optional[Tags] = None,
    ) -> "PressureBlock":
        """``rate`` is the drain magnitude (constant, Q3 default arm)."""
        return cls(
            name=name,
            role=Role.PRESSURE,
            ports=(Port(port, container, PortDir.IN),),
            rate=rate if rate is not None else Constant(1.0),
            poisson=poisson,
            params=params or {},
        )

    def realize(self, seed: Seed, ns: str, bound: Mapping[str, MoleculeImpl]) -> Fragment:
        fragment = super().realize(seed, ns, bound)
        if self.poisson is not None:
            times = _draw_poisson_times(seed.child(ns), self.poisson)
            object.__setattr__(self, "insult_times", times)
        return fragment


# ═══════════════════════════════════════════════════════════════════════════
# F015 S2 (M38.3) — pattern-blocks: one modifier-bearing reaction, not a
# multi-reaction idiom.
# ═══════════════════════════════════════════════════════════════════════════


def _modulator_fragment(
    ports: tuple[Port, ...],
    modifier_port: str,
    bound: Mapping[str, MoleculeImpl],
    stoich: Mapping[str, float],
    rate: float,
    modulation: Modulation,
    ns: str,
) -> Fragment:
    """Shared ``realize`` body for the S2 modulation blocks.

    Every port except ``modifier_port`` becomes a reactant (``IN``) or product
    (``OUT``) of ONE reaction, exactly like :meth:`ReactionBlock.realize`;
    ``modifier_port`` resolves to a non-consumed modifier species instead —
    attached via ``ReactionImpl.modifiers`` with the given ``modulation``, never
    added to ``reactants``/``products`` (so it never enters the F012 balance
    gate, per ``bio.conservation``).
    """
    reactants: dict[MoleculeImpl, float] = {}
    products: dict[MoleculeImpl, float] = {}
    for port in ports:
        if port.name == modifier_port:
            continue
        molecule = bound[port.name]
        coef = stoich.get(port.name, 1.0)
        if port.direction is PortDir.IN:
            reactants[molecule] = coef
        else:
            products[molecule] = coef

    modifier_mol = bound[modifier_port]
    rxn_id = f"{ns}/rxn"
    container = _container_of(ports)
    reaction = cast(
        ReactionImpl,
        mk.R(rxn_id, reactants, products, modifiers={modifier_mol: modulation}, rate=rate),
    )
    molecules = {m.name: m for m in list(reactants) + list(products) + [modifier_mol]}
    return Fragment(
        molecules=molecules,
        reactions={rxn_id: reaction},
        provenance=(Provenance(rxn_id, container),),
    )


@dataclass(frozen=True)
class SignalingBlock(SkeletonBlock):
    """SIGNALING: a control wire — ONE ``in -> out`` reaction, its rate scaled
    by a linear ``"activator"`` or ``"inhibitor"`` ``modifier`` species
    (``kind=`` selects which; params ``a``/``Ki`` are ``Dist`` holes sampled
    with the block's own namespaced seed). Replaces the old multi-reaction
    "signaling cascade" idiom with one attachment.
    """

    rate: Dist[float] = field(default_factory=lambda: Constant(1.0))
    kind: str = "activator"  # "activator" or "inhibitor" (Modulation.kind)
    a: Dist[float] = field(default_factory=lambda: Constant(1.0))
    Ki: Dist[float] = field(default_factory=lambda: Constant(1.0))
    modifier_port: str = "modifier"

    @classmethod
    def make(
        cls,
        name: str,
        *,
        in_port: str = "in",
        out_port: str = "out",
        modifier_port: str = "modifier",
        container: Optional[NodeId] = None,
        rate: Optional[Dist[float]] = None,
        kind: str = "activator",
        a: Optional[Dist[float]] = None,
        Ki: Optional[Dist[float]] = None,
        params: Optional[Tags] = None,
    ) -> "SignalingBlock":
        if kind not in ("activator", "inhibitor"):
            raise SkeletonError(f"SignalingBlock kind must be 'activator' or 'inhibitor', got {kind!r}")
        return cls(
            name=name,
            role=Role.SIGNALING,
            ports=(
                Port(in_port, container, PortDir.IN),
                Port(out_port, container, PortDir.OUT),
                Port(modifier_port, container, PortDir.IN),
            ),
            rate=rate if rate is not None else Constant(1.0),
            kind=kind,
            a=a if a is not None else Constant(1.0),
            Ki=Ki if Ki is not None else Constant(1.0),
            modifier_port=modifier_port,
            params=params or {},
        )

    def realize(self, seed: Seed, ns: str, bound: Mapping[str, MoleculeImpl]) -> Fragment:
        rate = self.rate.sample(seed.child("rate"))
        if self.kind == "activator":
            modulation = Modulation(kind="activator", a=self.a.sample(seed.child("a")))
        else:
            modulation = Modulation(kind="inhibitor", Ki=self.Ki.sample(seed.child("Ki")))
        return _modulator_fragment(self.ports, self.modifier_port, bound, {}, rate, modulation, ns)


@dataclass(frozen=True)
class InhibitionBlock(SkeletonBlock):
    """SIGNALING (inhibitory config): ONE ``in -> out`` reaction, its rate
    divided by a linear ``"inhibitor"`` ``modifier`` — ``1 / (1 + [I] / Ki)``.
    A dedicated, single-purpose config of the same attachment
    :class:`SignalingBlock` generalizes (``kind="inhibitor"``).
    """

    rate: Dist[float] = field(default_factory=lambda: Constant(1.0))
    Ki: Dist[float] = field(default_factory=lambda: Constant(1.0))
    modifier_port: str = "modifier"

    @classmethod
    def make(
        cls,
        name: str,
        *,
        in_port: str = "in",
        out_port: str = "out",
        modifier_port: str = "modifier",
        container: Optional[NodeId] = None,
        rate: Optional[Dist[float]] = None,
        Ki: Optional[Dist[float]] = None,
        params: Optional[Tags] = None,
    ) -> "InhibitionBlock":
        return cls(
            name=name,
            role=Role.SIGNALING,
            ports=(
                Port(in_port, container, PortDir.IN),
                Port(out_port, container, PortDir.OUT),
                Port(modifier_port, container, PortDir.IN),
            ),
            rate=rate if rate is not None else Constant(1.0),
            Ki=Ki if Ki is not None else Constant(1.0),
            modifier_port=modifier_port,
            params=params or {},
        )

    def realize(self, seed: Seed, ns: str, bound: Mapping[str, MoleculeImpl]) -> Fragment:
        rate = self.rate.sample(seed.child("rate"))
        modulation = Modulation(kind="inhibitor", Ki=self.Ki.sample(seed.child("Ki")))
        return _modulator_fragment(self.ports, self.modifier_port, bound, {}, rate, modulation, ns)


@dataclass(frozen=True)
class EnzymeBlock(SkeletonBlock):
    """SIGNALING (catalytic config): ONE ``substrate -> product`` reaction, its
    rate scaled by a saturating ``"michaelis"`` ``enzyme`` modifier —
    ``Vmax * [enzyme] / (K + [enzyme])`` (hyperbolic in the enzyme's OWN
    concentration, the same convention every modulator kind uses). No ``ES``
    intermediate pool — one reaction replaces the old
    ``S + E -> ES -> P + E`` mechanism idiom.
    """

    rate: Dist[float] = field(default_factory=lambda: Constant(1.0))
    Vmax: Dist[float] = field(default_factory=lambda: Constant(1.0))
    K: Dist[float] = field(default_factory=lambda: Constant(1.0))
    modifier_port: str = "enzyme"

    @classmethod
    def make(
        cls,
        name: str,
        *,
        substrate_port: str = "substrate",
        product_port: str = "product",
        modifier_port: str = "enzyme",
        container: Optional[NodeId] = None,
        rate: Optional[Dist[float]] = None,
        Vmax: Optional[Dist[float]] = None,
        K: Optional[Dist[float]] = None,
        params: Optional[Tags] = None,
    ) -> "EnzymeBlock":
        return cls(
            name=name,
            role=Role.SIGNALING,
            ports=(
                Port(substrate_port, container, PortDir.IN),
                Port(product_port, container, PortDir.OUT),
                Port(modifier_port, container, PortDir.IN),
            ),
            rate=rate if rate is not None else Constant(1.0),
            Vmax=Vmax if Vmax is not None else Constant(1.0),
            K=K if K is not None else Constant(1.0),
            modifier_port=modifier_port,
            params=params or {},
        )

    def realize(self, seed: Seed, ns: str, bound: Mapping[str, MoleculeImpl]) -> Fragment:
        rate = self.rate.sample(seed.child("rate"))
        modulation = Modulation(
            kind="michaelis",
            Vmax=self.Vmax.sample(seed.child("Vmax")),
            K=self.K.sample(seed.child("K")),
        )
        return _modulator_fragment(self.ports, self.modifier_port, bound, {}, rate, modulation, ns)


@dataclass(frozen=True)
class CooperativeBindingBlock(SkeletonBlock):
    """SIGNALING (cooperative config): ONE ``in -> out`` reaction, its rate
    scaled by a Hill-form ``"hill"`` ``modifier`` — ``Vmax * [modifier]**n /
    (K**n + [modifier]**n)``. Higher cooperativity ``n`` sharpens the response
    into a step around ``K`` (vs the hyperbolic response at ``n=1``, the
    :class:`EnzymeBlock` degenerate case).
    """

    rate: Dist[float] = field(default_factory=lambda: Constant(1.0))
    Vmax: Dist[float] = field(default_factory=lambda: Constant(1.0))
    K: Dist[float] = field(default_factory=lambda: Constant(1.0))
    n: Dist[float] = field(default_factory=lambda: Constant(2.0))
    modifier_port: str = "modifier"

    @classmethod
    def make(
        cls,
        name: str,
        *,
        in_port: str = "in",
        out_port: str = "out",
        modifier_port: str = "modifier",
        container: Optional[NodeId] = None,
        rate: Optional[Dist[float]] = None,
        Vmax: Optional[Dist[float]] = None,
        K: Optional[Dist[float]] = None,
        n: Optional[Dist[float]] = None,
        params: Optional[Tags] = None,
    ) -> "CooperativeBindingBlock":
        return cls(
            name=name,
            role=Role.SIGNALING,
            ports=(
                Port(in_port, container, PortDir.IN),
                Port(out_port, container, PortDir.OUT),
                Port(modifier_port, container, PortDir.IN),
            ),
            rate=rate if rate is not None else Constant(1.0),
            Vmax=Vmax if Vmax is not None else Constant(1.0),
            K=K if K is not None else Constant(1.0),
            n=n if n is not None else Constant(2.0),
            modifier_port=modifier_port,
            params=params or {},
        )

    def realize(self, seed: Seed, ns: str, bound: Mapping[str, MoleculeImpl]) -> Fragment:
        rate = self.rate.sample(seed.child("rate"))
        modulation = Modulation(
            kind="hill",
            Vmax=self.Vmax.sample(seed.child("Vmax")),
            K=self.K.sample(seed.child("K")),
            n=self.n.sample(seed.child("n")),
        )
        return _modulator_fragment(self.ports, self.modifier_port, bound, {}, rate, modulation, ns)
