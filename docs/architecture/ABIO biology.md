# ABIO biology
**Parent**: [[ABIO Sys]]
Molecules, reactions, pathways, containers, and their generators.

## Atoms and Molecules
Chemical elements and compounds in the alien biology.
- **[[Atom]]** - Chemical element with symbol, name, and atomic weight. Immutable value objects shared across molecules.
- **[[Molecule]]** - Chemical compound composed of atoms. Has biosynthetic depth, derived formula (symbol), and molecular weight.
- **[[MoleculeGenerator]]** - Factory that produces synthetic molecules with configurable properties.

## Reactions (Rust)
Transformations between molecules.
- **[[Reaction]]** - Transformation with reactants, products, effectors, and rate functions.
- **[[ReactionGenerator]]** - Factory that produces synthetic reactions with configurable kinetics.

## Chemistry
Container for molecules and reactions forming a chemical system.
- **[[Chemistry]]** - Entity that groups molecules and reactions together. Provides validation, state management, and simulation support.

## Pathways
Connected sequences of reactions (analytical abstraction).
- **[[Pathway]]** - Connected subgraph forming a metabolic function: linear chains, branching paths, cycles, or signaling cascades. Used for understanding and generating coherent reaction networks, not directly in simulation.

## Compartments (Rust)
Nestable biological structures from organelles to organisms. All are Entity subclasses.
- **[[Compartment]]** - Nestable Entity for molecules, reactions, and child containers. Kind labels: organism, organ, cell, organelle.
- **[[ContainerGenerator]]** - Composable factory for Compartments. Generators compose recursively: simple generators build complex ones.

## Simulation
Multi-compartment simulation with reactions within compartments and flows across membranes.
- **[[WorldState]]** - Dense concentration storage: `[num_compartments × num_molecules]` array. GPU-friendly, O(1) access.
- **[[CompartmentTree]]** - Hierarchical topology of compartments. Stores parent-child relationships, separated from concentrations.
- **[[Flow]]** - Membrane transport between compartments. Moves molecules across parent-child boundaries (diffusion, active transport).
- **[[WorldSimulator]]** - Multi-compartment simulation engine. Applies reactions within compartments, flows across membranes.
- **[[Simulator]]** - Legacy single-compartment simulator. See WorldSimulator for multi-compartment simulations.
- **[[State]]** - Legacy single-compartment concentrations. See WorldState for multi-compartment storage.
