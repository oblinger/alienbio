"""Thin adapters between the existing bio classes and the neutral suite types.

These adapters wrap the EXISTING library classes (``ChemistryImpl``,
``WorldStateImpl``, ``CompartmentTreeImpl``); they do not introduce a new domain
model. The single source of truth stays with the existing classes — the neutral
:mod:`alienbio.suite.types` are a structural view.

Round-trips are defined at the NEUTRAL level:
- ``to_network(from_network(net)) == net``
- ``to_state(from_state(sv, tree)) == sv``

Reconstruction caveats (documented, and the round-trip fixtures respect them):
- A neutral :class:`~alienbio.suite.types.Species` carries ``name``, ``symbol``,
  ``bdepth``, ``molecular_weight`` as tags. ``symbol`` and ``molecular_weight``
  are *derived* from a molecule's atoms, which the neutral view does not carry;
  a molecule reconstructed by :func:`from_network` therefore has ``symbol == ""``
  and ``molecular_weight == 0.0``. Neutral round-trip fixtures use species whose
  tags reflect atom-free molecules.
- ``rate`` is opaque: it is carried through by object identity (the same object
  survives ``to_network(from_network(...))``).
- A neutral :class:`~alienbio.suite.types.StateVector` labels its axes ``c{i}`` /
  ``s{j}`` because :class:`WorldStateImpl` stores no compartment/species names.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from ..bio.chemistry import ChemistryImpl
from ..bio.compartment_tree import CompartmentTreeImpl
from ..bio.molecule import MoleculeImpl
from ..bio.reaction import ReactionImpl
from ..bio.world_state import WorldStateImpl
from ..infra.entity import MockDat
from ..protocols.bio import Chemistry, WorldState
from .types import (
    Reaction,
    ReactionNetwork,
    Species,
    StateVector,
)


def _mock_dat(path: str) -> Any:
    """A duck-typed DAT anchor for constructing atom-free entities.

    ``MockDat`` is not statically a ``Dat``; the ``Any`` return keeps the neutral
    reconstruction type-clean while matching the runtime interface Entity needs.
    """
    return MockDat(path)


def to_network(chem: Chemistry) -> ReactionNetwork:
    """Build a neutral :class:`ReactionNetwork` from a ``Chemistry``.

    Species are keyed by molecule name; molecule props (name, symbol, bdepth,
    molecular_weight) become opaque tags. Reaction stoichiometry is stored as
    ``int(coeff)``; ``rate`` is carried opaque (same object). ``modifiers`` are
    empty (the base protocol has none).
    """
    species: dict[str, Species] = {}
    for mol in chem.molecules.values():
        nid = mol.name
        species[nid] = Species(
            id=nid,
            attrs={
                "name": mol.name,
                "symbol": mol.symbol,
                "bdepth": mol.bdepth,
                "molecular_weight": mol.molecular_weight,
            },
        )

    reactions: dict[str, Reaction] = {}
    for rxn in chem.reactions.values():
        reactants = tuple((mol.name, int(coeff)) for mol, coeff in rxn.reactants.items())
        products = tuple((mol.name, int(coeff)) for mol, coeff in rxn.products.items())
        reactions[rxn.name] = Reaction(
            id=rxn.name,
            reactants=reactants,
            products=products,
            modifiers=(),
            rate=rxn.rate,
        )

    return ReactionNetwork(species=species, reactions=reactions)


def from_network(net: ReactionNetwork) -> ChemistryImpl:
    """Reconstruct a concrete ``ChemistryImpl`` structurally equal to ``net``.

    ``symbol`` and ``molecular_weight`` tags cannot be recovered (they are
    atom-derived); the reconstructed molecules are atom-free. The opaque
    ``rate`` object is passed through unchanged (identity preserved).
    """
    molecules: dict[str, MoleculeImpl] = {}
    for sid, sp in net.species.items():
        name = str(sp.attrs.get("name", sid))
        bdepth = int(sp.attrs.get("bdepth", 0))
        molecules[sid] = MoleculeImpl(
            sid,
            dat=_mock_dat(f"mol/{sid}"),
            name=name,
            bdepth=bdepth,
        )

    reactions: dict[str, ReactionImpl] = {}
    for rid, rxn in net.reactions.items():
        reactants = {molecules[n]: float(s) for n, s in rxn.reactants}
        products = {molecules[n]: float(s) for n, s in rxn.products}
        reactions[rid] = ReactionImpl(
            rid,
            reactants=reactants,
            products=products,
            rate=rxn.rate,
            dat=_mock_dat(f"rxn/{rid}"),
        )

    return ChemistryImpl(
        "network",
        molecules=molecules,
        reactions=reactions,
        dat=_mock_dat("chem/network"),
    )


def to_state(ws: WorldState) -> StateVector:
    """Build a neutral :class:`StateVector` from a ``WorldState``.

    Axes are labelled ``c{i}`` (compartments) and ``s{j}`` (species) because a
    ``WorldState`` stores no names.
    """
    data = np.asarray(ws.as_array(), dtype=np.float64).reshape(
        ws.num_compartments, ws.num_molecules
    )
    compartments = tuple(f"c{i}" for i in range(ws.num_compartments))
    species = tuple(f"s{j}" for j in range(ws.num_molecules))
    return StateVector(data=data, compartments=compartments, species=species)


def from_state(sv: StateVector, tree: CompartmentTreeImpl) -> WorldStateImpl:
    """Reconstruct a concrete ``WorldStateImpl`` from a neutral state vector.

    ``tree`` supplies the topology; it must have ``len(sv.compartments)``
    compartments. Concentrations are filled positionally from ``sv.data``.
    """
    n_mol = len(sv.species)
    flat = np.asarray(sv.data, dtype=np.float64).flatten().tolist()
    return WorldStateImpl(tree, n_mol, initial_concentrations=flat)
