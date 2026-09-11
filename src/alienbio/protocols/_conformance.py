"""The Protocols as a LIVE contract (T051 box 5 / T057 proposal 6).

Nothing in ``src/`` annotates a value with ``Simulator``, ``Flow`` or the
rest, so pyright had nothing to check and the exported contracts drifted
(``TransportFlux.stoichiometry`` keyed by ``int`` against a ``str``
Protocol; ``SimulatorBase.run`` without ``sample_every``). Assigning each
implementation to its Protocol here, under ``TYPE_CHECKING`` only, puts
every intended conformance in front of ``pyright src/`` -- the CI gate --
so a future drift is a red check rather than a runtime surprise. Runtime
cost: none (the block never executes).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from alienbio.bio.atom import AtomImpl
    from alienbio.bio.chemistry import ChemistryImpl
    from alienbio.bio.compartment_tree import CompartmentTreeImpl
    from alienbio.bio.flow import GeneralFlow as GeneralFlowImpl
    from alienbio.bio.flow import TransportFlux
    from alienbio.bio.jax_simulator import JaxWorldSimulator
    from alienbio.bio.molecule import MoleculeImpl
    from alienbio.bio.reaction import ReactionImpl
    from alienbio.bio.world_simulator import WorldSimulatorImpl
    from alienbio.bio.world_state import WorldStateImpl

    from .bio import (
        Atom,
        Chemistry,
        CompartmentTree,
        Flow,
        GeneralFlow,
        Molecule,
        Reaction,
        Simulator,
        WorldState,
    )

    def _conforms(
        atom: AtomImpl,
        molecule: MoleculeImpl,
        reaction: ReactionImpl,
        chemistry: ChemistryImpl,
        tree: CompartmentTreeImpl,
        state: WorldStateImpl,
        transport: TransportFlux,
        general: GeneralFlowImpl,
        reference: WorldSimulatorImpl,
        jax: JaxWorldSimulator,
    ) -> None:
        _a: Atom = atom
        _m: Molecule = molecule
        _r: Reaction = reaction
        _c: Chemistry = chemistry
        _t: CompartmentTree = tree
        _s: WorldState = state
        _f1: Flow = transport
        _f2: GeneralFlow = general
        _sim1: Simulator = reference
        _sim2: Simulator = jax
