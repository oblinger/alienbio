"""Protocol definitions for the alienbio system.

One module, ``bio``: Atom, Molecule, Reaction, Flow, GeneralFlow, Chemistry,
CompartmentTree, WorldState, Simulator — the nine Protocols the classes in
``alienbio.bio`` satisfy (``_conformance.py`` holds them to it under pyright).
The infra layer (``Entity``, ``IO``) is concrete classes, not Protocols; the
suite's Protocols live in ``alienbio.suite``.

Usage:
    from alienbio.protocols import Atom, Molecule, Reaction, Chemistry
    from alienbio.protocols.bio import Atom, Molecule, Reaction
    from alienbio.protocols.bio import Simulator
"""

# Bio protocols
from .bio import (
    Atom,
    Molecule,
    Reaction,
    Flow,
    GeneralFlow,
    Chemistry,
    CompartmentTree,
    WorldState,
    Simulator,
)


__all__ = [
    # Bio protocols
    "Atom",
    "Molecule",
    "Reaction",
    "Flow",
    "GeneralFlow",
    "Chemistry",
    "CompartmentTree",
    "WorldState",
    "Simulator",
]
