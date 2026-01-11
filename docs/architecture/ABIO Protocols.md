 [[Architecture Docs]]

# Protocols

Alphabetical listing of all classes in the Alien Biology system, organized by subsystem.

## By Subsystem

| Subsystem | Classes |
|-----------|---------|
| **[[ABIO infra\|Infrastructure]]** | Bio, Entity, Expr, Interpreter, IO |
| **[[ABIO biology\|Biology]]** | Atom, Chemistry, Compartment, CompartmentTree, ContainerGenerator, Flow, Generator, Molecule, MoleculeGenerator, Pathway, Reaction, ReactionGenerator, WorldSimulator, WorldState |
| **[[ABIO execution\|Execution]]** | Action, Context, Experiment, Measurement, Simulator, State, Step, Task, Test, TestHarness, Timeline, World |

---

## A
- **[[classes/execution/action|Action]]** — Agent action to perturb the system state
- **[[classes/biology/Atom|Atom]]** — Chemical element with symbol, name, and atomic weight

## B
- **[[classes/infra/Bio|Bio]]** — Loading, hydration, and persistence for biology objects in DAT folders

## C
- **[[classes/biology/Chemistry|Chemistry]]** — Container for molecules and reactions forming a chemical system
- **[[classes/biology/Compartment|Compartment]]** — Nestable container for molecules, reactions, and child containers
- **[[classes/biology/CompartmentTree|CompartmentTree]]** — Hierarchical topology of compartments with parent-child relationships
- **[[classes/biology/ContainerGenerator|ContainerGenerator]]** — Composable factory for Compartments
- **[[classes/execution/Context|Context]]** — Runtime pegboard for all major subsystems

## E
- **[[classes/infra/entity|Entity]]** — Base class for all biology objects
- **[[classes/execution/experiment|Experiment]]** — Single world setup with task, agent, scoring
- **[[classes/infra/Expr|Expr]]** — Simple functional expressions for operations and declarations

## F
- **[[classes/biology/Flow|Flow]]** — Membrane transport between parent-child compartments

## G
- **[[classes/biology/generator|Generator]]** — Base class for synthetic biology factories

## I
- **[[classes/infra/Interpreter|Interpreter]]** — Evaluates Expr trees and handles language dispatch
- **[[classes/infra/IO|IO]]** — Entity I/O: prefix bindings, formatting, parsing, persistence

## M
- **[[classes/execution/measurement|Measurement]]** — Function to observe system state
- **[[classes/biology/Molecule|Molecule]]** — Chemical compound composed of atoms with derived formula and weight
- **[[classes/biology/MoleculeGenerator|MoleculeGenerator]]** — Factory for synthetic molecules

## P
- **[[classes/biology/Pathway|Pathway]]** — Connected sequence of reactions

## R
- **[[classes/biology/Reaction|Reaction]]** — Transformation between molecules with reactants, products, effectors
- **[[classes/biology/ReactionGenerator|ReactionGenerator]]** — Factory for synthetic reactions

## S
- **[[commands/ABIO Scenario|Scenario]]** — Complete runnable unit (chemistry, containers, interface, briefing, constitution)
- **[[classes/execution/simulator|Simulator]]** — Execution engine for biology dynamics
- **[[classes/execution/state|State]]** — Snapshot of molecule concentrations
- **[[classes/execution/step|Step]]** — Single time advancement applying reactions

## T
- **[[classes/execution/task|Task]]** — Goal specification with scoring criteria
- **[[classes/execution/test|Test]]** — Batch of experiments across variations
- **[[classes/execution/TestHarness|TestHarness]]** — Execution runner with logging and result aggregation
- **[[classes/execution/timeline|Timeline]]** — Sequence of states with intervention hooks

## W
- **[[classes/execution/world|World]]** — Complete runnable setup with system, generators, initial conditions
- **[[classes/biology/WorldSimulator|WorldSimulator]]** — Multi-compartment simulation engine with reactions and flows
- **[[classes/biology/WorldState|WorldState]]** — Dense concentration storage for multi-compartment simulations
