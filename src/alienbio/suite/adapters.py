"""Thin adapters between the existing bio classes and the neutral suite types.

These adapters wrap the EXISTING library classes (``WorldStateImpl``,
``CompartmentTreeImpl``); they do not introduce a new domain model. The single
source of truth stays with the existing classes — the neutral
:mod:`alienbio.suite.types` are a structural view.

Round-trip is defined at the NEUTRAL level:
- ``to_state(from_state(sv, tree)) == sv``

Reconstruction caveat (documented, and the round-trip fixtures respect it):
- A neutral :class:`~alienbio.suite.types.StateVector` labels its axes ``c{i}`` /
  ``s{j}`` because :class:`WorldStateImpl` stores no compartment/species names.
"""

from __future__ import annotations

import numpy as np

from ..bio.compartment_tree import CompartmentTreeImpl
from ..bio.world_state import WorldStateImpl
from ..protocols.bio import WorldState
from .types import StateVector


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
