"""Biology protocol definitions.

Protocols for the biology subsystem:
- Atom: Chemical element with symbol and properties
- Molecule: Chemical species composed of atoms
- Reaction: Transformations within a compartment
- Flow: Transport across compartment membranes
- Chemistry: Container for atoms, molecules, reactions
- CompartmentTree: Hierarchical topology of compartments
- WorldState: Concentration storage for all compartments
- Simulator: Step-based simulation

These protocols define the interfaces that implementation classes must satisfy.
Use these for type hints to allow for alternative implementations.
"""

from __future__ import annotations

from abc import abstractmethod
from typing import Any, Callable, Dict, Iterator, List, Optional, Protocol, Union, runtime_checkable


# ═══════════════════════════════════════════════════════════════════════════════
# Basic Types
# ═══════════════════════════════════════════════════════════════════════════════

# IDs are integers for efficient array indexing
MoleculeId = int
CompartmentId = int


@runtime_checkable
class Atom(Protocol):
    """Protocol for atomic elements.

    Atoms are the building blocks of molecules. Each atom has:
    - symbol: 1-2 letter chemical notation (e.g., "C", "H", "Na")
    - name: Human-readable name (e.g., "Carbon", "Hydrogen")
    - atomic_weight: Mass in atomic mass units
    """

    @property
    def symbol(self) -> str:
        """Chemical symbol (1-2 letters): 'C', 'H', 'O', 'Na'."""
        ...

    @property
    def name(self) -> str:
        """Human-readable name: 'Carbon', 'Hydrogen'."""
        ...

    @property
    def atomic_weight(self) -> float:
        """Atomic mass in atomic mass units."""
        ...


@runtime_checkable
class Molecule(Protocol):
    """Protocol for molecule entities.

    Molecules are composed of atoms and have:
    - atoms: Composition as {Atom: count}
    - bdepth: Biosynthetic depth (0 = primitive, higher = more complex)
    - name: Human-readable name (e.g., "glucose", "water")
    - symbol: Chemical formula derived from atoms (e.g., "C6H12O6")
    - molecular_weight: Computed from atom weights
    """

    @property
    def local_name(self) -> str:
        """The molecule's local name within its parent entity."""
        ...

    @property
    def atoms(self) -> Dict[Atom, int]:
        """Atom composition: {atom: count}."""
        ...

    @property
    def bdepth(self) -> int:
        """Biosynthetic depth (0 = primitive, 4+ = complex)."""
        ...

    @property
    def name(self) -> str:
        """Human-readable name: 'glucose', 'water'."""
        ...

    @property
    def symbol(self) -> str:
        """Chemical formula derived from atoms: 'C6H12O6', 'H2O'."""
        ...

    @property
    def molecular_weight(self) -> float:
        """Molecular mass computed from atom weights."""
        ...


# ═══════════════════════════════════════════════════════════════════════════════
# Operations: Reactions and Flows
# ═══════════════════════════════════════════════════════════════════════════════

@runtime_checkable
class Reaction(Protocol):
    """Protocol for reaction entities.

    Reactions define transformations within a single compartment.
    Each reaction has reactants, products, and a rate.
    """

    @property
    def local_name(self) -> str:
        """The reaction's local name."""
        ...

    @property
    def name(self) -> str:
        """Human-readable name."""
        ...

    @property
    def symbol(self) -> str:
        """Formula string: 'A + B -> C + D'."""
        ...

    @property
    def reactants(self) -> Dict[Molecule, float]:
        """Reactant molecules and their stoichiometric coefficients."""
        ...

    @property
    def products(self) -> Dict[Molecule, float]:
        """Product molecules and their stoichiometric coefficients."""
        ...

    @property
    def rate(self) -> Union[float, Callable]:
        """Reaction rate (constant or function of state)."""
        ...

    def get_rate(self, state: WorldState, compartment: CompartmentId) -> float:
        """Get the effective rate for a given compartment's state."""
        ...


