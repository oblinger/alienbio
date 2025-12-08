# ABIO Protocols

Alphabetical listing of all protocols in the Alien Biology system.

For hierarchical organization, see [[alienbio]] → [[ABIO infra]], [[ABIO biology]], [[ABIO execution]].

## A
- **[[Action]]** - Agent action to perturb system state

## B
- **[[BioContainer]]** - Nestable container for molecules, reactions, and child containers
- **[[BioMolecule]]** - Chemical compound with atoms, bonds, properties
- **[[BioReaction]]** - Transformation between molecules

## C
- **[[ContainerGenerator]]** - Composable factory for BioContainers
- **[[Context]]** - Runtime pegboard for all major subsystems

## E
- **[[Entity]]** - Base class for all biology objects
- **[[Experiment]]** - Single world setup with task, agent, scoring
- **[[Expr]]** - Simple functional expressions for operations and declarations

## G
- **[[Generator]]** - Base class for synthetic biology factories

## M
- **[[Measurement]]** - Function to observe system state
- **[[MoleculeGenerator]]** - Factory for synthetic molecules

## P
- **[[Pathway]]** - Connected sequence of reactions
- **[[PersistentEntity]]** - Entity saved to data/, loadable by name

## R
- **[[ReactionGenerator]]** - Factory for synthetic reactions

## S
- **[[ScopedEntity]]** - Entity named relative to containing World
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
