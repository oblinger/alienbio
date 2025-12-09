"""WorldState: concentration storage for multi-compartment simulations."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .compartment_tree import CompartmentTreeImpl

# Type aliases
MoleculeId = int
CompartmentId = int


class WorldStateImpl:
    """Implementation: Dense concentration storage for all compartments.

    Stores concentrations as a flat array indexed by [compartment, molecule].
    Also stores multiplicity (instance count) per compartment.
    Dense storage is efficient for small to medium molecule counts.

    Each WorldState holds a reference to its CompartmentTree. Multiple states
    share the same tree reference (immutable sharing) until topology changes.
    When topology changes (e.g., cell division), a new tree is created.

    Attributes:
        tree: The CompartmentTree this state belongs to (shared reference)
        num_compartments: Number of compartments (derived from tree)
        num_molecules: Number of molecules in vocabulary
        concentrations: Flat array [num_compartments * num_molecules]
        multiplicities: Array [num_compartments] - instance count per compartment

    The concentration array is row-major: concentrations[comp * num_molecules + mol]

    Multiplicity represents how many instances of this compartment exist.
    For example, "arterial red blood cells" might have multiplicity 1e6.
    Concentrations are per-instance; total molecules = multiplicity * concentration.

    Example:
        tree = CompartmentTreeImpl()
        root = tree.add_root("organism")
        cell = tree.add_child(root, "cell")
        state = WorldStateImpl(tree=tree, num_molecules=50)

        # Set concentrations
        state.set(compartment=cell, molecule=5, value=1.0)
        print(state.get(cell, 5))  # 1.0

        # Set multiplicity (number of cells)
        state.set_multiplicity(cell, 1000.0)
        print(state.get_multiplicity(cell))  # 1000.0
    """

    __slots__ = ("_tree", "_num_molecules", "_concentrations", "_multiplicities")

    def __init__(
        self,
        tree: CompartmentTreeImpl,
        num_molecules: int,
        initial_concentrations: Optional[List[float]] = None,
        initial_multiplicities: Optional[List[float]] = None,
    ) -> None:
        """Initialize world state.

        Args:
            tree: CompartmentTree defining the topology (shared reference)
            num_molecules: Number of molecules in vocabulary
            initial_concentrations: Optional flat array of initial concentrations
            initial_multiplicities: Optional array of initial multiplicities per compartment
        """
        self._tree = tree
        self._num_molecules = num_molecules

        num_compartments = tree.num_compartments
        size = num_compartments * num_molecules

        # Initialize concentrations
        if initial_concentrations is not None:
            if len(initial_concentrations) != size:
                raise ValueError(
                    f"Initial concentrations size {len(initial_concentrations)} != "
                    f"{num_compartments} * {num_molecules} = {size}"
                )
            self._concentrations = list(initial_concentrations)
        else:
            self._concentrations = [0.0] * size

        # Initialize multiplicities (default 1.0 for each compartment)
        if initial_multiplicities is not None:
            if len(initial_multiplicities) != num_compartments:
                raise ValueError(
                    f"Initial multiplicities size {len(initial_multiplicities)} != "
                    f"num_compartments {num_compartments}"
                )
            self._multiplicities = list(initial_multiplicities)
        else:
            self._multiplicities = [1.0] * num_compartments

    @property
    def tree(self) -> CompartmentTreeImpl:
        """The compartment tree this state belongs to (shared reference)."""
        return self._tree

    @property
    def num_compartments(self) -> int:
        """Number of compartments (from tree)."""
        return self._tree.num_compartments

    @property
    def num_molecules(self) -> int:
        """Number of molecules in vocabulary."""
        return self._num_molecules

    def _index(self, compartment: CompartmentId, molecule: MoleculeId) -> int:
        """Compute flat array index."""
        return compartment * self._num_molecules + molecule

    def get(self, compartment: CompartmentId, molecule: MoleculeId) -> float:
        """Get concentration of molecule in compartment."""
        return self._concentrations[self._index(compartment, molecule)]

    def set(
        self, compartment: CompartmentId, molecule: MoleculeId, value: float
    ) -> None:
        """Set concentration of molecule in compartment."""
        self._concentrations[self._index(compartment, molecule)] = value

    def get_compartment(self, compartment: CompartmentId) -> List[float]:
        """Get all concentrations for a compartment."""
        start = compartment * self._num_molecules
        end = start + self._num_molecules
        return self._concentrations[start:end]

    def set_compartment(
        self, compartment: CompartmentId, values: List[float]
    ) -> None:
        """Set all concentrations for a compartment."""
        if len(values) != self._num_molecules:
            raise ValueError(
                f"Values length {len(values)} != num_molecules {self._num_molecules}"
            )
        start = compartment * self._num_molecules
        for i, v in enumerate(values):
            self._concentrations[start + i] = v

    # ── Multiplicity methods ──────────────────────────────────────────────────

    def get_multiplicity(self, compartment: CompartmentId) -> float:
        """Get multiplicity (instance count) for a compartment."""
        return self._multiplicities[compartment]

    def set_multiplicity(self, compartment: CompartmentId, value: float) -> None:
        """Set multiplicity (instance count) for a compartment."""
        self._multiplicities[compartment] = value

    def get_all_multiplicities(self) -> List[float]:
        """Get multiplicities for all compartments."""
        return self._multiplicities.copy()

    def total_molecules(self, compartment: CompartmentId, molecule: MoleculeId) -> float:
        """Get total molecules = multiplicity * concentration."""
        return self._multiplicities[compartment] * self.get(compartment, molecule)

    # ── Copy and array methods ────────────────────────────────────────────────

    def copy(self) -> WorldStateImpl:
        """Create a copy of this state (shares tree reference)."""
        return WorldStateImpl(
            self._tree,  # Shared reference - tree is immutable
            self._num_molecules,
            initial_concentrations=self._concentrations.copy(),
            initial_multiplicities=self._multiplicities.copy(),
        )

    def as_array(self) -> Any:
        """Get concentrations as 2D numpy array [compartments x molecules].

        Returns a view if numpy is available, otherwise a list of lists.
        """
        try:
            import numpy as np

            arr = np.array(self._concentrations, dtype=np.float64)
            return arr.reshape(self.num_compartments, self._num_molecules)
        except ImportError:
            # Fallback: return list of lists
            return [
                self.get_compartment(c) for c in range(self.num_compartments)
            ]

    def from_array(self, arr: Any) -> None:
        """Set concentrations from 2D array [compartments x molecules]."""
        try:
            import numpy as np

            flat = np.asarray(arr, dtype=np.float64).flatten()
            if len(flat) != len(self._concentrations):
                raise ValueError(
                    f"Array size {len(flat)} != expected {len(self._concentrations)}"
                )
            self._concentrations = flat.tolist()
        except ImportError:
            # Fallback: assume list of lists
            idx = 0
            for row in arr:
                for val in row:
                    self._concentrations[idx] = float(val)
                    idx += 1

    def __repr__(self) -> str:
        """Full representation."""
        return (
            f"WorldStateImpl(compartments={self.num_compartments}, "
            f"molecules={self._num_molecules})"
        )

    def __str__(self) -> str:
        """Short representation with summary stats."""
        total = sum(self._concentrations)
        nonzero = sum(1 for c in self._concentrations if c > 0)
        return (
            f"WorldState({self.num_compartments}x{self._num_molecules}, "
            f"total={total:.3g}, nonzero={nonzero})"
        )
