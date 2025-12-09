"""BioMolecule: entities representing chemical species."""

from __future__ import annotations

from typing import Any, Dict, Optional, TYPE_CHECKING

from ..infra.entity import Entity

if TYPE_CHECKING:
    from dvc_dat import Dat


class BioMolecule(Entity, type_name="Molecule"):
    """A molecule in the biological system.

    BioMolecules are named entities with arbitrary properties.
    They participate in reactions as reactants or products.

    Attributes:
        properties: Dict of molecule-specific data (e.g., molecular weight,
                   functional groups, atom counts)
    """

    __slots__ = ("_properties",)

    def __init__(
        self,
        name: str,
        *,
        parent: Optional[Entity] = None,
        dat: Optional[Dat] = None,
        description: str = "",
        properties: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize a molecule.

        Args:
            name: Local name within parent
            parent: Link to containing entity
            dat: DAT anchor for root molecules
            description: Human-readable description
            properties: Dict of molecule-specific properties
        """
        super().__init__(name, parent=parent, dat=dat, description=description)
        self._properties: Dict[str, Any] = properties.copy() if properties else {}

    @property
    def properties(self) -> Dict[str, Any]:
        """Molecule properties (read-only copy)."""
        return self._properties.copy()

    def set_property(self, key: str, value: Any) -> None:
        """Set a property value."""
        self._properties[key] = value

    def get_property(self, key: str, default: Any = None) -> Any:
        """Get a property value."""
        return self._properties.get(key, default)

    def to_dict(self, recursive: bool = False, _root: Optional[Entity] = None) -> Dict[str, Any]:
        """Convert to dict for serialization."""
        result = super().to_dict(recursive=recursive, _root=_root)
        if self._properties:
            result["properties"] = self._properties.copy()
        return result

    def __repr__(self) -> str:
        """Full representation."""
        parts = [f"name={self._local_name!r}"]
        if self.description:
            parts.append(f"description={self.description!r}")
        if self._properties:
            parts.append(f"properties={self._properties!r}")
        return f"BioMolecule({', '.join(parts)})"
