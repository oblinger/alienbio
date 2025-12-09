"""Bio module: core biology classes for alienbio.

This module defines the fundamental biology abstractions:

Protocols (for type hints) - from alienbio.protocols.bio:
- Atom: protocol for atomic elements
- Molecule: protocol for molecule entities
- Reaction: protocol for reaction entities
- Flow: protocol for transport between compartments
- Chemistry: protocol for chemistry containers
- CompartmentTree: protocol for compartment topology
- WorldState: protocol for multi-compartment concentrations
- State: protocol for single-compartment concentrations (legacy)
- Simulator: protocol for simulators

Implementations:
- AtomImpl: chemical elements with symbol, name, atomic_weight
- MoleculeImpl: composed of atoms with bdepth, name, derived symbol/weight
- ReactionImpl: transformations between molecules with rates
- Flow hierarchy:
  - Flow: abstract base class for all flows
  - MembraneFlow: transport across parent-child membrane with stoichiometry
  - LateralFlow: transport between sibling compartments
- ChemistryImpl: container for atoms, molecules, and reactions
- CompartmentImpl: biological compartment with flows, concentrations, reactions
- CompartmentTreeImpl: hierarchical compartment topology (simulation)
- WorldStateImpl: multi-compartment concentration storage (simulation)
- StateImpl: single-compartment concentrations (legacy)
- SimpleSimulatorImpl: basic single-compartment simulator (legacy)
- WorldSimulatorImpl: multi-compartment simulator with flows
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
    Flow,
    Chemistry,
    CompartmentTree,
    WorldState,
    State,
    Simulator,
)

# Implementation classes - atoms and molecules
from .atom import AtomImpl, COMMON_ATOMS, get_atom
from .molecule import MoleculeImpl

# Implementation classes - reactions and flows
from .reaction import ReactionImpl
from .flow import Flow, MembraneFlow, LateralFlow, FlowImpl, MULTIPLICITY_ID

# Implementation classes - containers and compartments
from .chemistry import ChemistryImpl
from .compartment import CompartmentImpl
from .compartment_tree import CompartmentTreeImpl

# Implementation classes - state
from .world_state import WorldStateImpl
from .state import StateImpl

# Implementation classes - simulation
from .simulator import SimpleSimulatorImpl, SimulatorBase
from .world_simulator import WorldSimulatorImpl, ReactionSpec

__all__ = [
    # Type aliases
    "MoleculeId",
    "CompartmentId",
    # Protocols (for type hints)
    "Atom",
    "Molecule",
    "Reaction",
    "Flow",
    "Chemistry",
    "CompartmentTree",
    "WorldState",
    "State",
    "Simulator",
    # Implementation classes
    "AtomImpl",
    "MoleculeImpl",
    "ReactionImpl",
    "MembraneFlow",
    "LateralFlow",
    "FlowImpl",  # Alias for LateralFlow (backwards compat)
    "ChemistryImpl",
    "CompartmentImpl",
    "CompartmentTreeImpl",
    "WorldStateImpl",
    "StateImpl",
    "SimpleSimulatorImpl",
    "WorldSimulatorImpl",
    "ReactionSpec",
    # Abstract base for subclassing
    "SimulatorBase",
    # Atom utilities
    "COMMON_ATOMS",
    "get_atom",
    # Flow constants
    "MULTIPLICITY_ID",
]
