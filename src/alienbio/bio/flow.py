"""Flow: transport between compartments.

Flow hierarchy:
- Flow (abstract base): common interface for all flows
- MembraneFlow: transport across parent-child boundary with stoichiometry
- GeneralFlow: arbitrary state modifications (placeholder, needs general interpreter)
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

