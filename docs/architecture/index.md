# Protocol Index

Alphabetical listing of all protocols in the Alien Biology system.

For hierarchical organization, see [[alienbio|ALIEN BIO]] → [[infra|Infra]], [[biology|Biology]], [[execution|Execution]].

## A

- [[action|Action]] - Agent action to perturb system state

## B

- [[bio_molecule|BioMolecule]] - Chemical compound with atoms, bonds, properties
- [[bio_organism|BioOrganism]] - Complete organism with compartmentalized physiology
- [[bio_reaction|BioReaction]] - Transformation between molecules
- [[bio_system|BioSystem]] - DAG of bioparts with molecule concentrations

## E

- [[entity|Entity]] - Base class for all biology objects
- [[experiment|Experiment]] - Single world setup with task, agent, scoring

## G

- [[generator|Generator]] - Base class for synthetic biology factories

## H

- [[harness|Harness]] - Execution runner with logging and result aggregation

## M

- [[measurement|Measurement]] - Function to observe system state
- [[molecule_generator|MoleculeGenerator]] - Factory for synthetic molecules

## P

- [[pathway|Pathway]] - Connected sequence of reactions
- [[persistent_entity|PersistentEntity]] - Entity saved to data/, loadable by name

## R

- [[reaction_generator|ReactionGenerator]] - Factory for synthetic reactions

## S

- [[scoped_entity|ScopedEntity]] - Entity named relative to containing World
- [[simulator|Simulator]] - Execution engine for biology dynamics
- [[state|State]] - Snapshot of molecule concentrations
- [[step|Step]] - Single time advancement applying reactions
- [[system_generator|SystemGenerator]] - Factory for complete bio-systems

## T

- [[task|Task]] - Goal specification with scoring criteria
- [[test|Test]] - Batch of experiments across variations
- [[timeline|Timeline]] - Sequence of states with intervention hooks

## W

- [[world|World]] - Complete runnable setup with system, generators, initial conditions
