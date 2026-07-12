[[Architecture Docs]]

# Protocols

Alphabetical listing of all classes in the Alien Biology system, organized by subsystem.

## By Subsystem

| Subsystem | Classes |
|-----------|---------|
| **[[ABIO infra|Infrastructure]]** | Bio, Entity, Expr, Interpreter, IO |
| **[[ABIO biology|Biology]]** | Atom, Chemistry, Compartment, CompartmentTree, ContainerGenerator, Flow, Generator, Molecule, MoleculeGenerator, Pathway, Reaction, ReactionGenerator, WorldSimulator, WorldState |
| **[[ABIO execution|Execution]]** | Action, Context, Experiment, Measurement, Simulator, State, Step, Task, Test, TestHarness, Timeline, World |

---

## A
- **[[action|Action]]** — Agent action to perturb the system state
- **[[Atom]]** — Chemical element with symbol, name, and atomic weight

## B
- **[[Bio]]** — Loading, hydration, and persistence for biology objects in DAT folders

## C
- **[[Chemistry]]** — Container for molecules and reactions forming a chemical system
- **[[Compartment]]** — Nestable container for molecules, reactions, and child containers
- **[[CompartmentTree]]** — Hierarchical topology of compartments with parent-child relationships
- **[[ContainerGenerator]]** — Composable factory for Compartments
- **[[Context]]** — Runtime pegboard for all major subsystems

## E
- **[[entity|Entity]]** — Base class for all biology objects
- **[[experiment|Experiment]]** — Single world setup with task, agent, scoring
- **[[Expr]]** — Simple functional expressions for operations and declarations

## F
- **[[Flow]]** — Membrane transport between parent-child compartments

## G
- **[[generator|Generator]]** — Base class for synthetic biology factories

## I
- **[[Interpreter]]** — Evaluates Expr trees and handles language dispatch
- **[[IO]]** — Entity I/O: prefix bindings, formatting, parsing, persistence

## M
- **[[measurement|Measurement]]** — Function to observe system state
- **[[Molecule]]** — Chemical compound composed of atoms with derived formula and weight
- **[[MoleculeGenerator]]** — Factory for synthetic molecules

## P
- **[[Pathway]]** — Connected sequence of reactions

## R
- **[[Reaction]]** — Transformation between molecules with reactants, products, effectors
- **[[ReactionGenerator]]** — Factory for synthetic reactions

## S
- **[[ABIO Scenario|Scenario]]** — Complete runnable unit (chemistry, containers, interface, briefing, constitution)
- **[[simulator|Simulator]]** — Execution engine for biology dynamics
- **[[state|State]]** — Snapshot of molecule concentrations
- **[[step|Step]]** — Single time advancement applying reactions

## T
- **[[task|Task]]** — Goal specification with scoring criteria
- **[[test|Test]]** — Batch of experiments across variations
- **[[TestHarness]]** — Execution runner with logging and result aggregation
- **[[timeline|Timeline]]** — Sequence of states with intervention hooks

## W
- **[[world|World]]** — Complete runnable setup with system, generators, initial conditions
- **[[WorldSimulator]]** — Multi-compartment simulation engine with reactions and flows
- **[[WorldState]]** — Dense concentration storage for multi-compartment simulations