@runtime_checkable
class Flow(Protocol):
    """Protocol for transport between compartments.

    Flow hierarchy:
    - Flow (base): common interface for all flows
    - MembraneFlow: transport across parent-child membrane with stoichiometry
    - GeneralFlow: arbitrary state modifications (placeholder)

    Each flow is anchored to an origin compartment.
    """

    @property
    def origin(self) -> CompartmentId:
        """The origin compartment (where this flow is anchored)."""
        ...

    @property
    def name(self) -> str:
        """Human-readable name."""
        ...

    @property
    def is_membrane_flow(self) -> bool:
        """True if this is a membrane flow (origin ↔ parent)."""
        ...

    @property
    def is_general_flow(self) -> bool:
        """True if this is a general flow (arbitrary edits)."""
        ...

    def compute_flux(
        self, state: WorldState, tree: CompartmentTree
    ) -> float:
        """Compute flux for this flow."""
        ...

    def apply(
        self, state: WorldState, tree: CompartmentTree, dt: float
    ) -> None:
        """Apply this flow to the state (mutates in place)."""
        ...

    def attributes(self) -> Dict[str, Any]:
        """Semantic content for serialization."""
        ...


@runtime_checkable
class MembraneFlow(Flow, Protocol):
    """Protocol for membrane flows with stoichiometry.

    Membrane flows transport molecules across the parent-child boundary.
    Like reactions, they specify stoichiometry for multiple molecules
    moving together per event.

    Direction convention:
    - Positive stoichiometry = molecules move INTO origin (from parent)
    - Negative stoichiometry = molecules move OUT OF origin (into parent)
    """

    @property
    def stoichiometry(self) -> Dict[str, float]:
        """Molecules and counts moved per event {molecule: count}."""
        ...

    @property
    def rate_constant(self) -> float:
        """Base rate of events per unit time."""
        ...


@runtime_checkable
class GeneralFlow(Flow, Protocol):
    """Protocol for general flows (placeholder).

    GeneralFlow is a catch-all for flows that don't fit the MembraneFlow pattern.
    This includes lateral flows, instance transfers, and arbitrary state edits.

    NOTE: This is a placeholder. Full implementation will require a more
    general interpreter to handle arbitrary state modifications.
    """

    @property
    def description(self) -> str:
        """Description of what this flow does."""
        ...


# ═══════════════════════════════════════════════════════════════════════════════
# Containers: Chemistry and CompartmentTree
# ═══════════════════════════════════════════════════════════════════════════════

@runtime_checkable
class Chemistry(Protocol):
    """Protocol for chemistry containers.

    Chemistry acts as the "world" for a chemical system,
    holding atoms, molecules, and reactions as public dict attributes.
    """

    @property
    def local_name(self) -> str:
        """The chemistry's local name."""
        ...

    @property
    def atoms(self) -> Dict[str, Atom]:
        """All atoms in this chemistry (by symbol)."""
        ...

    @property
    def molecules(self) -> Dict[str, Molecule]:
        """All molecules in this chemistry (by name)."""
        ...

    @property
    def reactions(self) -> Dict[str, Reaction]:
        """All reactions in this chemistry (by name)."""
        ...

    def validate(self) -> List[str]:
        """Validate the chemistry for consistency."""
        ...


@runtime_checkable
class CompartmentTree(Protocol):
    """Protocol for compartment topology.

    Represents the hierarchical structure of compartments (organism > organ > cell).
    Stored separately from concentrations to allow efficient updates.
    """

    @property
    def num_compartments(self) -> int:
        """Total number of compartments."""
        ...

    def parent(self, child: CompartmentId) -> Optional[CompartmentId]:
        """Get parent of a compartment (None for root)."""
        ...

    def children(self, parent: CompartmentId) -> List[CompartmentId]:
        """Get children of a compartment."""
        ...

    def root(self) -> CompartmentId:
        """Get the root compartment."""
        ...

    def is_root(self, compartment: CompartmentId) -> bool:
        """Check if compartment is the root."""
        ...


# ═══════════════════════════════════════════════════════════════════════════════
# State: WorldState
# ═══════════════════════════════════════════════════════════════════════════════

