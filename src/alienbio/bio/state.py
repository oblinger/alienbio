"""State: molecule concentrations at a point in time."""

from __future__ import annotations

from typing import Any, Dict, Iterator, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .chemistry import BioChemistry
    from .molecule import BioMolecule


class State:
    """Concentrations of molecules at a point in time.

    State is essentially a dict mapping molecules to concentration values.
    It's tied to a BioChemistry which defines the valid molecules.

    Attributes:
        chemistry: The BioChemistry this state belongs to
        concentrations: Dict mapping molecule names to concentration values

    Example:
        state = State(chemistry)
        state["glucose"] = 1.0
        state["atp"] = 0.5
        print(state["glucose"])  # 1.0
    """

    __slots__ = ("_chemistry", "_concentrations")

    def __init__(
        self,
        chemistry: BioChemistry,
        initial: Optional[Dict[str, float]] = None,
    ) -> None:
        """Initialize state for a chemistry.

        Args:
            chemistry: The BioChemistry defining valid molecules
            initial: Optional dict of initial concentrations by molecule name
        """
        self._chemistry = chemistry
        self._concentrations: Dict[str, float] = {}

        # Initialize all molecules to 0.0
        for name in chemistry.molecules:
            self._concentrations[name] = 0.0

        # Apply initial values
        if initial:
            for name, value in initial.items():
                if name in self._concentrations:
                    self._concentrations[name] = value
                else:
                    raise KeyError(f"Unknown molecule: {name!r}")

    @property
    def chemistry(self) -> BioChemistry:
        """The BioChemistry this state belongs to."""
        return self._chemistry

    def __getitem__(self, key: str) -> float:
        """Get concentration by molecule name."""
        return self._concentrations[key]

    def __setitem__(self, key: str, value: float) -> None:
        """Set concentration by molecule name."""
        if key not in self._concentrations:
            raise KeyError(f"Unknown molecule: {key!r}")
        self._concentrations[key] = value

    def __contains__(self, key: str) -> bool:
        """Check if molecule exists in state."""
        return key in self._concentrations

    def __iter__(self) -> Iterator[str]:
        """Iterate over molecule names."""
        return iter(self._concentrations)

    def __len__(self) -> int:
        """Number of molecules in state."""
        return len(self._concentrations)

    def get(self, key: str, default: float = 0.0) -> float:
        """Get concentration with default."""
        return self._concentrations.get(key, default)

    def get_molecule(self, molecule: BioMolecule) -> float:
        """Get concentration by molecule object."""
        return self._concentrations[molecule.local_name]

    def set_molecule(self, molecule: BioMolecule, value: float) -> None:
        """Set concentration by molecule object."""
        self[molecule.local_name] = value

    def items(self) -> Iterator[tuple[str, float]]:
        """Iterate over (name, concentration) pairs."""
        return iter(self._concentrations.items())

    def copy(self) -> State:
        """Create a copy of this state."""
        new_state = State(self._chemistry)
        new_state._concentrations = self._concentrations.copy()
        return new_state

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for serialization."""
        return {
            "chemistry": self._chemistry.local_name,
            "concentrations": self._concentrations.copy(),
        }

    @classmethod
    def from_dict(cls, chemistry: BioChemistry, data: Dict[str, Any]) -> State:
        """Create state from serialized dict."""
        return cls(chemistry, initial=data.get("concentrations", {}))

    def __repr__(self) -> str:
        """Full representation."""
        conc_str = ", ".join(
            f"{k}={v:.3g}" for k, v in self._concentrations.items()
        )
        return f"State({conc_str})"

    def __str__(self) -> str:
        """Short representation."""
        non_zero = [(k, v) for k, v in self._concentrations.items() if v > 0]
        if not non_zero:
            return "State(empty)"
        conc_str = ", ".join(f"{k}={v:.3g}" for k, v in non_zero[:5])
        if len(non_zero) > 5:
            conc_str += f", ... ({len(non_zero)} molecules)"
        return f"State({conc_str})"
