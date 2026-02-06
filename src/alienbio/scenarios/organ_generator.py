"""Organ generator: build multi-compartment organisms from chemistry."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, List, Optional

from ..bio.compartment_tree import CompartmentTreeImpl
from ..bio.world_state import WorldStateImpl
from ..bio.world_simulator import WorldSimulatorImpl, ReactionSpec
from ..bio.flow import GeneralFlow

from ..bio.chemistry import ChemistryImpl

CompartmentId = int


@dataclass
class OrganSpec:
    """Specification for an organ (compartment with reactions)."""

    name: str
    reactions: List[str]  # reaction names active in this organ
    initial_concentrations: Dict[int, float]  # mol_id -> concentration


@dataclass
class TransportLink:
    """Transport link between two compartments."""

    source: CompartmentId
    target: CompartmentId
    molecule_id: int
    rate: float


@dataclass
class Organism:
    """A generated multi-compartment organism."""

    tree: CompartmentTreeImpl
    state: WorldStateImpl
    simulator: WorldSimulatorImpl
    transport_links: List[TransportLink]

    @property
    def num_compartments(self) -> int:
        return self.tree.num_compartments

    @property
    def num_transport_links(self) -> int:
        return len(self.transport_links)


def generate_organism(
    chemistry: ChemistryImpl,
    *,
    num_organs: int = 3,
    seed: Optional[int] = None,
    dt: float = 1.0,
    transport_rate: float = 0.01,
) -> Organism:
    """Generate a multi-compartment organism from a chemistry.

    Creates an organism with:
    - A root compartment ("body")
    - Multiple organ compartments as children
    - Each organ gets a subset of reactions
    - Transport links between organs for shared molecules

    Args:
        chemistry: Chemistry defining molecules and reactions
        num_organs: Number of organ compartments to create
        seed: Random seed for reproducibility
        dt: Simulation time step
        transport_rate: Rate for inter-compartment transport

    Returns:
        Organism with tree, state, simulator, and transport links
    """
    rng = random.Random(seed)

    mol_names = list(chemistry.molecules.keys())
    mol_to_id = {name: i for i, name in enumerate(mol_names)}
    num_molecules = len(mol_names)

    # Build compartment tree
    tree = CompartmentTreeImpl()
    body = tree.add_root("body")
    organs: List[CompartmentId] = []
    for i in range(num_organs):
        organ = tree.add_child(body, f"organ_{i}")
        organs.append(organ)

    # Assign reactions to organs (each reaction goes to 1-2 organs)
    reaction_specs: List[ReactionSpec] = []
    for rxn_name, reaction in chemistry.reactions.items():
        # Convert to ReactionSpec
        reactants = {}
        products = {}
        for mol, stoich in reaction.reactants.items():
            mid = mol_to_id.get(mol.name)
            if mid is not None:
                reactants[mid] = stoich
        for mol, stoich in reaction.products.items():
            mid = mol_to_id.get(mol.name)
            if mid is not None:
                products[mid] = stoich

        rate = reaction.rate if isinstance(reaction.rate, (int, float)) else 1.0

        # Assign to random organs
        n_assigned = rng.randint(1, min(2, num_organs))
        assigned = rng.sample(organs, n_assigned)

        reaction_specs.append(ReactionSpec(
            name=rxn_name,
            reactants=reactants,
            products=products,
            rate_constant=rate,
            compartments=assigned,
        ))

    # Create transport flows between adjacent organs
    transport_links: List[TransportLink] = []
    flows: List[GeneralFlow] = []

    for i in range(len(organs) - 1):
        src = organs[i]
        tgt = organs[i + 1]
        # Transport a random molecule in both directions
        mol_id = rng.randrange(num_molecules)

        transport_links.append(TransportLink(src, tgt, mol_id, transport_rate))
        transport_links.append(TransportLink(tgt, src, mol_id, transport_rate))

        # Create GeneralFlow for transport
        def _make_flow(s: int, t: int, m: int, r: float) -> GeneralFlow:
            def apply_fn(state: WorldStateImpl, _tree: CompartmentTreeImpl, dt_: float) -> None:
                conc_src = state.get(s, m)
                transfer = conc_src * r * dt_
                state.set(s, m, max(0.0, conc_src - transfer))
                state.set(t, m, state.get(t, m) + transfer)
            return GeneralFlow(origin=s, apply_fn=apply_fn, name=f"transport_{s}_to_{t}_mol{m}")

        flows.append(_make_flow(src, tgt, mol_id, transport_rate))
        flows.append(_make_flow(tgt, src, mol_id, transport_rate))

    # Build simulator
    simulator = WorldSimulatorImpl(
        tree=tree,
        reactions=reaction_specs,
        flows=flows,
        num_molecules=num_molecules,
        dt=dt,
    )

    # Build initial state (small random concentrations in each organ)
    state = WorldStateImpl(tree=tree, num_molecules=num_molecules)
    for organ in organs:
        for mol_id in range(num_molecules):
            state.set(organ, mol_id, rng.uniform(0.0, 5.0))

    return Organism(
        tree=tree,
        state=state,
        simulator=simulator,
        transport_links=transport_links,
    )