@runtime_checkable
class WorldState(Protocol):
    """Protocol for world concentration state.

    Stores concentrations for all compartments and molecules.
    Dense storage: [num_compartments x num_molecules] array.
    Can be extended with sparse overflow for large molecule counts.

    Each WorldState holds a reference to its CompartmentTree. Multiple
    states can share the same tree (immutable sharing). When topology
    changes (e.g., cell division), a new tree is created and new states
    point to it while historical states keep their original tree reference.
    """

    @property
    def tree(self) -> CompartmentTree:
        """The compartment tree this state belongs to."""
        ...

    @property
    def num_compartments(self) -> int:
        """Number of compartments."""
        ...

    @property
    def num_molecules(self) -> int:
        """Number of molecules in vocabulary."""
        ...

    def get(self, compartment: CompartmentId, molecule: MoleculeId) -> float:
        """Get concentration of molecule in compartment."""
        ...

    def set(self, compartment: CompartmentId, molecule: MoleculeId, value: float) -> None:
        """Set concentration of molecule in compartment."""
        ...

    def get_compartment(self, compartment: CompartmentId) -> List[float]:
        """Get all concentrations for a compartment."""
        ...

    # Multiplicity methods

    def get_multiplicity(self, compartment: CompartmentId) -> float:
        """Get multiplicity (instance count) for a compartment."""
        ...

    def set_multiplicity(self, compartment: CompartmentId, value: float) -> None:
        """Set multiplicity (instance count) for a compartment."""
        ...

    def total_molecules(self, compartment: CompartmentId, molecule: MoleculeId) -> float:
        """Get total molecules = multiplicity * concentration."""
        ...

    # Copy and array methods

    def copy(self) -> WorldState:
        """Create a copy of this state (shares tree reference)."""
        ...

    def as_array(self) -> Any:
        """Get concentrations as 2D array [compartments x molecules]."""
        ...


# ═══════════════════════════════════════════════════════════════════════════════
# State (for single-compartment Chemistry simulations)
# ═══════════════════════════════════════════════════════════════════════════════

@runtime_checkable
class State(Protocol):
    """Protocol for single-compartment molecule concentration state.

    Simple interface for simulations with one compartment.
    For multi-compartment simulations, use WorldState instead.
    """

    @property
    def chemistry(self) -> Chemistry:
        """The Chemistry this state belongs to."""
        ...

    def __getitem__(self, key: str) -> float:
        """Get concentration by molecule name."""
        ...

    def __setitem__(self, key: str, value: float) -> None:
        """Set concentration by molecule name."""
        ...

    def __contains__(self, key: str) -> bool:
        """Check if molecule exists in state."""
        ...

    def __iter__(self) -> Iterator[str]:
        """Iterate over molecule names."""
        ...

    def __len__(self) -> int:
        """Number of molecules in state."""
        ...

    def get(self, key: str, default: float = 0.0) -> float:
        """Get concentration with default."""
        ...

    def get_molecule(self, molecule: Molecule) -> float:
        """Get concentration by molecule object."""
        ...

    def set_molecule(self, molecule: Molecule, value: float) -> None:
        """Set concentration by molecule object."""
        ...

    def copy(self) -> State:
        """Create a copy of this state."""
        ...


# ═══════════════════════════════════════════════════════════════════════════════
# Simulation
# ═══════════════════════════════════════════════════════════════════════════════

class Simulator(Protocol):
    """Protocol for simulators.

    A Simulator advances the state of a chemical system over time.
    Applies reactions within compartments and flows across membranes.
    """

    @property
    def chemistry(self) -> Chemistry:
        """The Chemistry being simulated."""
        ...

    @property
    def tree(self) -> CompartmentTree:
        """The compartment topology."""
        ...

    @property
    def dt(self) -> float:
        """Time step size."""
        ...

    @abstractmethod
    def step(self, state: WorldState) -> WorldState:
        """Advance the simulation by one time step."""
        ...

    def run(
        self,
        state: WorldState,
        steps: int,
        sample_every: Optional[int] = None,
    ) -> List[WorldState]:
        """Run simulation for multiple steps, optionally sampling history."""
        ...
