"""Chemistry: container for atoms, molecules, and reactions."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, TYPE_CHECKING, Self

from ..infra import graph_ops
from ..infra.entity import Entity

if TYPE_CHECKING:
    from dvc_dat import Dat

from .atom import AtomImpl
from .molecule import MoleculeImpl
from .reaction import ReactionImpl


def _mock_dat(path: str) -> Any:
    """A duck-typed DAT anchor for constructing derived entities.

    ``MockDat`` is not statically a ``Dat``; the ``Any`` return matches the
    runtime interface Entity needs while staying type-clean (the same idiom the
    suite adapters use).
    """
    from ..infra.entity import MockDat

    return MockDat(path)


def _reaction_graph_view(chem: "ChemistryImpl") -> graph_ops.GraphView:
    """Adapt a chemistry into a neutral bipartite graph view.

    Reads only ``molecules`` / ``reactions``. Node ids are molecule / reaction
    ``name``s; a reaction's incidence is its reactant + product molecule names
    (the base protocol carries no modifiers); a molecule's match key is
    ``(name, symbol, bdepth, molecular_weight)`` — the same properties the neutral
    view tags a species with, so ``match`` agrees across both representations.
    """
    incidence = {
        rxn.name: frozenset(
            [m.name for m in rxn.reactants] + [m.name for m in rxn.products]
        )
        for rxn in chem.reactions.values()
    }
    species_key = {
        mol.name: (mol.name, mol.symbol, mol.bdepth, mol.molecular_weight)
        for mol in chem.molecules.values()
    }
    return graph_ops.GraphView(
        species_ids=tuple(mol.name for mol in chem.molecules.values()),
        reaction_ids=tuple(rxn.name for rxn in chem.reactions.values()),
        incidence=incidence,
        species_key=species_key,
    )


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

    @classmethod
    def hydrate(
        cls,
        data: dict[str, Any],
        *,
        dat: Optional[Dat] = None,
        parent: Optional[Entity] = None,
        local_name: Optional[str] = None,
    ) -> Self:
        """Create a Chemistry from a dict.

        Recursively hydrates molecules and reactions from nested dicts.

        Args:
            data: Dict with keys: molecules, reactions, atoms, description
                  Each molecule/reaction can be a dict that gets hydrated.
            dat: DAT anchor (if root entity)
            parent: Parent entity (if child)
            local_name: Override name

        Returns:
            New ChemistryImpl with hydrated molecules and reactions
        """
        from ..infra.entity import MockDat

        name = local_name or data.get("name", "chemistry")

        # Create mock dat if needed
        if dat is None and parent is None:
            dat = MockDat(f"chem/{name}")

        # Extract molecules and reactions data
        molecules_data = data.get("molecules", {})
        reactions_data = data.get("reactions", {})

        # First pass: hydrate molecules
        molecules: Dict[str, MoleculeImpl] = {}
        for mol_key, mol_data in molecules_data.items():
            if isinstance(mol_data, dict):
                molecules[mol_key] = MoleculeImpl.hydrate(
                    mol_data,
                    local_name=mol_key,
                )
            else:
                # Simple name, create basic molecule
                molecules[mol_key] = MoleculeImpl.hydrate(
                    {"name": mol_key},
                    local_name=mol_key,
                )

        # Second pass: hydrate reactions (needs molecules)
        reactions: Dict[str, ReactionImpl] = {}
        for rxn_key, rxn_data in reactions_data.items():
            if isinstance(rxn_data, dict):
                reactions[rxn_key] = ReactionImpl.hydrate(
                    rxn_data,
                    molecules=molecules,
                    local_name=rxn_key,
                )
            else:
                # M8-residual: a non-dict reaction entry was previously dropped
                # silently, turning a malformed/typo'd spec into a chemistry with
                # missing reactions. Fail loudly instead.
                raise ValueError(
                    f"Reaction '{rxn_key}' must be a mapping, got "
                    f"{type(rxn_data).__name__}: {rxn_data!r}"
                )

        return cls(
            name,
            molecules=molecules,
            reactions=reactions,
            parent=parent,
            dat=dat,
            description=data.get("description", ""),
        )

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

    # ─────────────────────────────────────────────────────────────────────
    # Graph queries — the reaction network is the bipartite graph of
    # molecules (species nodes) and reactions (reaction nodes). Node ids are
    # molecule/reaction ``name``s. Delegates to the shared neutral algorithms
    # in :mod:`alienbio.infra.graph_ops` (single source of truth, shared with
    # the neutral ``ReactionNetwork`` view).
    # ─────────────────────────────────────────────────────────────────────

    def neighbors(self, node: str) -> set[str]:
        """Molecule<->reaction adjacency (bipartite), by name."""
        return graph_ops.neighbors(_reaction_graph_view(self), node)

    def paths(self, a: str, b: str, max_len: int = 8) -> List[List[str]]:
        """All simple paths (by name) from ``a`` to ``b`` within ``max_len`` edges."""
        return graph_ops.paths(_reaction_graph_view(self), a, b, max_len)

    def subgraph(self, nodes: Iterable[str]) -> "ChemistryImpl":
        """The induced sub-chemistry over ``nodes`` (edges to dropped nodes removed).

        Reuses the surviving molecule objects; rebuilds each surviving reaction
        with its reactant/product entries filtered to the kept molecules (rate is
        carried through by identity). All atoms are retained (they are not graph
        nodes).
        """
        node_set = set(nodes)
        kept_species, kept_reactions = graph_ops.subgraph_selection(
            _reaction_graph_view(self), node_set
        )
        name_to_mol = {mol.name: mol for mol in self.molecules.values()}
        name_to_rxn = {rxn.name: rxn for rxn in self.reactions.values()}

        new_molecules: Dict[str, MoleculeImpl] = {
            name: name_to_mol[name] for name in kept_species
        }
        new_reactions: Dict[str, ReactionImpl] = {}
        for rname in kept_reactions:
            rxn = name_to_rxn[rname]
            new_reactions[rname] = ReactionImpl(
                rname,
                reactants={
                    m: c for m, c in rxn.reactants.items() if m.name in node_set
                },
                products={
                    m: c for m, c in rxn.products.items() if m.name in node_set
                },
                rate=rxn.rate,
                dat=_mock_dat(f"rxn/{rname}"),
            )
        return ChemistryImpl(
            "subgraph",
            atoms=self.atoms.copy(),
            molecules=new_molecules,
            reactions=new_reactions,
            dat=_mock_dat("chem/subgraph"),
        )

    def match(self, pattern: "ChemistryImpl") -> List[Dict[str, str]]:
        """All subgraph embeddings of ``pattern`` into this chemistry.

        Molecules match on ``(name, symbol, bdepth, molecular_weight)`` equality,
        reactions structurally; injectivity and every pattern edge are enforced.
        Returns each embedding as ``{pattern_name: host_name}``; ``[]`` if none.
        """
        return graph_ops.match(
            _reaction_graph_view(self), _reaction_graph_view(pattern)
        )

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
