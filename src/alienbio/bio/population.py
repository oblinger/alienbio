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
  at the parent's per-instance concentrations (nothing here touches concentrations
  directly), so ``stoich`` must be declared to fund the FULL biomass of each new
  instance or the F012 amount-canary (:func:`alienbio.bio.conservation.total_quantity`)
  fires — matter created from nothing.
- :class:`PerCapitaDeath` — ``extent = k · N · dt``; optionally releases biomass back
  to a named pool (the reverse of growth's draw).
- :class:`CountFlow` — the size-class transition primitive (Q2=A): an inter-compartment
  count flow that moves ``Δmultiplicity`` from ``origin`` to ``dest`` at
  ``rate_constant · N_origin`` (a maturation edge, parallel in shape to
  :class:`~alienbio.bio.flow.TransportFlux` but on the multiplicity axis rather than a
  molecule pool). Conserves headcount exactly: the SAME extent leaves ``origin`` and
  enters ``dest``.

Every law's :meth:`PopulationLaw.contribute` reads ONLY the frozen start-of-step state
(order-independent, H4-flavored) and ACCUMULATES its multiplicity/molecule deltas into
caller-supplied dicts rather than mutating state directly — so several laws can affect
the same compartment/pool in one step without one clobbering another's read of the frozen
baseline (:meth:`WorldSimulatorImpl._population_pass` applies the accumulated totals once,
after every law has contributed).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .world_state import WorldStateImpl

# Type aliases
MoleculeId = int
CompartmentId = int

#: Accumulator for Δmultiplicity, keyed by compartment — populated by every law's
#: :meth:`PopulationLaw.contribute`, applied once by the population pass.
MultDelta = Dict[CompartmentId, float]

#: Accumulator for Δconcentration, keyed by ``(compartment, molecule)`` — the resource
#: draw/release side of growth/death, applied once alongside ``MultDelta``.
MolDelta = Dict[tuple[CompartmentId, MoleculeId], float]


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
    ) -> None:
        """Read ``frozen`` (start-of-step state) and ACCUMULATE this law's
        Δmultiplicity / Δconcentration into the shared caller-supplied dicts.

        Never mutates ``frozen``, and never reads the dicts back — every law is a
        pure function of the frozen state, so order among laws does not matter.
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

        if self._stoich > 0.0:
            drawn = self._stoich * raw
            scale = frozen.get_multiplicity(self._resource_compartment) * frozen.get_volume(
                self._resource_compartment
            )
            if scale > 0.0:
                key = (self._resource_compartment, self._resource)
                mol_delta[key] = mol_delta.get(key, 0.0) - drawn / scale

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
    ) -> None:
        raw = self.compute_extent(frozen) * dt
        n = frozen.get_multiplicity(self._compartment)
        raw = min(raw, n)  # never kill more than exist
        if raw <= 0.0:
            return

        mult_delta[self._compartment] = mult_delta.get(self._compartment, 0.0) - raw

        if (
            self._release_compartment is not None
            and self._release_resource is not None
            and self._release_stoich > 0.0
        ):
            scale = frozen.get_multiplicity(self._release_compartment) * frozen.get_volume(
                self._release_compartment
            )
            if scale > 0.0:
                key = (self._release_compartment, self._release_resource)
                released = self._release_stoich * raw
                mol_delta[key] = mol_delta.get(key, 0.0) + released / scale

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
    ) -> None:
        raw = self.compute_extent(frozen) * dt
        n = frozen.get_multiplicity(self._origin)
        raw = min(raw, n)  # never move more than exist at origin
        if raw <= 0.0:
            return

        mult_delta[self._origin] = mult_delta.get(self._origin, 0.0) - raw
        mult_delta[self._dest] = mult_delta.get(self._dest, 0.0) + raw

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
