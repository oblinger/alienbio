# ABIO biology
**Parent**: [[ABIO Sys]]
Molecules, reactions, pathways, containers, and their generators.

## Molecules (Rust)
Chemical compounds in the alien biology.
- **[[BioMolecule]]** - Chemical compound with atoms, bonds, and properties. Organized by biosynthetic depth.
- **[[MoleculeGenerator]]** - Factory that produces synthetic molecules with configurable properties.

## Reactions (Rust)
Transformations between molecules.
- **[[BioReaction]]** - Transformation with reactants, products, effectors, and rate functions.
- **[[ReactionGenerator]]** - Factory that produces synthetic reactions with configurable kinetics.

## BioChemistry
Container for molecules and reactions forming a chemical system.
- **[[BioChemistry]]** - Entity that groups molecules and reactions together. Provides validation, state management, and simulation support.

## BioPathways
Connected sequences of reactions (analytical abstraction).
- **[[BioPathway]]** - Connected subgraph forming a metabolic function: linear chains, branching paths, cycles, or signaling cascades. Used for understanding and generating coherent reaction networks, not directly in simulation.

## BioContainers (Rust)
Nestable biological structures from organelles to organisms. All are Entity subclasses.
- **[[BioContainer]]** - Nestable Entity for molecules, reactions, and child containers. Kind labels: organism, organ, cell, organelle.
- **[[ContainerGenerator]]** - Composable factory for BioContainers. Generators compose recursively: simple generators build complex ones.
