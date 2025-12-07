# Protocol Index

Alphabetical listing of all protocols in the Alien Biology system.

For hierarchical organization, see [[alienbio]] → [[infra]], [[biology]], [[execution]].

## A
- **[[Action]]** - Agent action to perturb system state

## B
- **[[BioMolecule]]** - Chemical compound with atoms, bonds, properties
- **[[BioOrganism]]** - Complete organism with compartmentalized physiology
- **[[BioReaction]]** - Transformation between molecules
- **[[BioSystem]]** - DAG of bioparts with molecule concentrations

## E
- **[[Entity]]** - Base class for all biology objects
- **[[Experiment]]** - Single world setup with task, agent, scoring

## G
- **[[Generator]]** - Base class for synthetic biology factories

## H
- **[[Harness]]** - Execution runner with logging and result aggregation

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
- **[[SystemGenerator]]** - Factory for complete bio-systems

## T
- **[[Task]]** - Goal specification with scoring criteria
- **[[Test]]** - Batch of experiments across variations
- **[[Timeline]]** - Sequence of states with intervention hooks

## W
- **[[World]]** - Complete runnable setup with system, generators, initial conditions
