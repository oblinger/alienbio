"""Alien Biology: A framework for testing agentic AI reasoning."""

from dvc_dat import Dat

from .infra import imports  # noqa: F401 - ensures do-referenced modules are loaded

from .infra.entity import Entity
from .infra.io import IO

# Standard runner for DATs
from .run import run

# Spec Language module exports
from .spec_lang import (
    # Bio singleton and class
    bio,
    Bio,
    # Decorators
    biotype,
    fn,
    scoring,
    action,
    measurement,
    rate,
    # Registry access
    get_biotype,
    get_action,
    get_measurement,
    get_scoring,
    get_rate,
    # Evaluation system (new)
    Evaluable,
    Quoted,
    Reference,
    Include,
    hydrate,
    dehydrate,
    EvalContext,
    eval_node,
    make_context,
    # Loader functions
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
    ReferenceSimulatorImpl,
    # Abstract base class for subclassing
    SimulatorBase,
    # Atom utilities
    COMMON_ATOMS,
    get_atom,
)

# Config module - API key management
from . import config

__version__ = "0.1.0"

__all__ = [
    # Infrastructure
    "Dat",
    "Entity",
    "IO",
    "run",
    # Bio singleton and class
    "bio",
    "Bio",
    # Decorators
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
    # Evaluation system (primary API)
    "Evaluable",
    "Quoted",
    "Reference",
    "Include",
    "hydrate",
    "dehydrate",
    "EvalContext",
    "eval_node",
    "make_context",
    # Loader functions
    "transform_typed_keys",
    "expand_defaults",
    # Biology protocols (for type hints)
    "Atom",
    "Molecule",
    "Reaction",
    "Chemistry",
    "State",
    "Simulator",
    # Biology implementation classes
    "AtomImpl",
    "MoleculeImpl",
    "ReactionImpl",
    "ChemistryImpl",
    "StateImpl",
    "ReferenceSimulatorImpl",
    "SimulatorBase",
    # Atom utilities
    "COMMON_ATOMS",
    "get_atom",
]
