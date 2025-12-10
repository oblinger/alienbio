# ABIO Protocols
**Parent**: [[ABIO Sys]]
Alphabetical listing of all protocols in the Alien Biology system.

## A
- **[[Action]]** - Agent action to perturb system state
- **[[Atom]]** - Chemical element with symbol, name, and atomic weight

## C
- **[[Chemistry]]** - Container for molecules and reactions forming a chemical system
- **[[Compartment]]** - Nestable container for molecules, reactions, and child containers
- **[[CompartmentTree]]** - Hierarchical topology of compartments with parent-child relationships
- **[[ContainerGenerator]]** - Composable factory for Compartments
- **[[Context]]** - Runtime pegboard for all major subsystems

## E
- **[[Entity]]** - Base class for all biology objects
- **[[Experiment]]** - Single world setup with task, agent, scoring
- **[[Expr]]** - Simple functional expressions for operations and declarations

## F
- **[[Flow]]** - Membrane transport between parent-child compartments

## G
- **[[Generator]]** - Base class for synthetic biology factories

## I
- **[[IO]]** - Entity I/O: prefix bindings, formatting, parsing, persistence

## M
- **[[Measurement]]** - Function to observe system state
- **[[Molecule]]** - Chemical compound composed of atoms with derived formula and weight
- **[[MoleculeGenerator]]** - Factory for synthetic molecules

## P
- **[[Pathway]]** - Connected sequence of reactions

## R
- **[[Reaction]]** - Transformation between molecules with reactants, products, effectors
- **[[ReactionGenerator]]** - Factory for synthetic reactions

## S
- **[[Simulator]]** - Execution engine for biology dynamics
- **[[State]]** - Snapshot of molecule concentrations
- **[[Step]]** - Single time advancement applying reactions

## T
- **[[Task]]** - Goal specification with scoring criteria
- **[[Test]]** - Batch of experiments across variations
- **[[TestHarness]]** - Execution runner with logging and result aggregation
- **[[Timeline]]** - Sequence of states with intervention hooks

## W
- **[[World]]** - Complete runnable setup with system, generators, initial conditions
- **[[WorldSimulator]]** - Multi-compartment simulation engine with reactions and flows
- **[[WorldState]]** - Dense concentration storage for multi-compartment simulations
