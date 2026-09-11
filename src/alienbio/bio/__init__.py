"""Bio module: the chemistry substrate alienbio's instrument runs on.

Protocols (for type hints) — from ``alienbio.protocols.bio``; the
implementations conform under ``pyright src/`` (``protocols/_conformance``):
- Atom, Molecule, Reaction, Chemistry: the entities
- Flow: transport between compartments (``TransportFlux``, ``GeneralFlow``)
- CompartmentTree, WorldState: topology and the dense multi-compartment store
- Simulator: the reference and JAX steppers, which must agree to 1e-9

Implementations:
- AtomImpl, MoleculeImpl, ReactionImpl (+ Modulation), ChemistryImpl
- CompartmentImpl, CompartmentTreeImpl, WorldStateImpl
- WorldImpl: the declarative world and its single resolution point
- WorldSimulatorImpl / ReactionSpec, and ``jax_simulator.JaxWorldSimulator``
- TransportFlux, GeneralFlow; PerCapitaGrowth / PerCapitaDeath / CountFlow
- conservation / energy canaries, the compiled rate grammar (``rate_expr``)

The M1 single-compartment runtime that used to live beside these
(``ReferenceSimulatorImpl``, ``BioSystem``, ``StateImpl``, the agent/task
layer, equilibrium/perturbation/quiescence analysis, ``MembraneFlow``) was
deleted in T056 (2026-09-10): it ran a different physics from the world
simulator and nothing on the instrument's path imported it.
"""

# Protocols (for type hints) - from central protocols module
from ..protocols.bio import (
    # Type aliases
    MoleculeId,
    CompartmentId,
    # Core protocols
    Atom,
    Molecule,
    Reaction,
    Chemistry,
    CompartmentTree,
    WorldState,
    Simulator,
)

# MockDat - lightweight mock for creating entities without a real catalog
from ..infra.entity import MockDat

# mk - terse maker pegboard; importing .makers registers the M/R/C makers
from ..infra.mk import mk
from . import makers as _makers  # noqa: F401 - registers mk.M / mk.R / mk.C on import

# Implementation classes - atoms and molecules
from .atom import AtomImpl, COMMON_ATOMS, get_atom
from .molecule import MoleculeImpl

# Implementation classes - reactions and flows. `Flow` here is the ABC every
# flow subclasses (the Protocol of the same name is `protocols.bio.Flow`;
# re-exporting both under one name shadowed the Protocol — T054/T056).
from .reaction import ReactionImpl, Modulation
from .flow import Flow, GeneralFlow, TransportFlux

# Implementation classes - containers and compartments
from .chemistry import ChemistryImpl
from .compartment import CompartmentImpl
from .compartment_tree import CompartmentTreeImpl

# Implementation classes - the world store and simulation
from .world_state import WorldStateImpl
from .world_simulator import WorldSimulatorImpl, ReactionSpec

# Population laws (F017)
from .population import CountFlow, PerCapitaDeath, PerCapitaGrowth, PopulationLaw

__all__ = [
    # Type aliases
    "MoleculeId",
    "CompartmentId",
    # Protocols (for type hints)
    "Atom",
    "Molecule",
    "Reaction",
    "Chemistry",
    "CompartmentTree",
    "WorldState",
    "Simulator",
    # Implementation classes
    "AtomImpl",
    "MoleculeImpl",
    "ReactionImpl",
    "Modulation",
    "Flow",
    "GeneralFlow",
    "TransportFlux",
    "ChemistryImpl",
    "CompartmentImpl",
    "CompartmentTreeImpl",
    "WorldStateImpl",
    "WorldSimulatorImpl",
    "ReactionSpec",
    "PopulationLaw",
    "PerCapitaGrowth",
    "PerCapitaDeath",
    "CountFlow",
    # Atom utilities
    "COMMON_ATOMS",
    "get_atom",
    # MockDat
    "MockDat",
    # mk maker pegboard
    "mk",
]


from typing import Optional as _Optional, TYPE_CHECKING as _TYPE_CHECKING

if _TYPE_CHECKING:
    from ..infra.io import IO

#: The IO context entities resolve orphan roots and refs through. ``None``
#: until one is attached (``alienbio.bio.io = IO()``); an entity that needs
#: it before then raises, it never invents one.
io: "_Optional[IO]" = None
