"""Flow: transport between compartments.

Flow hierarchy:
- Flow (abstract base): common interface for all flows
- MembraneFlow: transport across parent-child boundary with stoichiometry
- LateralFlow: transport between siblings (instance or molecule transfer)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING, Union

if TYPE_CHECKING:
    from .world_state import WorldStateImpl
    from .compartment_tree import CompartmentTreeImpl

# Type aliases
MoleculeId = int
CompartmentId = int

# Flow rate can be constant or function of concentrations
FlowRateFunction = Callable[[float, float], float]  # (source_conc, target_conc) -> rate
FlowRateValue = Union[float, FlowRateFunction]

# Special molecule ID for multiplicity (instance count)
MULTIPLICITY_ID = -1


class Flow(ABC):
    """Abstract base class for all flows.

    Flows move molecules (or instances) between compartments. Each flow is
    anchored to an origin compartment and transfers to a target.

    Subclasses:
    - MembraneFlow: transport across parent-child membrane with stoichiometry
    - LateralFlow: transport between sibling compartments

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
    def is_lateral_flow(self) -> bool:
        """True if this is a lateral flow (origin ↔ sibling)."""
        ...

    @property
    @abstractmethod
    def is_instance_transfer(self) -> bool:
        """True if this transfers instances (multiplicity) rather than molecules."""
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
            Flux value (positive = into origin for membrane, origin→target for lateral)
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
    def is_lateral_flow(self) -> bool:
        """False - this is not a lateral flow."""
        return False

    @property
    def is_instance_transfer(self) -> bool:
        """False - membrane flows transfer molecules, not instances."""
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


class LateralFlow(Flow):
    """Transport between sibling compartments.

    A LateralFlow moves molecules or instances between compartments that
    share the same parent. Common use cases:
    - Instance transfer: RBCs moving from arteries to veins
    - Molecule exchange: nutrients between adjacent cells

    For instance transfers, use molecule=MULTIPLICITY_ID.

    Example:
        # RBC transfer from arteries to veins
        rbc_flow = LateralFlow(
            origin=arterial_rbc_id,
            target=venous_rbc_id,
            molecule=MULTIPLICITY_ID,  # transfer instances
            rate_constant=0.01,
            name="rbc_circulation",
        )

        # Molecule diffusion between adjacent cells
        gap_junction = LateralFlow(
            origin=cell1_id,
            target=cell2_id,
            molecule=calcium_id,
            rate_constant=0.1,
            name="gap_junction_ca",
        )
    """

    __slots__ = ("_target", "_molecule", "_rate_constant", "_rate_fn")

    def __init__(
        self,
        origin: CompartmentId,
        target: CompartmentId,
        molecule: MoleculeId,
        rate_constant: float = 1.0,
        rate_fn: Optional[FlowRateFunction] = None,
        name: str = "",
    ) -> None:
        """Initialize a lateral flow.

        Args:
            origin: The origin compartment
            target: The target compartment (sibling of origin)
            molecule: The molecule being transported (by ID), or MULTIPLICITY_ID
            rate_constant: Base permeability/transport rate
            rate_fn: Optional function (source_conc, target_conc) -> rate
            name: Human-readable name for this flow
        """
        if not name:
            name = f"lateral_{molecule}_{origin}_to_{target}"
        super().__init__(origin, name)

        self._target = target
        self._molecule = molecule
        self._rate_constant = rate_constant
        self._rate_fn = rate_fn

    @property
    def target(self) -> CompartmentId:
        """The target compartment."""
        return self._target

    @property
    def molecule(self) -> MoleculeId:
        """The molecule being transported (MULTIPLICITY_ID for instances)."""
        return self._molecule

    @property
    def rate_constant(self) -> float:
        """Base permeability/transport rate."""
        return self._rate_constant

    @property
    def is_membrane_flow(self) -> bool:
        """False - this is not a membrane flow."""
        return False

    @property
    def is_lateral_flow(self) -> bool:
        """True - this is a lateral flow."""
        return True

    @property
    def is_instance_transfer(self) -> bool:
        """True if this transfers instances (multiplicity) rather than molecules."""
        return self._molecule == MULTIPLICITY_ID

    def compute_flux(
        self,
        state: WorldStateImpl,
        tree: CompartmentTreeImpl,
    ) -> float:
        """Compute flux from origin to target.

        Positive flux = transfer from origin to target.

        Args:
            state: Current world state with concentrations
            tree: Compartment topology

        Returns:
            Flux value
        """
        # Get concentrations (or multiplicities for instance transfers)
        if self._molecule == MULTIPLICITY_ID:
            source_val = state.get_multiplicity(self._origin)
            dest_val = state.get_multiplicity(self._target)
        else:
            source_val = state.get(self._origin, self._molecule)
            dest_val = state.get(self._target, self._molecule)

        if self._rate_fn is not None:
            return self._rate_fn(source_val, dest_val)
        else:
            # Simple diffusion / transfer based on gradient
            return self._rate_constant * (source_val - dest_val)

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
        flux = self.compute_flux(state, tree) * dt

        # Apply flux: origin loses, target gains
        if self._molecule == MULTIPLICITY_ID:
            source_val = state.get_multiplicity(self._origin)
            dest_val = state.get_multiplicity(self._target)
            state.set_multiplicity(self._origin, max(0.0, source_val - flux))
            state.set_multiplicity(self._target, max(0.0, dest_val + flux))
        else:
            source_val = state.get(self._origin, self._molecule)
            dest_val = state.get(self._target, self._molecule)
            state.set(self._origin, self._molecule, max(0.0, source_val - flux))
            state.set(self._target, self._molecule, max(0.0, dest_val + flux))

    def attributes(self) -> Dict[str, Any]:
        """Semantic content for serialization."""
        result: Dict[str, Any] = {
            "type": "lateral",
            "name": self._name,
            "origin": self._origin,
            "target": self._target,
            "molecule": self._molecule,
            "rate_constant": self._rate_constant,
        }
        # Note: rate_fn cannot be serialized
        return result

    def __repr__(self) -> str:
        """Full representation."""
        return (
            f"LateralFlow(origin={self._origin}, target={self._target}, "
            f"molecule={self._molecule}, rate={self._rate_constant})"
        )

    def __str__(self) -> str:
        """Short representation."""
        return f"LateralFlow({self._name})"


# Keep FlowImpl as alias for backwards compatibility during transition
# TODO: Remove after updating all usages
FlowImpl = LateralFlow
