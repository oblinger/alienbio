"""Population: count-based rate laws on the compartment ``multiplicity`` axis (F017).

A population is a compartment with a large ``multiplicity`` (F012/M37.1 already stores
this per compartment; ``amount = multiplicity · volume · concentration``). Until F017,
nothing ever WROTE ``multiplicity`` during a run — this module is the simulator's
FIRST multiplicity-update path (the F012 Q3 count-based rate-law content the M37.2
``_desired_extent`` seam was built to accept), realized as a **separate population
pass** (skeleton decision Q1=A) rather than threaded through the per-molecule H4
rationing loop: the multiplicity axis is a per-compartment *scalar*, not a pool, so
forcing it through the reaction competition machinery would need a fake species for
no gain.

Three typed, declarative rate-law records (frozen — no callable/arbitrary-Python rate
laws, matching the F012/S6 posture):

- :class:`PerCapitaGrowth` — ``extent = k · N · [resource] · dt`` (Q3=A: an explicit
  resource-consumption stoichiometry ``stoich`` on the record; a growth of ``ΔN``
  draws ``stoich · ΔN`` resource AMOUNT from a named pool, exactly like a reaction's
  reactant side). Bilinear in population size and resource concentration, so growth
  self-limits as the resource pool draws down — logistic boundedness from nutrient
  limitation, no arbitrary cap (F012 D-f). Q4=A (born-full): new instances are created
  at the parent's per-instance concentrations (except a resource drawn from the
  growing compartment itself, which the newborns share rather than copy), so
  ``stoich`` must be declared to fund the FULL biomass of each new instance or the
  F012 amount-canary (:func:`alienbio.bio.conservation.total_quantity`) fires —
  matter created from nothing.
- :class:`PerCapitaDeath` — ``extent = k · N · dt``; optionally releases biomass back
  to a named pool (the reverse of growth's draw).
- :class:`CountFlow` — the size-class transition primitive (Q2=A): an inter-compartment
  count flow that moves ``Δmultiplicity`` from ``origin`` to ``dest`` at
  ``rate_constant · N_origin`` (a maturation edge, parallel in shape to
  :class:`~alienbio.bio.flow.TransportFlux` but on the multiplicity axis rather than a
  molecule pool). Conserves headcount exactly: the SAME extent leaves ``origin`` and
  enters ``dest``.

Every law's :meth:`PopulationLaw.contribute` reads ONLY the frozen start-of-step state
(order-independent, H4-flavored) and ACCUMULATES its multiplicity deltas, molecule AMOUNT
deltas and content :class:`Carry` records into caller-supplied containers rather than
mutating state directly — so several laws can affect the same compartment/pool in one step
without one clobbering another's read of the frozen baseline
(:func:`apply_population_laws` applies the accumulated totals once, after every law has
contributed, conserving amount wherever a law moves content).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, FrozenSet, List, Optional, Sequence, TYPE_CHECKING

from .rate_expr import ROUNDING_FLOOR

if TYPE_CHECKING:
    from .world_state import WorldStateImpl

# Type aliases
MoleculeId = int
CompartmentId = int

#: Accumulator for Δmultiplicity, keyed by compartment — populated by every law's
#: :meth:`PopulationLaw.contribute`, applied once by the population pass.
MultDelta = Dict[CompartmentId, float]

#: Accumulator for Δamount (``multiplicity · volume · concentration``, NOT a
#: concentration), keyed by ``(compartment, molecule)`` — the resource draw/release side
#: of growth/death, applied once alongside ``MultDelta``.
MolDelta = Dict[tuple[CompartmentId, MoleculeId], float]


@dataclass(frozen=True)
class Carry:
    """``count`` instances' contents, read per instance off ``src`` in the state the
    pass writes (``volume · concentration``, after the reaction and flow passes).

    - ``removes``: the contents leave ``src`` (a death, or a :class:`CountFlow`
      departure); otherwise they are copied (a birth: born-full).
    - ``dst``: where the contents land; ``None`` means they leave the world (death).
    - ``skip``: molecules NOT copied by a birth — a growth law's own resource when it
      draws from its own compartment: the newborns share the pool they are funded from,
      so the drawn resource is not also replicated (module-doc finding, 2026-10).

    A carry scales with its law's ration like every other delta.
    """

    src: CompartmentId
    dst: Optional[CompartmentId]
    count: float
    removes: bool
    skip: FrozenSet[MoleculeId] = frozenset()


#: Accumulator for :class:`Carry` records.
Carries = List[Carry]


class PopulationLaw(ABC):
    """Abstract base for a typed count-based rate-law record (multiplicity axis).

    Subclasses:
    - PerCapitaGrowth: resource-coupled per-capita growth
    - PerCapitaDeath: per-capita death, with an optional biomass release
    - CountFlow: size-class maturation (Δmultiplicity origin -> dest)
    """

    __slots__ = ("_name",)

    def __init__(self, name: str = "") -> None:
        self._name = name

    @property
    def name(self) -> str:
        """Human-readable name."""
        return self._name

    @abstractmethod
    def contribute(
        self,
        frozen: "WorldStateImpl",
        dt: float,
        mult_delta: MultDelta,
        mol_delta: MolDelta,
        carries: Carries,
    ) -> None:
        """Read ``frozen`` (start-of-step state) and ACCUMULATE this law's
        Δmultiplicity, Δamount and content :class:`Carry` records into the
        caller-supplied containers.

        Never mutates ``frozen``, and never reads the containers back — every law
        is a pure function of the frozen state, so order among laws does not matter.
        """
        ...

    @abstractmethod
    def attributes(self) -> Dict[str, Any]:
        """Semantic content for serialization."""
        ...


class PerCapitaGrowth(PopulationLaw):
    """Resource-coupled per-capita growth (F017 Q3=A/Q4=A).

    ``extent = rate_constant · N_compartment · [resource]_resource_compartment · dt``,
    floored at 0 (a growth law never itself causes shrinkage — use
    :class:`PerCapitaDeath` for that). Bilinear in population size and resource
    concentration: as the resource pool draws down, growth self-limits toward 0 —
    logistic boundedness from nutrient limitation, with no separate governor.

    The resource draw is rationed exactly like a reaction's reactant (see
    :class:`~alienbio.bio.flow.TransportFlux`'s amount-rationing precedent): if
    ``stoich · extent`` exceeds the resource pool's available AMOUNT, the extent is
    scaled down so the pool never goes negative. ``stoich == 0.0`` (the uncoupled
    config) skips the draw entirely — growth still happens, but nothing funds the new
    instances' biomass, so the F012 amount-canary (:func:`alienbio.bio.conservation.
    total_quantity`) fires: matter created from nothing. This is deliberate — it is
    the negative half of F017's conservation red-then-green test.
    """

    __slots__ = ("_compartment", "_resource_compartment", "_resource", "_stoich", "_rate_constant")

    def __init__(
        self,
        compartment: CompartmentId,
        resource_compartment: CompartmentId,
        resource: MoleculeId,
        stoich: float,
        rate_constant: float = 1.0,
        name: str = "",
    ) -> None:
        """Initialize a resource-coupled per-capita growth law.

        Args:
            compartment: the population compartment whose multiplicity grows
            resource_compartment: the compartment holding the resource pool (may equal
                ``compartment``)
            resource: molecule id of the resource
            stoich: resource AMOUNT consumed per new instance (``ΔN``); ``0.0`` means
                uncoupled (no draw) — deliberately leaky, see class docstring
            rate_constant: ``k``
            name: human-readable name
        """
        if not name:
            name = f"growth_at_{compartment}"
        super().__init__(name)
        self._compartment = compartment
        self._resource_compartment = resource_compartment
        self._resource = resource
        self._stoich = stoich
        self._rate_constant = rate_constant

    @property
    def compartment(self) -> CompartmentId:
        """The population compartment whose multiplicity grows."""
        return self._compartment

    @property
    def resource_compartment(self) -> CompartmentId:
        """The compartment holding the resource pool."""
        return self._resource_compartment

    @property
    def resource(self) -> MoleculeId:
        """Molecule id of the resource."""
        return self._resource

    @property
    def stoich(self) -> float:
        """Resource AMOUNT consumed per new instance."""
        return self._stoich

    @property
    def rate_constant(self) -> float:
        """``k``."""
        return self._rate_constant

    def compute_extent(self, frozen: "WorldStateImpl") -> float:
        """Raw (unrationed) Δmultiplicity from the frozen state, floored at 0."""
        n = frozen.get_multiplicity(self._compartment)
        conc = frozen.get(self._resource_compartment, self._resource)
        return max(0.0, self._rate_constant * n * conc)

    def contribute(
        self,
        frozen: "WorldStateImpl",
        dt: float,
        mult_delta: MultDelta,
        mol_delta: MolDelta,
        carries: Carries,
    ) -> None:
        raw = self.compute_extent(frozen) * dt
        if raw <= 0.0:
            return

        if self._stoich > 0.0:
            needed = self._stoich * raw
            available = frozen.amount(self._resource_compartment, self._resource)
            if needed > available:
                scale = available / needed if needed > 0.0 else 0.0
                raw *= scale
            if raw <= 0.0:
                return

        mult_delta[self._compartment] = mult_delta.get(self._compartment, 0.0) + raw

        # Born-full: the newborns copy the compartment's per-instance contents —
        # except, when the resource is drawn from this same compartment, the
        # resource itself: the newborns share the pool that funds them, so
        # N = 2, [R] = 1, stoich = 1 growing by 0.2 ends at R amount 1.8 (it was
        # 1.98: the draw was a concentration on the old count, and the newborns
        # then held the post-draw concentration).
        self_draw = self._stoich > 0.0 and self._resource_compartment == self._compartment
        carries.append(
            Carry(
                src=self._compartment,
                dst=self._compartment,
                count=raw,
                removes=False,
                skip=frozenset({self._resource}) if self_draw else frozenset(),
            )
        )

        if self._stoich > 0.0:
            key = (self._resource_compartment, self._resource)
            mol_delta[key] = mol_delta.get(key, 0.0) - self._stoich * raw

    def attributes(self) -> Dict[str, Any]:
        """Semantic content for serialization."""
        return {
            "type": "per_capita_growth",
            "name": self._name,
            "compartment": self._compartment,
            "resource_compartment": self._resource_compartment,
            "resource": self._resource,
            "stoich": self._stoich,
            "rate_constant": self._rate_constant,
        }

    def __repr__(self) -> str:
        """Full representation."""
        return (
            f"PerCapitaGrowth(compartment={self._compartment}, "
            f"resource_compartment={self._resource_compartment}, resource={self._resource}, "
            f"stoich={self._stoich}, rate_constant={self._rate_constant})"
        )

    def __str__(self) -> str:
        """Short representation."""
        return f"PerCapitaGrowth({self._name})"


class PerCapitaDeath(PopulationLaw):
    """Per-capita death: ``extent = rate_constant · N · dt``, floored at 0 and clamped
    so a compartment's multiplicity never goes negative.

    Optionally releases biomass back to a named pool (the reverse of
    :class:`PerCapitaGrowth`'s draw) — ``release_stoich · extent`` resource AMOUNT is
    added to ``(release_compartment, release_resource)`` when all three are supplied;
    absent (the default), death is a pure multiplicity shrink with no release.
    """

    __slots__ = (
        "_compartment",
        "_rate_constant",
        "_release_compartment",
        "_release_resource",
        "_release_stoich",
    )

    def __init__(
        self,
        compartment: CompartmentId,
        rate_constant: float = 1.0,
        release_compartment: Optional[CompartmentId] = None,
        release_resource: Optional[MoleculeId] = None,
        release_stoich: float = 0.0,
        name: str = "",
    ) -> None:
        """Initialize a per-capita death law.

        Args:
            compartment: the population compartment whose multiplicity shrinks
            rate_constant: ``k``
            release_compartment: optional compartment receiving released biomass
            release_resource: optional molecule id receiving released biomass
            release_stoich: resource AMOUNT released per death, when both
                ``release_compartment``/``release_resource`` are set
            name: human-readable name
        """
        if not name:
            name = f"death_at_{compartment}"
        super().__init__(name)
        self._compartment = compartment
        self._rate_constant = rate_constant
        self._release_compartment = release_compartment
        self._release_resource = release_resource
        self._release_stoich = release_stoich

    @property
    def compartment(self) -> CompartmentId:
        """The population compartment whose multiplicity shrinks."""
        return self._compartment

    @property
    def rate_constant(self) -> float:
        """``k``."""
        return self._rate_constant

    @property
    def release_compartment(self) -> Optional[CompartmentId]:
        """Optional compartment receiving released biomass."""
        return self._release_compartment

    @property
    def release_resource(self) -> Optional[MoleculeId]:
        """Optional molecule id receiving released biomass."""
        return self._release_resource

    @property
    def release_stoich(self) -> float:
        """Resource AMOUNT released per death."""
        return self._release_stoich

    def compute_extent(self, frozen: "WorldStateImpl") -> float:
        """Raw (unrationed) Δmultiplicity magnitude from the frozen state, floored at 0."""
        n = frozen.get_multiplicity(self._compartment)
        return max(0.0, self._rate_constant * n)

    def contribute(
        self,
        frozen: "WorldStateImpl",
        dt: float,
        mult_delta: MultDelta,
        mol_delta: MolDelta,
        carries: Carries,
    ) -> None:
        raw = self.compute_extent(frozen) * dt
        n = frozen.get_multiplicity(self._compartment)
        raw = min(raw, n)  # never kill more than exist
        if raw <= 0.0:
            return

        mult_delta[self._compartment] = mult_delta.get(self._compartment, 0.0) - raw
        # The dead take their contents out of the world (die-full).
        carries.append(Carry(src=self._compartment, dst=None, count=raw, removes=True))

        if (
            self._release_compartment is not None
            and self._release_resource is not None
            and self._release_stoich > 0.0
        ):
            # Written to the named release compartment. Where that compartment
            # ends the step at multiplicity × volume 0 (empty at the start, or
            # emptied by this step's own deaths), :func:`apply_population_laws`
            # moves the release into the dying compartment — decided against
            # the post-pass sizes, not this frozen read (T088 leftovers).
            key = (self._release_compartment, self._release_resource)
            mol_delta[key] = mol_delta.get(key, 0.0) + self._release_stoich * raw

    def attributes(self) -> Dict[str, Any]:
        """Semantic content for serialization."""
        return {
            "type": "per_capita_death",
            "name": self._name,
            "compartment": self._compartment,
            "rate_constant": self._rate_constant,
            "release_compartment": self._release_compartment,
            "release_resource": self._release_resource,
            "release_stoich": self._release_stoich,
        }

    def __repr__(self) -> str:
        """Full representation."""
        return f"PerCapitaDeath(compartment={self._compartment}, rate_constant={self._rate_constant})"

    def __str__(self) -> str:
        """Short representation."""
        return f"PerCapitaDeath({self._name})"


class CountFlow(PopulationLaw):
    """Size-class transition (F017 Q2=A): moves Δmultiplicity ``origin -> dest`` at
    ``rate_constant · N_origin``, floored at 0 and clamped so ``origin`` never goes
    negative. A maturation edge — the same extent leaves ``origin`` and enters
    ``dest``, so headcount is conserved exactly (parallel in shape to
    :class:`~alienbio.bio.flow.TransportFlux`, but on the multiplicity axis rather
    than a molecule pool).
    """

    __slots__ = ("_origin", "_dest", "_rate_constant")

    def __init__(
        self,
        origin: CompartmentId,
        dest: CompartmentId,
        rate_constant: float = 1.0,
        name: str = "",
    ) -> None:
        """Initialize a count flow.

        Args:
            origin: the compartment this flow moves multiplicity OUT OF
            dest: the compartment this flow moves multiplicity INTO
            rate_constant: ``k``
            name: human-readable name
        """
        if not name:
            name = f"count_flow_{origin}_to_{dest}"
        super().__init__(name)
        self._origin = origin
        self._dest = dest
        self._rate_constant = rate_constant

    @property
    def origin(self) -> CompartmentId:
        """The compartment this flow moves multiplicity OUT OF."""
        return self._origin

    @property
    def dest(self) -> CompartmentId:
        """The compartment this flow moves multiplicity INTO."""
        return self._dest

    @property
    def rate_constant(self) -> float:
        """``k``."""
        return self._rate_constant

    def compute_extent(self, frozen: "WorldStateImpl") -> float:
        """Raw (unrationed) Δmultiplicity from the frozen state, floored at 0."""
        n = frozen.get_multiplicity(self._origin)
        return max(0.0, self._rate_constant * n)

    def contribute(
        self,
        frozen: "WorldStateImpl",
        dt: float,
        mult_delta: MultDelta,
        mol_delta: MolDelta,
        carries: Carries,
    ) -> None:
        raw = self.compute_extent(frozen) * dt
        n = frozen.get_multiplicity(self._origin)
        raw = min(raw, n)  # never move more than exist at origin
        if raw <= 0.0:
            return

        mult_delta[self._origin] = mult_delta.get(self._origin, 0.0) - raw
        mult_delta[self._dest] = mult_delta.get(self._dest, 0.0) + raw
        # The movers take their own contents with them; ``dest`` ends at the
        # amount-weighted mix (they used to take on dest's concentration: ten
        # instances at [X] = 2 moving one into an empty class went 20 -> 18).
        carries.append(Carry(src=self._origin, dst=self._dest, count=raw, removes=True))

    def attributes(self) -> Dict[str, Any]:
        """Semantic content for serialization."""
        return {
            "type": "count_flow",
            "name": self._name,
            "origin": self._origin,
            "dest": self._dest,
            "rate_constant": self._rate_constant,
        }

    def __repr__(self) -> str:
        """Full representation."""
        return (
            f"CountFlow(origin={self._origin}, dest={self._dest}, "
            f"rate_constant={self._rate_constant})"
        )

    def __str__(self) -> str:
        """Short representation."""
        return f"CountFlow({self._name})"




def apply_population_laws(
    laws: "Sequence[PopulationLaw]",
    new_state: "WorldStateImpl",
    frozen: "WorldStateImpl",
    dt: float,
) -> None:
    """Apply every law's deltas together, rationing the SUMMED demand on each
    drained key (T051 box 4 / T053) and conserving molecule amount wherever a
    law moves content (module-doc finding, 2026-10).

    Each law is asked for its deltas against the frozen start-of-step state, so
    order among laws does not matter. A law's ``contribute`` already limits its
    own draw to what the frozen state holds, but two laws drawing the same pool
    each saw the whole pool: two deaths on one compartment took multiplicity to
    −10 in a step, and the shipped microcosm's two growth laws both draw
    ``pond/food``. So the per-law contributions are collected separately, the
    negative contributions to each key are summed, and every law that draws a
    key short of its demand is scaled by the tightest ratio over the keys it
    draws — the single-pass min-ratio scheme
    :meth:`~alienbio.bio.world_simulator.WorldSimulatorImpl._apply_reactions`
    already uses for shared reactants. A law's whole contribution scales
    together, so a growth law whose resource draw is cut grows by the same
    fraction less.

    Multiplicity is rationed first; a molecule draw is then rationed against
    the pool LESS what the (multiplicity-rationed) deaths and departures carry
    out of it, so a draw and a death on one pool cannot together over-draw it.

    Molecule changes are AMOUNTS. A key whose amount no law touches explicitly,
    in a compartment that receives no movers and whose births copy it, keeps
    its concentration (born-full / die-full: the count changes, the
    per-instance contents do not). Every other key is accounted as an amount —
    the pool before the pass, plus what births copy, minus what deaths and
    departures carry out, plus what arrivals carry in, plus the draws and
    releases — and divided by the compartment's new ``multiplicity · volume``.
    A compartment left at size 0 holds no amount, so anything landing there is
    lost; a death releasing into a compartment that ENDS the step at size 0
    (read off the multiplicities this pass writes, not the frozen state — a
    release compartment its own deaths empty this step counts) sends it to the
    dying compartment instead, and when that one ends empty too the release
    leaves the world with the dead's contents.

    Same-pass gains are not available to same-pass draws (T088 leftovers,
    deliberate): a draw is rationed against the pool as the earlier passes
    left it, never against what a death releases or a birth copies in this
    pass — the reaction pass's rule for its own products. A pool emptied by
    a draw and refilled by a release in one step ends at the release, and the
    draw that wanted more gets it next step.
    """
    per_law: list[tuple[MultDelta, MolDelta, Carries]] = []
    for law in laws:
        mult: MultDelta = {}
        mol: MolDelta = {}
        carries: Carries = []
        law.contribute(frozen, dt, mult, mol, carries)
        per_law.append((mult, mol, carries))

    # Phase 1 — multiplicity. Demands come off the frozen state; the ration is
    # against the pool as the reaction and flow passes LEFT it in
    # ``new_state``, so the three passes together never over-draw a pool.
    mult_demand: MultDelta = {}
    for mult, _, _ in per_law:
        for comp, delta in mult.items():
            if delta < 0.0:
                mult_demand[comp] = mult_demand.get(comp, 0.0) - delta
    mult_ratio = {
        comp: (
            min(1.0, max(0.0, new_state.get_multiplicity(comp)) / dem) if dem > 0.0 else 1.0
        )
        for comp, dem in mult_demand.items()
    }
    mult_scale: list[float] = []
    for mult, _, _ in per_law:
        scale = 1.0
        for comp, delta in mult.items():
            if delta < 0.0:
                scale = min(scale, mult_ratio[comp])
        mult_scale.append(scale)

    num_molecules = new_state.num_molecules

    def per_instance(comp: CompartmentId, mol_id: MoleculeId) -> float:
        return new_state.get_volume(comp) * new_state.get(comp, mol_id)

    # Phase 2 — molecule draws, against the pool less what leaves with the
    # dead and the departing (an upper bound on it: a law's final scale is at
    # most its multiplicity scale).
    outflow: Dict[CompartmentId, float] = {}
    for (_, _, carries), scale in zip(per_law, mult_scale):
        for carry in carries:
            if carry.removes:
                outflow[carry.src] = outflow.get(carry.src, 0.0) + carry.count * scale
    mol_demand: MolDelta = {}
    for _, mol, _ in per_law:
        for key, delta in mol.items():
            if delta < 0.0:
                mol_demand[key] = mol_demand.get(key, 0.0) - delta
    mol_ratio: Dict[tuple[CompartmentId, MoleculeId], float] = {}
    for (comp, mol_id), dem in mol_demand.items():
        avail = new_state.amount(comp, mol_id) - outflow.get(comp, 0.0) * per_instance(
            comp, mol_id
        )
        mol_ratio[(comp, mol_id)] = min(1.0, max(0.0, avail) / dem) if dem > 0.0 else 1.0

    # Each law's final scale: its multiplicity scale, tightened by every
    # molecule key it draws.
    final_scale: list[float] = []
    for (_, mol, _), scale in zip(per_law, mult_scale):
        for key, delta in mol.items():
            if delta < 0.0:
                scale = min(scale, mol_ratio[key])
        final_scale.append(scale)

    # The multiplicities the pass will write, so a death's release can be
    # placed against the sizes the step ENDS at.
    mult_delta: MultDelta = {}
    for (mult, _, _), scale in zip(per_law, final_scale):
        for comp, delta in mult.items():
            mult_delta[comp] = mult_delta.get(comp, 0.0) + delta * scale

    def _post_mult(comp: CompartmentId) -> float:
        value = new_state.get_multiplicity(comp) + mult_delta.get(comp, 0.0)
        return 0.0 if -ROUNDING_FLOOR < value < 0.0 else value

    def _ends_empty(comp: CompartmentId) -> bool:
        return _post_mult(comp) * new_state.get_volume(comp) <= 0.0

    # Accumulate the scaled deltas.
    mol_delta: MolDelta = {}
    scaled_carries: list[Carry] = []
    for law, (mult, mol, carries), scale in zip(laws, per_law, final_scale):
        for key, delta in mol.items():
            if (
                delta > 0.0
                and isinstance(law, PerCapitaDeath)
                and key == (law.release_compartment, law.release_resource)
                and _ends_empty(key[0])
            ):
                # A release compartment that ends the step at size 0 cannot
                # hold an amount: the release stays in the dying compartment.
                # When that one ends empty too (the population died out this
                # step) the release leaves the world with the dead's contents.
                key = (law.compartment, key[1])
            mol_delta[key] = mol_delta.get(key, 0.0) + delta * scale
        for carry in carries:
            if scale != 1.0:
                carry = Carry(carry.src, carry.dst, carry.count * scale, carry.removes, carry.skip)
            scaled_carries.append(carry)

    # Which keys need amount accounting: explicit deltas, every molecule of a
    # compartment receiving movers, and a birth's skipped molecules.
    accounted: set[tuple[CompartmentId, MoleculeId]] = set(mol_delta)
    for carry in scaled_carries:
        if carry.dst is not None and carry.dst != carry.src:
            accounted.update((carry.dst, m) for m in range(num_molecules))
        if not carry.removes:
            accounted.update((carry.src, m) for m in carry.skip)

    amounts: Dict[tuple[CompartmentId, MoleculeId], float] = {}
    if accounted:
        # Read everything off the pre-pass state before writing anything.
        amounts = {key: new_state.amount(*key) for key in accounted}
        for carry in scaled_carries:
            for m in range(num_molecules):
                q = carry.count * per_instance(carry.src, m)
                if carry.removes:
                    if (carry.src, m) in amounts:
                        amounts[(carry.src, m)] -= q
                    if carry.dst is not None and (carry.dst, m) in amounts:
                        amounts[(carry.dst, m)] += q
                elif m not in carry.skip and (carry.src, m) in amounts:
                    amounts[(carry.src, m)] += q
        for key, delta in mol_delta.items():
            amounts[key] += delta

    for comp, delta in mult_delta.items():
        value = new_state.get_multiplicity(comp) + delta
        if -ROUNDING_FLOOR < value < 0.0:
            value = 0.0
        new_state.set_multiplicity(comp, value)
    for (comp, mol_id), amount in amounts.items():
        size = new_state.get_multiplicity(comp) * new_state.get_volume(comp)
        if size <= 0.0:
            continue  # holds no amount; its concentration is moot
        value = amount / size
        # Every draw is rationed, so exact arithmetic never goes below zero;
        # float rounding can leave -1e-16 — snap it, as the reaction pass does
        # (found by `bio report`, 2026-08-30).
        if -ROUNDING_FLOOR < value < 0.0:
            value = 0.0
        new_state.set(comp, mol_id, value)
