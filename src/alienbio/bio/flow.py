"""Flow: transport between compartments.

Flow hierarchy:
- Flow (abstract base): common interface for all flows
- MembraneFlow: transport across parent-child boundary with stoichiometry
- GeneralFlow: arbitrary state modifications (placeholder, needs general interpreter)
- TransportFlux: cross-compartment flux between ANY two compartments (F016/S3),
  amount-conserving in AMOUNT-space (not concentration) regardless of the two
  compartments' volumes/multiplicities
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .world_state import WorldStateImpl
    from .compartment_tree import CompartmentTreeImpl

# Type aliases
CompartmentId = int


class Flow(ABC):
    """Abstract base class for all flows.

    Flows move molecules (or instances) between compartments. Each flow is
    anchored to an origin compartment.

    Subclasses:
    - MembraneFlow: transport across parent-child membrane with stoichiometry
    - GeneralFlow: arbitrary state modifications (placeholder)

    Common interface:
    - origin: the compartment where this flow is anchored
    - name: human-readable identifier
    - compute_flux(): calculate transfer rate
    - apply(): modify state based on flux
    """

    __slots__ = ("_origin", "_name")

    def __init__(
        self,
        origin: CompartmentId,
        name: str = "",
    ) -> None:
        """Initialize base flow.

        Args:
            origin: The origin compartment (where this flow is anchored)
            name: Human-readable name for this flow
        """
        self._origin = origin
        self._name = name

    @property
    def origin(self) -> CompartmentId:
        """The origin compartment (where this flow is anchored)."""
        return self._origin

    @property
    def name(self) -> str:
        """Human-readable name."""
        return self._name

    @property
    @abstractmethod
    def is_membrane_flow(self) -> bool:
        """True if this is a membrane flow (origin ↔ parent)."""
        ...

    @property
    @abstractmethod
    def is_general_flow(self) -> bool:
        """True if this is a general flow (arbitrary edits)."""
        ...

    @abstractmethod
    def compute_flux(
        self,
        state: WorldStateImpl,
        tree: CompartmentTreeImpl,
    ) -> float:
        """Compute flux for this flow.

        Args:
            state: Current world state with concentrations
            tree: Compartment topology

        Returns:
            Flux value (positive = into origin for membrane flows)
        """
        ...

    @abstractmethod
    def apply(
        self,
        state: WorldStateImpl,
        tree: CompartmentTreeImpl,
        dt: float = 1.0,
    ) -> None:
        """Apply this flow to the state (mutates in place).

        Args:
            state: World state to modify
            tree: Compartment topology
            dt: Time step
        """
        ...

    @abstractmethod
    def attributes(self) -> Dict[str, Any]:
        """Semantic content for serialization."""
        ...


class MembraneFlow(Flow):
    """Transport across parent-child membrane with stoichiometry.

    A MembraneFlow moves molecules across the membrane between a compartment
    and its parent. Like reactions, it can specify stoichiometry for multiple
    molecules moving together.

    The rate equation determines how many "events" occur per unit time.
    Each event moves the specified stoichiometry of molecules.

    Direction convention:
    - Positive stoichiometry = molecules move INTO the origin (from parent)
    - Negative stoichiometry = molecules move OUT OF origin (into parent)

    Example:
        # Sodium-glucose cotransporter (SGLT1)
        # Moves 2 Na+ and 1 glucose into the cell together
        sglt1 = MembraneFlow(
            origin=cell_id,
            stoichiometry={"sodium": 2, "glucose": 1},
            rate_constant=10.0,
            name="sglt1",
        )

        # Sodium-potassium pump (Na+/K+-ATPase)
        # Pumps 3 Na+ out, 2 K+ in per ATP hydrolyzed
        na_k_pump = MembraneFlow(
            origin=cell_id,
            stoichiometry={"sodium": -3, "potassium": 2, "atp": -1, "adp": 1},
            rate_constant=5.0,
            name="na_k_atpase",
        )
    """

    __slots__ = ("_stoichiometry", "_rate_constant", "_rate_fn")

    def __init__(
        self,
        origin: CompartmentId,
        stoichiometry: Dict[str, float],
        rate_constant: float = 1.0,
        rate_fn: Optional[Callable[..., float]] = None,
        name: str = "",
    ) -> None:
        """Initialize a membrane flow.

        Args:
            origin: The compartment whose membrane this flow crosses
            stoichiometry: Molecules and counts moved per event {molecule: count}
                          Positive = into origin, negative = out of origin
            rate_constant: Base rate of events per unit time
            rate_fn: Optional custom rate function
            name: Human-readable name for this flow
        """
        if not name:
            molecules = "_".join(stoichiometry.keys())
            name = f"membrane_{molecules}_at_{origin}"
        super().__init__(origin, name)

        self._stoichiometry = stoichiometry.copy()
        self._rate_constant = rate_constant
        self._rate_fn = rate_fn

    @property
    def stoichiometry(self) -> Dict[str, float]:
        """Molecules and counts moved per event {molecule: count}."""
        return self._stoichiometry.copy()

    @property
    def rate_constant(self) -> float:
        """Base rate of events per unit time."""
        return self._rate_constant

    @property
    def is_membrane_flow(self) -> bool:
        """True - this is a membrane flow."""
        return True

    @property
    def is_general_flow(self) -> bool:
        """False - this is not a general flow."""
        return False

    def compute_flux(
        self,
        state: WorldStateImpl,
        tree: CompartmentTreeImpl,
    ) -> float:
        """Compute the rate of events (not molecules).

        Returns the number of "transport events" per unit time.
        Multiply by stoichiometry to get actual molecule transfer.

        Args:
            state: Current world state with concentrations
            tree: Compartment topology

        Returns:
            Event rate (events per unit time)
        """
        parent = tree.parent(self._origin)
        if parent is None:
            return 0.0

        if self._rate_fn is not None:
            # Custom rate function - pass state and relevant info
            return self._rate_fn(state, self._origin, parent)
        else:
            # Simple constant rate
            return self._rate_constant

    def apply(
        self,
        state: WorldStateImpl,
        tree: CompartmentTreeImpl,
        dt: float = 1.0,
    ) -> None:
        """Apply this flow to the state (mutates in place).

        Computes event rate, then applies stoichiometry to both
        origin and parent compartments.

        Args:
            state: World state to modify
            tree: Compartment topology
            dt: Time step
        """
        parent = tree.parent(self._origin)
        if parent is None:
            return

        event_rate = self.compute_flux(state, tree) * dt

        # Apply stoichiometry
        # Positive stoich = into origin (from parent)
        # Negative stoich = out of origin (into parent)
        for molecule_name, count in self._stoichiometry.items():
            # TODO: Need molecule name -> ID mapping from chemistry
            # For now, this is a placeholder showing the pattern
            # molecules_transferred = event_rate * count
            # origin gains: +molecules_transferred
            # parent loses: -molecules_transferred
            pass

    def attributes(self) -> Dict[str, Any]:
        """Semantic content for serialization."""
        result: Dict[str, Any] = {
            "type": "membrane",
            "name": self._name,
            "origin": self._origin,
            "stoichiometry": self._stoichiometry.copy(),
            "rate_constant": self._rate_constant,
        }
        # Note: rate_fn cannot be serialized
        return result

    def __repr__(self) -> str:
        """Full representation."""
        stoich_str = ", ".join(f"{m}:{c}" for m, c in self._stoichiometry.items())
        return f"MembraneFlow(origin={self._origin}, stoich={{{stoich_str}}}, rate={self._rate_constant})"

    def __str__(self) -> str:
        """Short representation."""
        return f"MembraneFlow({self._name})"


class GeneralFlow(Flow):
    """Arbitrary state modifications (placeholder).

    GeneralFlow is a catch-all for flows that don't fit the MembraneFlow pattern.
    This includes:
    - Lateral flows between siblings
    - Instance transfers (RBCs moving between compartments)
    - Any other arbitrary edits to the system

    NOTE: This is currently a placeholder. Full implementation will require
    a more general interpreter to handle arbitrary state modifications
    specified via Expr or similar.

    For now, GeneralFlow stores an apply_fn that takes state and tree
    and performs arbitrary modifications.
    """

    __slots__ = ("_apply_fn", "_description")

    def __init__(
        self,
        origin: CompartmentId,
        apply_fn: Optional[Callable[[WorldStateImpl, CompartmentTreeImpl, float], None]] = None,
        name: str = "",
        description: str = "",
    ) -> None:
        """Initialize a general flow.

        Args:
            origin: The compartment where this flow is conceptually anchored
            apply_fn: Function (state, tree, dt) -> None that modifies state
            name: Human-readable name for this flow
            description: Description of what this flow does

        NOTE: This is a placeholder. Full implementation will need a more
        general interpreter to support Expr-based specifications.
        """
        if not name:
            name = f"general_flow_at_{origin}"
        super().__init__(origin, name)

        self._apply_fn = apply_fn
        self._description = description

    @property
    def description(self) -> str:
        """Description of what this flow does."""
        return self._description

    @property
    def is_membrane_flow(self) -> bool:
        """False - this is not a membrane flow."""
        return False

    @property
    def is_general_flow(self) -> bool:
        """True - this is a general flow."""
        return True

    def compute_flux(
        self,
        state: WorldStateImpl,
        tree: CompartmentTreeImpl,
    ) -> float:
        """General flows don't have a simple flux concept.

        Returns 0.0 as placeholder. The actual work happens in apply().
        """
        return 0.0

    def apply(
        self,
        state: WorldStateImpl,
        tree: CompartmentTreeImpl,
        dt: float = 1.0,
    ) -> None:
        """Apply this flow to the state (mutates in place).

        Args:
            state: World state to modify
            tree: Compartment topology
            dt: Time step
        """
        if self._apply_fn is not None:
            self._apply_fn(state, tree, dt)

    def attributes(self) -> Dict[str, Any]:
        """Semantic content for serialization.

        NOTE: apply_fn cannot be serialized. Full implementation will
        need Expr-based specification that can be serialized.
        """
        return {
            "type": "general",
            "name": self._name,
            "origin": self._origin,
            "description": self._description,
        }

    def __repr__(self) -> str:
        """Full representation."""
        return f"GeneralFlow(origin={self._origin}, name={self._name!r})"

    def __str__(self) -> str:
        """Short representation."""
        return f"GeneralFlow({self._name})"


class TransportFlux(Flow):
    """Cross-compartment flux: moves conserved AMOUNT (not concentration)
    between two independently-addressed compartments (F016/S3, skeleton
    decision S3 / coverage gap G3).

    Unlike :class:`MembraneFlow` (anchored to a parent-child pair via the
    tree), ``origin``/``dest`` here are two arbitrary compartments — no tree
    relationship required, which is what lets a :class:`~alienbio.suite.blocks.
    SpatialLatticeBlock` wire an arbitrary neighbor graph.

    Rate law (Q1=C, gradient default) — the event rate is driven by ONE
    ``driver_molecule``'s concentration:

    - ``rate_law="gradient"`` (default): Fickian, ``rate_constant *
      ([X]_origin - [X]_dest)`` — drives the driver species toward equal
      concentration across the two pools (the mechanism a diffusive lattice
      relaxes through).
    - ``rate_law="first_order"``: ``rate_constant * [X]_origin`` — a
      pump/boundary-flavored unidirectional law (no dependence on ``dest``).

    Either law's raw rate is floored at 0: this ONE flux is strictly
    ``origin -> dest``. A reversed local gradient (or a negative first-order
    rate) contributes nothing from THIS flux — wire a second, reversed
    ``TransportFlux`` for true bidirectional equilibration (e.g. a lattice's
    neighbor pair in each direction). This also protects against oscillation:
    once the driver species reaches equality, tiny numerical overshoot floors
    to 0 instead of flip-flopping sign every step.

    ``stoichiometry`` (``{molecule_id: count}``, exactly like
    ``MembraneFlow``) lets several species move together per event — active
    co-transport needs no new law, just an extra (possibly negative-count,
    counter-direction) entry co-transporting an energy carrier. Every species
    is rationed against the SAME shared event count (so a co-transported group
    moves in lockstep): for each species, the event count is clamped so its
    LOSING compartment's :meth:`WorldStateImpl.amount` never goes negative —
    the amount-conservation invariant (F012 count basis) this class exists to
    guarantee. The identical transferred amount ``Δn`` leaves the losing pool
    and enters the other, so ``Σ amount`` is invariant regardless of the two
    compartments' volumes/multiplicities.
    """

    __slots__ = ("_dest", "_stoichiometry", "_driver_molecule", "_rate_constant", "_rate_law")

    def __init__(
        self,
        origin: CompartmentId,
        dest: CompartmentId,
        stoichiometry: Dict[int, float],
        driver_molecule: int,
        rate_constant: float = 1.0,
        rate_law: str = "gradient",
        name: str = "",
    ) -> None:
        """Initialize a cross-compartment transport flux.

        Args:
            origin: The compartment this flux moves species OUT OF (the "src" pool)
            dest: The compartment this flux moves species INTO (the "dst" pool)
            stoichiometry: Molecule id -> count moved per event (all species move
                together, in lockstep, scaled by the shared event count)
            driver_molecule: Which molecule id's concentration drives the rate law
            rate_constant: ``D`` (gradient law) or ``k`` (first-order law)
            rate_law: ``"gradient"`` (Fickian, default) or ``"first_order"``
            name: Human-readable name for this flow

        Raises:
            ValueError: if ``rate_law`` is not one of the two supported laws.
        """
        if rate_law not in ("gradient", "first_order"):
            raise ValueError(
                f"TransportFlux rate_law must be 'gradient' or 'first_order', "
                f"got {rate_law!r}"
            )
        if not name:
            name = f"transport_{origin}_to_{dest}"
        super().__init__(origin, name)

        self._dest = dest
        self._stoichiometry = dict(stoichiometry)
        self._driver_molecule = driver_molecule
        self._rate_constant = rate_constant
        self._rate_law = rate_law

    @property
    def dest(self) -> CompartmentId:
        """The compartment this flux moves species INTO."""
        return self._dest

    @property
    def stoichiometry(self) -> Dict[int, float]:
        """Molecule id -> count moved per event (shared event count)."""
        return self._stoichiometry.copy()

    @property
    def driver_molecule(self) -> int:
        """Which molecule id's concentration drives the rate law."""
        return self._driver_molecule

    @property
    def rate_constant(self) -> float:
        """``D`` (gradient law) or ``k`` (first-order law)."""
        return self._rate_constant

    @property
    def rate_law(self) -> str:
        """``"gradient"`` (Fickian) or ``"first_order"``."""
        return self._rate_law

    @property
    def is_membrane_flow(self) -> bool:
        """False - this is not a parent-child membrane flow."""
        return False

    @property
    def is_general_flow(self) -> bool:
        """False - this is not an arbitrary-edit general flow."""
        return False

    def compute_flux(
        self,
        state: WorldStateImpl,
        tree: CompartmentTreeImpl,
    ) -> float:
        """Raw (unfloored, unrationed) event rate from the configured rate law.

        Args:
            state: Current world state with concentrations
            tree: Compartment topology (unused — origin/dest need no tree
                relationship)

        Returns:
            Event rate (events per unit time); may be negative (floored to 0
            in :meth:`apply`).
        """
        conc_src = state.get(self._origin, self._driver_molecule)
        if self._rate_law == "first_order":
            return self._rate_constant * conc_src
        # gradient (default): Fickian, driven toward equal concentration
        conc_dst = state.get(self._dest, self._driver_molecule)
        return self._rate_constant * (conc_src - conc_dst)

    def apply(
        self,
        state: WorldStateImpl,
        tree: CompartmentTreeImpl,
        dt: float = 1.0,
    ) -> None:
        """Apply this flux to the state (mutates in place).

        Computes the event rate, floors it at 0, rations it against every
        transported species' available AMOUNT in its losing compartment (so
        no species is ever driven negative), then moves the SAME clamped
        ``Δn`` out of the losing pool and into the other for each species —
        the amount-conserving bookkeeping this class exists to guarantee.

        Args:
            state: World state to modify
            tree: Compartment topology (unused)
            dt: Time step
        """
        event_count = max(self.compute_flux(state, tree) * dt, 0.0)
        if event_count <= 0.0:
            return

        # Ration: for each species, the compartment losing amount this event
        # is origin when count > 0 (species moves origin -> dest), else dest
        # (a negative count reverses that one species' direction — e.g. an
        # antiported energy carrier). Clamp the SHARED event count so no
        # species' losing pool goes negative.
        for mol, count in self._stoichiometry.items():
            if count == 0:
                continue
            losing = self._origin if count > 0 else self._dest
            available = state.amount(losing, mol)
            max_event = available / abs(count)
            if max_event < event_count:
                event_count = max(max_event, 0.0)

        if event_count <= 0.0:
            return

        origin_scale = state.get_multiplicity(self._origin) * state.get_volume(self._origin)
        dest_scale = state.get_multiplicity(self._dest) * state.get_volume(self._dest)
        for mol, count in self._stoichiometry.items():
            delta_n = event_count * count
            if origin_scale > 0:
                state.set(
                    self._origin, mol, state.get(self._origin, mol) - delta_n / origin_scale
                )
            if dest_scale > 0:
                state.set(self._dest, mol, state.get(self._dest, mol) + delta_n / dest_scale)

    def attributes(self) -> Dict[str, Any]:
        """Semantic content for serialization."""
        return {
            "type": "transport",
            "name": self._name,
            "origin": self._origin,
            "dest": self._dest,
            "stoichiometry": self._stoichiometry.copy(),
            "driver_molecule": self._driver_molecule,
            "rate_constant": self._rate_constant,
            "rate_law": self._rate_law,
        }

    def __repr__(self) -> str:
        """Full representation."""
        stoich_str = ", ".join(f"{m}:{c}" for m, c in self._stoichiometry.items())
        return (
            f"TransportFlux(origin={self._origin}, dest={self._dest}, "
            f"stoich={{{stoich_str}}}, rate={self._rate_constant}, law={self._rate_law!r})"
        )

    def __str__(self) -> str:
        """Short representation."""
        return f"TransportFlux({self._name})"

