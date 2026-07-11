"""WorldSimulator: multi-compartment simulation with reactions and flows."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

from .world_state import WorldStateImpl
from .compartment_tree import CompartmentTreeImpl
from .flow import GeneralFlow

if TYPE_CHECKING:
    from .chemistry import ChemistryImpl
    from .molecule import MoleculeImpl

logger = logging.getLogger(__name__)

# Type aliases
MoleculeId = int
CompartmentId = int


class ReactionSpec:
    """Specification for a reaction in the world simulator.

    Reactions occur within a single compartment and transform molecules.
    This is a lightweight spec using molecule IDs for efficient simulation.

    Attributes:
        name: Human-readable name
        reactants: Dict[MoleculeId, stoichiometry]
        products: Dict[MoleculeId, stoichiometry]
        rate_constant: Base reaction rate
        compartments: Which compartments this reaction occurs in (None = all)
    """

    __slots__ = ("name", "reactants", "products", "rate_constant", "compartments")

    def __init__(
        self,
        name: str,
        reactants: Dict[MoleculeId, float],
        products: Dict[MoleculeId, float],
        rate_constant: float = 1.0,
        compartments: Optional[List[CompartmentId]] = None,
    ) -> None:
        self.name = name
        self.reactants = reactants
        self.products = products
        self.rate_constant = rate_constant
        self.compartments = compartments  # None means all compartments


class WorldSimulatorImpl:
    """Implementation: Multi-compartment simulator with reactions and flows.

    Simulates a world with:
    - Multiple compartments organized in a tree (organism > organ > cell)
    - Reactions that occur within compartments
    - Flows that transport molecules across compartment membranes

    Each step:
    1. Compute all reaction rates (per compartment)
    2. Compute all flow fluxes (between parent-child pairs)
    3. Apply reactions (modify concentrations within compartments)
    4. Apply flows (transfer molecules across membranes)

    Example:
        # Build world
        tree = CompartmentTreeImpl()
        organism = tree.add_root("organism")
        cell = tree.add_child(organism, "cell")

        # Define reactions and flows
        reactions = [ReactionSpec("r1", {0: 1}, {1: 1}, rate_constant=0.1)]
        flows = [GeneralFlow(child=cell, molecule=0, rate_constant=0.05)]

        # Create simulator
        sim = WorldSimulatorImpl(
            tree=tree,
            reactions=reactions,
            flows=flows,
            num_molecules=10,
            dt=0.1,
        )

        # Run simulation
        state = WorldStateImpl(tree=tree, num_molecules=10)
        state.set(organism, 0, 100.0)  # initial concentration
        history = sim.run(state, steps=1000, sample_every=100)

        # All states in history share the same tree reference
        assert history[0].tree is history[-1].tree
    """

    __slots__ = ("_tree", "_reactions", "_flows", "_num_molecules", "_dt")

    def __init__(
        self,
        tree: CompartmentTreeImpl,
        reactions: List[ReactionSpec],
        flows: List[GeneralFlow],
        num_molecules: int,
        dt: float = 1.0,
    ) -> None:
        """Initialize world simulator.

        Args:
            tree: Compartment topology
            reactions: List of reaction specifications
            flows: List of flow specifications
            num_molecules: Number of molecules in vocabulary
            dt: Time step size
        """
        self._tree = tree
        self._reactions = reactions
        self._flows = flows
        self._num_molecules = num_molecules
        self._dt = dt

    @property
    def tree(self) -> CompartmentTreeImpl:
        """Compartment topology."""
        return self._tree

    @property
    def reactions(self) -> List[ReactionSpec]:
        """Reaction specifications."""
        return self._reactions

    @property
    def flows(self) -> List[GeneralFlow]:
        """Flow specifications."""
        return self._flows

    @property
    def num_molecules(self) -> int:
        """Number of molecules in vocabulary."""
        return self._num_molecules

    @property
    def dt(self) -> float:
        """Time step size."""
        return self._dt

    def step(self, state: WorldStateImpl) -> WorldStateImpl:
        """Advance simulation by one time step.

        Args:
            state: Current world state

        Returns:
            New state after applying reactions and flows
        """
        new_state = state.copy()

        # Apply reactions per compartment with order-independent simultaneous
        # extent (H4). Reactions never cross compartments, so grouping by
        # compartment is equivalent to the old global loop but lets us resolve
        # competition among all reactions active in a compartment at once.
        for comp in range(self._tree.num_compartments):
            active = [
                reaction
                for reaction in self._reactions
                if reaction.compartments is None or comp in reaction.compartments
            ]
            if active:
                self._apply_reactions(new_state, state, active, comp)

        # Apply flows between compartments
        for flow in self._flows:
            flow.apply(new_state, self._tree, self._dt)

        return new_state

    def _apply_reactions(
        self,
        new_state: WorldStateImpl,
        frozen: WorldStateImpl,
        reactions: List[ReactionSpec],
        compartment: CompartmentId,
    ) -> None:
        """Apply all reactions active in a compartment simultaneously (H4).

        Desired extents are read from the FROZEN start-of-step state; shared
        reactants are rationed by single-pass proportional min-ratio scaling
        (see ReferenceSimulatorImpl for the non-negativity proof); the final
        extents are applied together to ``new_state``. This is order-independent
        and reduces to the C1 clamp when reactions do not compete.
        """
        # 1. Desired extent per reaction from the frozen state (mass-action).
        desired: List[float] = []
        for reaction in reactions:
            rate = reaction.rate_constant
            for mol_id, stoich in reaction.reactants.items():
                rate *= frozen.get(compartment, mol_id) ** stoich
            rate *= self._dt
            desired.append(max(0.0, rate))

        # 2. Competition: demand per molecule, then per-molecule feasible ratio.
        demand: Dict[MoleculeId, float] = {}
        for reaction, ext in zip(reactions, desired):
            if ext <= 0.0:
                continue
            for mol_id, stoich in reaction.reactants.items():
                if stoich > 0:
                    demand[mol_id] = demand.get(mol_id, 0.0) + ext * stoich

        ratio: Dict[MoleculeId, float] = {}
        for mol_id, dem in demand.items():
            avail = frozen.get(compartment, mol_id)
            ratio[mol_id] = min(1.0, avail / dem) if dem > 0 else 1.0

        # Each reaction scales by the tightest ratio over its reactants.
        # 3. Apply simultaneously.
        for reaction, ext in zip(reactions, desired):
            scale = 1.0
            for mol_id, stoich in reaction.reactants.items():
                if stoich > 0:
                    scale = min(scale, ratio.get(mol_id, 1.0))
            extent = ext * scale

            for mol_id, stoich in reaction.reactants.items():
                new_state.set(
                    compartment,
                    mol_id,
                    new_state.get(compartment, mol_id) - extent * stoich,
                )
            for mol_id, stoich in reaction.products.items():
                new_state.set(
                    compartment,
                    mol_id,
                    new_state.get(compartment, mol_id) + extent * stoich,
                )

    def run(
        self,
        state: WorldStateImpl,
        steps: int,
        sample_every: Optional[int] = None,
    ) -> List[WorldStateImpl]:
        """Run simulation for multiple steps.

        Args:
            state: Initial state (not modified)
            steps: Number of steps to run
            sample_every: If set, only keep every Nth state (plus final)

        Returns:
            List of states (timeline)
        """
        if sample_every is None:
            sample_every = 1

        history: List[WorldStateImpl] = []
        current = state.copy()

        for i in range(steps):
            if i % sample_every == 0:
                history.append(current.copy())
            current = self.step(current)

        # Always include final state
        history.append(current.copy())
        return history

    @classmethod
    def from_chemistry(
        cls,
        chemistry: ChemistryImpl,
        tree: CompartmentTreeImpl,
        flows: Optional[List[GeneralFlow]] = None,
        dt: float = 1.0,
    ) -> WorldSimulatorImpl:
        """Create simulator from a Chemistry and compartment tree.

        Args:
            chemistry: Chemistry containing molecules and reactions
            tree: Compartment topology
            flows: Optional list of flows (empty if not provided)
            dt: Time step

        Returns:
            Configured WorldSimulatorImpl
        """
        # Build molecule ID mapping
        mol_names = list(chemistry.molecules.keys())
        mol_to_id = {name: i for i, name in enumerate(mol_names)}

        # Convert reactions to specs
        reaction_specs = []
        for rxn_name, reaction in chemistry.reactions.items():
            reactants = {}
            products = {}

            for mol, stoich in reaction.reactants.items():
                mol_id = mol_to_id.get(mol.name)
                if mol_id is None:
                    raise KeyError(
                        f"Reaction {rxn_name!r}: reactant {mol.name!r} not found in "
                        f"chemistry.molecules"
                    )
                reactants[mol_id] = stoich

            for mol, stoich in reaction.products.items():
                mol_id = mol_to_id.get(mol.name)
                if mol_id is None:
                    raise KeyError(
                        f"Reaction {rxn_name!r}: product {mol.name!r} not found in "
                        f"chemistry.molecules"
                    )
                products[mol_id] = stoich

            # Get rate constant (only works for constant rates)
            if isinstance(reaction.rate, (int, float)):
                rate = reaction.rate
            else:
                # Callable rate laws aren't supported by the ID-based world
                # simulator; downgrading to mass-action constant 1.0 silently
                # would produce a physically wrong world, so make it loud.
                rate = 1.0
                logger.warning(
                    "Reaction %r has a callable rate law that is not a constant "
                    "number; downgrading to rate_constant=1.0 for the world "
                    "simulator (mass-action). The world will not reflect the "
                    "reaction's actual rate law.",
                    rxn_name,
                )

            reaction_specs.append(ReactionSpec(
                name=rxn_name,
                reactants=reactants,
                products=products,
                rate_constant=rate,
                compartments=None,  # Apply to all compartments
            ))

        return cls(
            tree=tree,
            reactions=reaction_specs,
            flows=flows or [],
            num_molecules=len(mol_names),
            dt=dt,
        )

    def __repr__(self) -> str:
        """Full representation."""
        return (
            f"WorldSimulatorImpl(compartments={self._tree.num_compartments}, "
            f"molecules={self._num_molecules}, "
            f"reactions={len(self._reactions)}, "
            f"flows={len(self._flows)}, dt={self._dt})"
        )
