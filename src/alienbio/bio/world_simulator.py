"""WorldSimulator: multi-compartment simulation with reactions and flows."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional, Sequence, TYPE_CHECKING

from .world_state import WorldStateImpl
from .compartment_tree import CompartmentTreeImpl
from .flow import Flow
from .population import MolDelta, MultDelta, PopulationLaw
from .reaction import Modulation

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
        modulators: Dict[MoleculeId, Modulation] — non-consumed modifier species that
            scale the rate (F015 S2); empty for an unmodified reaction (the fast path).
    """

    __slots__ = ("name", "reactants", "products", "rate_constant", "compartments", "modulators")

    def __init__(
        self,
        name: str,
        reactants: Dict[MoleculeId, float],
        products: Dict[MoleculeId, float],
        rate_constant: float = 1.0,
        compartments: Optional[List[CompartmentId]] = None,
        modulators: Optional[Dict[MoleculeId, Modulation]] = None,
    ) -> None:
        self.name = name
        self.reactants = reactants
        self.products = products
        self.rate_constant = rate_constant
        self.compartments = compartments  # None means all compartments
        self.modulators = modulators or {}  # empty by default — the no-modifier fast path


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

    __slots__ = ("_tree", "_reactions", "_flows", "_population_laws", "_num_molecules", "_dt")

    def __init__(
        self,
        tree: CompartmentTreeImpl,
        reactions: List[ReactionSpec],
        flows: Sequence[Flow],
        num_molecules: int,
        dt: float = 1.0,
        population_laws: Optional[Sequence[PopulationLaw]] = None,
    ) -> None:
        """Initialize world simulator.

        Args:
            tree: Compartment topology
            reactions: List of reaction specifications
            flows: List of flow specifications
            num_molecules: Number of molecules in vocabulary
            dt: Time step size
            population_laws: Optional list of count-based rate-law records driving
                the multiplicity axis (F017); empty (the default) is the fast path —
                ``step`` skips the population pass entirely, so an existing world is
                byte-identical.
        """
        self._tree = tree
        self._reactions = reactions
        self._flows = flows
        self._population_laws = population_laws or []
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
    def flows(self) -> Sequence[Flow]:
        """Flow specifications."""
        return self._flows

    @property
    def population_laws(self) -> Sequence[PopulationLaw]:
        """Count-based rate-law records driving the multiplicity axis (F017)."""
        return self._population_laws

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

        # Apply the population pass (F017 — the FIRST multiplicity-update path).
        # Empty is the fast path: no allocation, byte-identical to every world
        # built before this field existed.
        if self._population_laws:
            self._apply_population_laws(new_state, state)

        return new_state

    def _apply_population_laws(
        self,
        new_state: WorldStateImpl,
        frozen: WorldStateImpl,
    ) -> None:
        """Apply every population law's Δmultiplicity/Δconcentration together
        (F017 Q1=A — a separate per-compartment pass, order-independent).

        Each law's :meth:`~alienbio.bio.population.PopulationLaw.contribute` reads
        ONLY the frozen start-of-step state and accumulates into the two delta
        dicts; only after every law has contributed are the accumulated totals
        written to ``new_state``. This lets several laws touch the same
        compartment/pool in one step (e.g. growth and death on the same
        population) without one law's write clobbering another's read of the
        frozen baseline.
        """
        mult_delta: MultDelta = {}
        mol_delta: MolDelta = {}
        for law in self._population_laws:
            law.contribute(frozen, self._dt, mult_delta, mol_delta)

        for comp, delta in mult_delta.items():
            new_state.set_multiplicity(comp, new_state.get_multiplicity(comp) + delta)
        for (comp, mol), delta in mol_delta.items():
            new_state.set(comp, mol, new_state.get(comp, mol) + delta)

    def _desired_extent(
        self,
        frozen: WorldStateImpl,
        reaction: ReactionSpec,
        compartment: CompartmentId,
    ) -> float:
        """Pre-rationing reaction extent for one step — the rate-law → extent seam (F012 Q3).

        The sole rate law today is constant mass-action:
        ``rate_constant * Π conc**stoich * dt`` from the frozen start-of-step state, floored
        at 0. A future count-based (per-capita / zeroth-order, for volumeless containers) or
        catalytic law adds a branch here keyed on the reaction's rate-law kind; the
        competition / proportional-rationing machinery in ``_apply_reactions`` is unaffected,
        because it consumes only the returned extent.

        Bidirectional modulation (F015 S2) multiplies in a second, independent factor: a
        reaction with no modulators (the common case) hits the ``modulators`` emptiness
        check and skips straight past it — no added allocation, no changed result.
        """
        rate = reaction.rate_constant
        for mol_id, stoich in reaction.reactants.items():
            rate *= frozen.get(compartment, mol_id) ** stoich
        if reaction.modulators:
            rate *= self._modulation_factor(frozen, reaction.modulators, compartment)
        rate *= self._dt
        return max(0.0, rate)

    @staticmethod
    def _modulation_factor(
        frozen: WorldStateImpl,
        modulators: Dict[MoleculeId, Modulation],
        compartment: CompartmentId,
    ) -> float:
        """Dimensionless rate-modulation factor from non-consumed modifier species.

        LINEAR form (F015 Q1): each ``"activator"`` (param ``a``) multiplies the
        numerator by ``(1 + a * [modifier])``; each ``"inhibitor"`` (param ``Ki``)
        multiplies the denominator by ``(1 + [modifier] / Ki)`` — one modifier of each kind
        reduces to ``(1 + a*[A]) / (1 + [I]/Ki)``.

        SATURABLE forms (M38.3), each an independent multiplicative term keyed off the
        modifier's own concentration (same convention as the linear kinds above):
        ``"michaelis"`` contributes ``Vmax * [modifier] / (K + [modifier])`` (hyperbolic
        saturation, the pattern-block seam for ``EnzymeBlock``); ``"hill"`` contributes
        ``Vmax * [modifier]**n / (K**n + [modifier]**n)`` (cooperative/sigmoidal, the seam
        for ``CooperativeBindingBlock``). A zero denominator (``K == 0`` and ``[modifier]
        == 0``) contributes ``0.0`` rather than raising.

        Any other kind (including the label-only default) is inert. Pure function of the
        FROZEN start-of-step state (F015 Q4): deterministic, order-independent (H4).
        """
        numerator = 1.0
        denominator = 1.0
        saturable = 1.0
        for mol_id, modulation in modulators.items():
            conc = frozen.get(compartment, mol_id)
            if modulation.kind == "activator" and modulation.a is not None:
                numerator *= 1.0 + modulation.a * conc
            elif modulation.kind == "inhibitor" and modulation.Ki is not None:
                denominator *= 1.0 + conc / modulation.Ki
            elif (
                modulation.kind == "michaelis"
                and modulation.Vmax is not None
                and modulation.K is not None
            ):
                denom = modulation.K + conc
                saturable *= (modulation.Vmax * conc / denom) if denom > 0.0 else 0.0
            elif (
                modulation.kind == "hill"
                and modulation.Vmax is not None
                and modulation.K is not None
                and modulation.n is not None
            ):
                conc_n = conc ** modulation.n
                denom = modulation.K ** modulation.n + conc_n
                saturable *= (modulation.Vmax * conc_n / denom) if denom > 0.0 else 0.0
        return saturable * numerator / denominator

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
        # 1. Desired extent per reaction from the frozen state (via the rate-law seam).
        desired: List[float] = [
            self._desired_extent(frozen, reaction, compartment) for reaction in reactions
        ]

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
        flows: Optional[Sequence[Flow]] = None,
        dt: float = 1.0,
        population_laws: Optional[Sequence[PopulationLaw]] = None,
    ) -> WorldSimulatorImpl:
        """Create simulator from a Chemistry and compartment tree.

        Args:
            chemistry: Chemistry containing molecules and reactions
            tree: Compartment topology
            flows: Optional list of flows (empty if not provided)
            dt: Time step
            population_laws: Optional list of count-based rate-law records (F017;
                empty if not provided — the no-op fast path)

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

            # Compile modulators (non-consumed modifier species that scale the rate —
            # F015 S2). A bare str role tag coerces to a label-only, rate-inert
            # Modulation (factor 1.0); reactions with no modifiers compile to an empty
            # dict, hitting the fast path in _desired_extent.
            modulators = {}
            for mol, mod_value in reaction.modifiers.items():
                mol_id = mol_to_id.get(mol.name)
                if mol_id is None:
                    raise KeyError(
                        f"Reaction {rxn_name!r}: modifier {mol.name!r} not found in "
                        f"chemistry.molecules"
                    )
                modulators[mol_id] = Modulation.from_value(mod_value)

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
                modulators=modulators,
            ))

        return cls(
            tree=tree,
            reactions=reaction_specs,
            flows=flows or [],
            num_molecules=len(mol_names),
            dt=dt,
            population_laws=population_laws or [],
        )

    def __repr__(self) -> str:
        """Full representation."""
        return (
            f"WorldSimulatorImpl(compartments={self._tree.num_compartments}, "
            f"molecules={self._num_molecules}, "
            f"reactions={len(self._reactions)}, "
            f"flows={len(self._flows)}, population_laws={len(self._population_laws)}, "
            f"dt={self._dt})"
        )
