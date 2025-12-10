"""Chemistry: container for atoms, molecules, and reactions."""

from __future__ import annotations

from typing import Any, Dict, Optional, TYPE_CHECKING

from ..infra.entity import Entity

if TYPE_CHECKING:
    from dvc_dat import Dat

from .atom import AtomImpl
from .molecule import MoleculeImpl
from .reaction import ReactionImpl


class ChemistryImpl(Entity, head="Chemistry"):
    """Implementation: Container for a chemical system.

    Chemistry holds atoms, molecules, and reactions as public dict attributes.
    These are indexed by:
    - atoms: by symbol ("C", "H", "O")
    - molecules: by name ("glucose", "atp")
    - reactions: by name ("glycolysis_step1", "atp_synthesis")

    Chemistry is conceptually immutable - built complete via constructor,
    though the dicts are technically mutable for flexibility.

    Example:
        chem = ChemistryImpl(
            "glycolysis",
            atoms={"C": carbon, "H": hydrogen, "O": oxygen},
            molecules={"glucose": glucose_mol, "atp": atp_mol},
            reactions={"step1": reaction1, "step2": reaction2},
            dat=dat,
        )

        # Direct access to contents
        chem.atoms["C"]  # -> carbon atom
        chem.molecules["glucose"]  # -> glucose molecule
        chem.reactions["step1"]  # -> reaction1
    """

    __slots__ = ("atoms", "molecules", "reactions")

    # Public attributes - direct access, no property wrappers
    atoms: Dict[str, AtomImpl]
    molecules: Dict[str, MoleculeImpl]
    reactions: Dict[str, ReactionImpl]

    def __init__(
        self,
        name: str,
        *,
        atoms: Optional[Dict[str, AtomImpl]] = None,
        molecules: Optional[Dict[str, MoleculeImpl]] = None,
        reactions: Optional[Dict[str, ReactionImpl]] = None,
        parent: Optional[Entity] = None,
        dat: Optional[Dat] = None,
        description: str = "",
    ) -> None:
        """Initialize a chemistry container.

        Args:
            name: Local name within parent
            atoms: Dict of atoms by symbol
            molecules: Dict of molecules by name
            reactions: Dict of reactions by name
            parent: Link to containing entity
            dat: DAT anchor for root chemistry entities
            description: Human-readable description
        """
        super().__init__(name, parent=parent, dat=dat, description=description)
        self.atoms = atoms.copy() if atoms else {}
        self.molecules = molecules.copy() if molecules else {}
        self.reactions = reactions.copy() if reactions else {}

    def validate(self) -> list[str]:
        """Validate the chemistry for consistency.

        Checks:
        - All molecule atoms are atoms in this chemistry
        - All reaction reactants/products are molecules in this chemistry

        Returns:
            List of error messages (empty if valid)
        """
        errors: list[str] = []
        atom_set = set(self.atoms.values())
        mol_set = set(self.molecules.values())

        # Check that all molecule atoms exist in chemistry
        for mol_name, molecule in self.molecules.items():
            for atom in molecule.atoms:
                if atom not in atom_set:
                    errors.append(
                        f"Molecule {mol_name}: atom {atom.symbol} not in chemistry"
                    )

        # Check that all reaction molecules exist in chemistry
        for rxn_name, reaction in self.reactions.items():
            for mol in reaction.reactants:
                if mol not in mol_set:
                    errors.append(
                        f"Reaction {rxn_name}: reactant {mol.name} not in chemistry"
                    )
            for mol in reaction.products:
                if mol not in mol_set:
                    errors.append(
                        f"Reaction {rxn_name}: product {mol.name} not in chemistry"
                    )

        return errors

    def attributes(self) -> Dict[str, Any]:
        """Semantic content of this chemistry."""
        result = super().attributes()

        # Serialize atoms as {symbol: {name, atomic_weight}}
        if self.atoms:
            result["atoms"] = {
                sym: {"name": atom.name, "atomic_weight": atom.atomic_weight}
                for sym, atom in self.atoms.items()
            }

        # Serialize molecules by name
        if self.molecules:
            result["molecules"] = {
                name: mol.attributes()
                for name, mol in self.molecules.items()
            }

        # Serialize reactions by name
        if self.reactions:
            result["reactions"] = {
                name: rxn.attributes()
                for name, rxn in self.reactions.items()
            }

        return result

    def __repr__(self) -> str:
        """Full representation."""
        return (
            f"ChemistryImpl({self._local_name!r}, "
            f"atoms={len(self.atoms)}, "
            f"molecules={len(self.molecules)}, "
            f"reactions={len(self.reactions)})"
        )
