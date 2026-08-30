 [[ABIO Architecture Docs]]

# ABIO biology
Molecules, reactions, pathways, containers, and their generators.

## Generators
Base protocols for synthetic biology factories.
- **[[Generator]]** - Base protocol for factories that produce synthetic biology components.

## Atoms and Molecules
Chemical elements and compounds in the alien biology.
- **[[ABIO Atom]]** - Chemical element with symbol, name, and atomic weight. Immutable value objects shared across molecules.
- **[[ABIO Molecule]]** - Chemical compound composed of atoms. Has biosynthetic depth, derived formula (symbol), and molecular weight.
- **[[ABIO MoleculeGenerator]]** - Factory that produces synthetic molecules with configurable properties.

## Reactions (Rust)
Transformations between molecules.
- **[[ABIO Reaction]]** - Transformation with reactants, products, effectors, and rate functions.
- **[[ABIO ReactionGenerator]]** - Factory that produces synthetic reactions with configurable kinetics.

## Chemistry
Container for molecules and reactions forming a chemical system.
- **[[ABIO Chemistry]]** - Entity that groups molecules and reactions together. Provides validation, state management, and simulation support.

## Pathways
Connected sequences of reactions (analytical abstraction).
- **[[ABIO Pathway]]** - Connected subgraph forming a metabolic function: linear chains, branching paths, cycles, or signaling cascades. Used for understanding and generating coherent reaction networks, not directly in simulation.

## Compartments (Rust)
Nestable biological structures from organelles to organisms. All are Entity subclasses.
- **[[ABIO Compartment]]** - Nestable Entity for molecules, reactions, and child containers. Kind labels: organism, organ, cell, organelle.
- **[[ABIO ContainerGenerator]]** - Composable factory for Compartments. Generators compose recursively: simple generators build complex ones.

## Simulation
Multi-compartment simulation with reactions within compartments and flows across membranes.
- **[[ABIO WorldState]]** - Dense concentration storage: `[num_compartments × num_molecules]` array. GPU-friendly, O(1) access.
- **[[ABIO CompartmentTree]]** - Hierarchical topology of compartments. Stores parent-child relationships, separated from concentrations.
- **[[ABIO Flow]]** - Membrane transport between compartments. Moves molecules across parent-child boundaries (diffusion, active transport).
- **[[ABIO WorldSimulator]]** - Multi-compartment simulation engine. Applies reactions within compartments, flows across membranes.
- **[[Simulator]]** - Legacy single-compartment simulator. See WorldSimulator for multi-compartment simulations.
- **[[State]]** - Legacy single-compartment concentrations. See WorldState for multi-compartment storage.
