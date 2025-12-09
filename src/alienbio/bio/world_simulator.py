"""WorldSimulator: multi-compartment simulation with reactions and flows."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

from .world_state import WorldStateImpl
from .compartment_tree import CompartmentTreeImpl
from .flow import FlowImpl

if TYPE_CHECKING:
    from .chemistry import ChemistryImpl
    from .molecule import MoleculeImpl

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
        flows = [FlowImpl(child=cell, molecule=0, rate_constant=0.05)]

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
        flows: List[FlowImpl],
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
    def flows(self) -> List[FlowImpl]:
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

        # Apply reactions in each compartment
        for reaction in self._reactions:
            compartments = reaction.compartments
            if compartments is None:
                compartments = range(self._tree.num_compartments)

            for comp in compartments:
                self._apply_reaction(new_state, reaction, comp)

        # Apply flows between compartments
        for flow in self._flows:
            flow.apply(new_state, self._tree, self._dt)

        return new_state

    def _apply_reaction(
        self,
        state: WorldStateImpl,
        reaction: ReactionSpec,
        compartment: CompartmentId,
    ) -> None:
        """Apply a single reaction in a compartment."""
        # Compute rate using mass-action kinetics
        rate = reaction.rate_constant
        for mol_id, stoich in reaction.reactants.items():
            conc = state.get(compartment, mol_id)
            rate *= conc ** stoich

        rate *= self._dt

        # Consume reactants
        for mol_id, stoich in reaction.reactants.items():
            current = state.get(compartment, mol_id)
            new_val = max(0.0, current - rate * stoich)
            state.set(compartment, mol_id, new_val)

        # Produce products
        for mol_id, stoich in reaction.products.items():
            current = state.get(compartment, mol_id)
            state.set(compartment, mol_id, current + rate * stoich)

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
        flows: Optional[List[FlowImpl]] = None,
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
                if mol_id is not None:
                    reactants[mol_id] = stoich

            for mol, stoich in reaction.products.items():
                mol_id = mol_to_id.get(mol.name)
                if mol_id is not None:
                    products[mol_id] = stoich

            # Get rate constant (only works for constant rates)
            rate = reaction.rate if isinstance(reaction.rate, (int, float)) else 1.0

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
