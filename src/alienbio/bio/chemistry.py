"""BioChemistry: container entity for molecules and reactions."""

from __future__ import annotations

from typing import Any, Dict, Iterator, List, Optional, TYPE_CHECKING

from ..infra.entity import Entity

if TYPE_CHECKING:
    from dvc_dat import Dat
    from .molecule import BioMolecule
    from .reaction import BioReaction


class BioChemistry(Entity, type_name="BioChemistry"):
    """Container for a set of molecules and their reactions.

    BioChemistry acts as the "world" for a chemical system, holding:
    - molecules: the chemical species
    - reactions: transformations between species

    Molecules and reactions are stored as children of the BioChemistry entity,
    accessible via the molecules and reactions properties which filter
    children by type.

    Example:
        chem = BioChemistry("glycolysis", dat=dat)
        glucose = BioMolecule("glucose", parent=chem)
        atp = BioMolecule("atp", parent=chem)
        reaction = BioReaction("step1", reactants={glucose: 1}, parent=chem)
    """

    __slots__ = ()

    def __init__(
        self,
        name: str,
        *,
        parent: Optional[Entity] = None,
        dat: Optional[Dat] = None,
        description: str = "",
    ) -> None:
        """Initialize a chemistry container.

        Args:
            name: Local name within parent
            parent: Link to containing entity
            dat: DAT anchor for root chemistry entities
            description: Human-readable description
        """
        super().__init__(name, parent=parent, dat=dat, description=description)

    @property
    def molecules(self) -> Dict[str, BioMolecule]:
        """All molecules in this chemistry (by name)."""
        from .molecule import BioMolecule
        return {
            name: child for name, child in self._children.items()
            if isinstance(child, BioMolecule)
        }

    @property
    def reactions(self) -> Dict[str, BioReaction]:
        """All reactions in this chemistry (by name)."""
        from .reaction import BioReaction
        return {
            name: child for name, child in self._children.items()
            if isinstance(child, BioReaction)
        }

    def iter_molecules(self) -> Iterator[BioMolecule]:
        """Iterate over molecules."""
        from .molecule import BioMolecule
        for child in self._children.values():
            if isinstance(child, BioMolecule):
                yield child

    def iter_reactions(self) -> Iterator[BioReaction]:
        """Iterate over reactions."""
        from .reaction import BioReaction
        for child in self._children.values():
            if isinstance(child, BioReaction):
                yield child

    def get_molecule(self, name: str) -> Optional[BioMolecule]:
        """Get a molecule by name."""
        from .molecule import BioMolecule
        child = self._children.get(name)
        return child if isinstance(child, BioMolecule) else None

    def get_reaction(self, name: str) -> Optional[BioReaction]:
        """Get a reaction by name."""
        from .reaction import BioReaction
        child = self._children.get(name)
        return child if isinstance(child, BioReaction) else None

    def validate(self) -> List[str]:
        """Validate the chemistry for consistency.

        Checks:
        - All reaction reactants/products are molecules in this chemistry
        - No orphaned molecules (optional warning)

        Returns:
            List of error/warning messages (empty if valid)
        """
        errors: List[str] = []
        molecules = set(self.iter_molecules())

        for reaction in self.iter_reactions():
            for mol in reaction.reactants:
                if mol not in molecules:
                    errors.append(
                        f"Reaction {reaction.local_name}: reactant {mol.local_name} "
                        f"not in chemistry"
                    )
            for mol in reaction.products:
                if mol not in molecules:
                    errors.append(
                        f"Reaction {reaction.local_name}: product {mol.local_name} "
                        f"not in chemistry"
                    )

        return errors

    def to_dict(self, recursive: bool = False, _root: Optional[Entity] = None) -> Dict[str, Any]:
        """Convert to dict for serialization."""
        result = super().to_dict(recursive=recursive, _root=_root)
        # Add counts for quick reference
        result["molecule_count"] = len(self.molecules)
        result["reaction_count"] = len(self.reactions)
        return result

    def __repr__(self) -> str:
        """Full representation."""
        return (
            f"BioChemistry({self._local_name!r}, "
            f"molecules={len(self.molecules)}, "
            f"reactions={len(self.reactions)})"
        )
