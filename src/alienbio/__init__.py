"""Alien Biology: a generative, parameterized testing framework for agentic
reasoning over alien biochemistries.

The framework is the ``suite`` package (worlds, tasks, briefs, the runner, the
experiment harness) over the ``bio`` core (chemistry, compartments, the
simulators), written in the ``expr`` language (``alienbio.expr``). The M1
scenario runtime (``Bio.build`` / ``run``, ``@action`` / ``@measurement``)
was deleted in M47.7 — there is one runtime.
"""

from dvc_dat import Dat

from .infra import imports  # noqa: F401 - ensures do-referenced modules are loaded
from .infra.entity import Entity
from .infra.io import IO
from .infra.mk import mk, Pegboard

from .spec_lang import biotype, get_biotype

from .bio import (
    Atom,
    Molecule,
    Reaction,
    Chemistry,
    State,
    Simulator,
    AtomImpl,
    MoleculeImpl,
    ReactionImpl,
    ChemistryImpl,
    StateImpl,
    ReferenceSimulatorImpl,
    SimulatorBase,
    COMMON_ATOMS,
    get_atom,
)

from . import config

__version__ = "0.1.0"

__all__ = [
    "Dat",
    "Entity",
    "IO",
    "mk",
    "Pegboard",
    "biotype",
    "get_biotype",
    "Atom",
    "Molecule",
    "Reaction",
    "Chemistry",
    "State",
    "Simulator",
    "AtomImpl",
    "MoleculeImpl",
    "ReactionImpl",
    "ChemistryImpl",
    "StateImpl",
    "ReferenceSimulatorImpl",
    "SimulatorBase",
    "COMMON_ATOMS",
    "get_atom",
    "config",
    "__version__",
]
