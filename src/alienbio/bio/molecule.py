"""Molecule: entities representing chemical species."""

from __future__ import annotations

from typing import Any, Dict, Optional, TYPE_CHECKING, Self

from ..infra.entity import Entity
from .atom import AtomImpl

if TYPE_CHECKING:
    from dvc_dat import Dat



class MoleculeImpl(Entity, head="Molecule"):
    """Implementation: A molecule in the biological system.

    Molecules are composed of atoms and participate in reactions.

    Attributes:
        atoms: Atom composition as {AtomImpl: count}
        bdepth: Biosynthetic depth (0 = primitive, higher = more complex)
        name: Human-readable name (e.g., 'glucose', 'water')
        symbol: Chemical formula derived from atoms (e.g., 'C6H12O6', 'H2O')
        molecular_weight: Computed from atom weights
    """

    __slots__ = ("_atoms", "_bdepth", "_name")

    def __init__(
        self,
        local_name: str,
        *,
        parent: Optional[Entity] = None,
        dat: Optional[Dat] = None,
        description: str = "",
        atoms: Optional[Dict[AtomImpl, int]] = None,
        bdepth: int = 0,
        name: Optional[str] = None,
    ) -> None:
        """Initialize a molecule.

        Args:
            local_name: Local name within parent (used as entity identifier)
            parent: Link to containing entity
            dat: DAT anchor for root molecules
            description: Human-readable description
            atoms: Atom composition as {AtomImpl: count}
            bdepth: Biosynthetic depth (0 = primitive)
            name: Human-readable name (defaults to local_name)
        """
        super().__init__(local_name, parent=parent, dat=dat, description=description)
        self._atoms: Dict[AtomImpl, int] = atoms.copy() if atoms else {}
        self._bdepth = bdepth
        self._name = name if name is not None else local_name

    @classmethod
    def hydrate(
        cls,
        data: dict[str, Any],
        *,
        dat: Optional[Dat] = None,
        parent: Optional[Entity] = None,
        local_name: Optional[str] = None,
    ) -> Self:
        """Create a Molecule from a dict.

        Args:
            data: Dict with optional keys: name, bdepth, atoms, description
            dat: DAT anchor (if root entity)
            parent: Parent entity (if child)
            local_name: Override name (defaults to data["name"])

        Returns:
            New MoleculeImpl instance
        """
        from ..infra.entity import _MockDat

        name = local_name or data.get("name", "molecule")

        # Create mock dat if needed
        if dat is None and parent is None:
            dat = _MockDat(f"mol/{name}")

        return cls(
            name,
            parent=parent,
            dat=dat,
            description=data.get("description", ""),
            bdepth=data.get("bdepth", 0),
            # atoms not hydrated here - would need atom registry
        )

    @property
    def atoms(self) -> Dict[AtomImpl, int]:
        """Atom composition: {atom: count}."""
        return self._atoms.copy()

    @property
    def bdepth(self) -> int:
        """Biosynthetic depth (0 = primitive, 4+ = complex)."""
        return self._bdepth

    @property
    def name(self) -> str:
        """Human-readable name: 'glucose', 'water'."""
        return self._name

    @property
    def symbol(self) -> str:
        """Chemical formula derived from atoms: 'C6H12O6', 'H2O'.

        Atoms are ordered by Hill system: C first, then H, then alphabetically.
        """
        if not self._atoms:
            return ""

        # Hill system: C first, then H, then alphabetically
        parts = []
        symbols_counts = [(atom.symbol, count) for atom, count in self._atoms.items()]

        # Sort: C first, H second, rest alphabetically
        def sort_key(item: tuple) -> tuple:
            sym = item[0]
            if sym == "C":
                return (0, sym)
            elif sym == "H":
                return (1, sym)
            else:
                return (2, sym)

        symbols_counts.sort(key=sort_key)

        for sym, count in symbols_counts:
            if count == 1:
                parts.append(sym)
            else:
                parts.append(f"{sym}{count}")

        return "".join(parts)

    @property
    def molecular_weight(self) -> float:
        """Molecular mass computed from atom weights."""
        return sum(
            atom.atomic_weight * count
            for atom, count in self._atoms.items()
        )

    def attributes(self) -> Dict[str, Any]:
        """Semantic content of this molecule."""
        result = super().attributes()
        if self._atoms:
            # Serialize atoms as {symbol: count} for readability
            result["atoms"] = {atom.symbol: count for atom, count in self._atoms.items()}
        if self._bdepth != 0:
            result["bdepth"] = self._bdepth
        if self._name != self._local_name:
            result["display_name"] = self._name
        return result

    def __repr__(self) -> str:
        """Full representation."""
        parts = [f"local_name={self._local_name!r}"]
        if self._name != self._local_name:
            parts.append(f"name={self._name!r}")
        if self._atoms:
            parts.append(f"symbol={self.symbol!r}")
        if self._bdepth != 0:
            parts.append(f"bdepth={self._bdepth}")
        if self.description:
            parts.append(f"description={self.description!r}")
        return f"MoleculeImpl({', '.join(parts)})"
