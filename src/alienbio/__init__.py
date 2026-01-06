"""Alien Biology: A framework for testing agentic AI reasoning."""

from dvc_dat import Dat

from .infra import imports  # noqa: F401 - ensures do-referenced modules are loaded

from .infra.context import (
    Context,
    _ctx,
    ctx,
    set_context,
    do,
    create,
    create_root,
    load,
    save,
    lookup,
    o,
)
from .infra.entity import Entity
from .infra.io import IO

# Standard runner for DATs
from .run import run

# Spec Language module exports
from .spec_lang import (
    Bio,
    biotype,
    fn,
    scoring,
    action,
    measurement,
    rate,
    get_biotype,
    get_action,
    get_measurement,
    get_scoring,
    get_rate,
    EvTag,
    RefTag,
    IncludeTag,
    transform_typed_keys,
    expand_defaults,
)

# Bio module exports
from .bio import (
    # Protocols (for type hints)
    Atom,
    Molecule,
    Reaction,
    Chemistry,
    State,
    Simulator,
    # Implementation classes
    AtomImpl,
    MoleculeImpl,
    ReactionImpl,
    ChemistryImpl,
    StateImpl,
    SimpleSimulatorImpl,
    # Abstract base class for subclassing
    SimulatorBase,
    # Atom utilities
    COMMON_ATOMS,
    get_atom,
)

__version__ = "0.1.0"

__all__ = [
    # Infrastructure
    "Context",
    "Dat",
    "Entity",
    "IO",
    "run",
    "_ctx",
    "ctx",
    "set_context",
    "do",
    "create",
    "create_root",
    "load",
    "save",
    "lookup",
    "o",
    # Spec Language
    "Bio",
    "biotype",
    "fn",
    "scoring",
    "action",
    "measurement",
    "rate",
    "get_biotype",
    "get_action",
    "get_measurement",
    "get_scoring",
    "get_rate",
    "EvTag",
    "RefTag",
    "IncludeTag",
    "transform_typed_keys",
    "expand_defaults",
    # Bio - Protocols (for type hints)
    "Atom",
    "Molecule",
    "Reaction",
    "Chemistry",
    "State",
    "Simulator",
    # Bio - Implementation classes
    "AtomImpl",
    "MoleculeImpl",
    "ReactionImpl",
    "ChemistryImpl",
    "StateImpl",
    "SimpleSimulatorImpl",
    # Bio - Abstract base class for subclassing
    "SimulatorBase",
    # Bio - Atom utilities
    "COMMON_ATOMS",
    "get_atom",
]
