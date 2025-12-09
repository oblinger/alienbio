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

# Bio module exports
from .bio import (
    BioMolecule,
    BioReaction,
    BioChemistry,
    State,
    Simulator,
)
from .bio.simulator import SimpleSimulator

__version__ = "0.1.0"

__all__ = [
    # Infrastructure
    "Context",
    "Dat",
    "Entity",
    "IO",
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
    # Bio
    "BioMolecule",
    "BioReaction",
    "BioChemistry",
    "State",
    "Simulator",
    "SimpleSimulator",
]
