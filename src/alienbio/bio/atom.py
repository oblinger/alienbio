"""Atom: entities representing chemical elements."""

from __future__ import annotations

from typing import Dict


class AtomImpl:
    """Implementation: A chemical element.

    Atoms are the building blocks of molecules. They are essentially constants
    representing chemical elements with their properties.

    Attributes:
        symbol: Chemical symbol (1-2 letters): 'C', 'H', 'O', 'Na'
        name: Human-readable name: 'Carbon', 'Hydrogen'
        atomic_weight: Atomic mass in atomic mass units
    """

    __slots__ = ("_symbol", "_name", "_atomic_weight")

    def __init__(
        self,
        symbol: str,
        name: str,
        atomic_weight: float,
    ) -> None:
        """Initialize an atom.

        Args:
            symbol: Chemical symbol (1-2 letters)
            name: Human-readable English name
            atomic_weight: Atomic mass in atomic mass units
        """
        if not symbol or len(symbol) > 2:
            raise ValueError(f"Symbol must be 1-2 characters, got {symbol!r}")
        self._symbol = symbol
        self._name = name
        self._atomic_weight = atomic_weight

    @property
    def symbol(self) -> str:
        """Chemical symbol (1-2 letters): 'C', 'H', 'O', 'Na'."""
        return self._symbol

    @property
    def name(self) -> str:
        """Human-readable name: 'Carbon', 'Hydrogen'."""
        return self._name

    @property
    def atomic_weight(self) -> float:
        """Atomic mass in atomic mass units."""
        return self._atomic_weight

    def __eq__(self, other: object) -> bool:
        """Atoms are equal if they have the same symbol."""
        if not isinstance(other, AtomImpl):
            return NotImplemented
        return self._symbol == other._symbol

    def __hash__(self) -> int:
        """Hash by symbol for use as dict key."""
        return hash(self._symbol)

    def __repr__(self) -> str:
        """Full representation."""
        return f"AtomImpl({self._symbol!r}, {self._name!r}, {self._atomic_weight})"

    def __str__(self) -> str:
        """Short display form."""
        return self._symbol


# Common atoms - these can be imported and used directly
# A more complete periodic table can be provided elsewhere


def _create_common_atoms() -> Dict[str, AtomImpl]:
    """Create the common atoms used in biology."""
    atoms = [
        AtomImpl("H", "Hydrogen", 1.008),
        AtomImpl("C", "Carbon", 12.011),
        AtomImpl("N", "Nitrogen", 14.007),
        AtomImpl("O", "Oxygen", 15.999),
        AtomImpl("P", "Phosphorus", 30.974),
        AtomImpl("S", "Sulfur", 32.065),
        AtomImpl("Na", "Sodium", 22.990),
        AtomImpl("K", "Potassium", 39.098),
        AtomImpl("Ca", "Calcium", 40.078),
        AtomImpl("Mg", "Magnesium", 24.305),
        AtomImpl("Cl", "Chlorine", 35.453),
        AtomImpl("Fe", "Iron", 55.845),
        AtomImpl("Zn", "Zinc", 65.38),
        AtomImpl("Cu", "Copper", 63.546),
    ]
    return {a.symbol: a for a in atoms}


# Common atoms dict for quick lookup
COMMON_ATOMS: Dict[str, AtomImpl] = _create_common_atoms()


def get_atom(symbol: str) -> AtomImpl:
    """Get an atom by its symbol.

    Args:
        symbol: Chemical symbol (e.g., 'C', 'H', 'Na')

    Returns:
        The AtomImpl for that element

    Raises:
        KeyError: If the symbol is not in COMMON_ATOMS
    """
    if symbol not in COMMON_ATOMS:
        raise KeyError(f"Unknown atom symbol: {symbol!r}")
    return COMMON_ATOMS[symbol]
