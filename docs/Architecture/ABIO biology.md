 [[ABIO Architecture Docs]] 

# ABIO biology
Molecules, reactions, chemistry, compartments and the simulators over them.

The generator and pathway pages this index used to carry were retired
2026-10-07 (T068): `MoleculeGenerator`, `ReactionGenerator`,
`ContainerGenerator`, the `Generator` protocol and `Pathway` are M1
design-era classes that no survivor of M47.7 / T056 implements. World
construction is the `suite` subsystem's skeletons and drafter heads now
(see [[ABIO Suite Runtime]]), and the reaction-network views that replaced
`Pathway`'s role live in `infra/graph_ops.py`. The "(Rust)" markers are
gone with them: `rust/` is a stub nothing in the package calls.

## Atoms and Molecules
Chemical elements and compounds in the alien biology.
- **[[ABIO Atom]]** - Chemical element with symbol, name, and atomic weight. Immutable value objects shared across molecules.
- **[[ABIO Molecule]]** - Chemical compound composed of atoms. Has biosynthetic depth, derived formula (symbol), and molecular weight.

## Reactions
Transformations between molecules.
- **[[ABIO Reaction]]** - Transformation with reactants, products, effectors, and rate functions.

## Chemistry
Container for molecules and reactions forming a chemical system.
- **[[ABIO Chemistry]]** - Entity that groups molecules and reactions together. Provides validation, state management, and simulation support.

## Compartments
Nestable biological structures from organelles to organisms. All are Entity subclasses.
- **[[ABIO Compartment]]** - Nestable Entity for molecules, reactions, and child containers. Kind labels: organism, organ, cell, organelle.

## Simulation
Multi-compartment simulation with reactions within compartments and flows across membranes.
- **[[ABIO WorldState]]** - Dense concentration storage: `[num_compartments × num_molecules]` array. GPU-friendly, O(1) access.
- **[[ABIO CompartmentTree]]** - Hierarchical topology of compartments. Stores parent-child relationships, separated from concentrations.
- **[[ABIO Flow]]** - Transport between compartments: `TransportFlux`, amount-conserving between any two compartment pools, applied in one rationed pass.
- **[[ABIO WorldSimulator]]** - Multi-compartment simulation engine. Applies reactions within compartments, flows across membranes.
