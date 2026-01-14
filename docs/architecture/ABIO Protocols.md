[[Architecture Docs]]

# Protocols

Alphabetical listing of all classes in the Alien Biology system, organized by subsystem.

## By Subsystem

| Subsystem | Classes |
|-----------|---------|
| **[Infrastructure](ABIO infra.md)** | Bio, Entity, Expr, Interpreter, IO |
| **[Biology](ABIO biology.md)** | Atom, Chemistry, Compartment, CompartmentTree, ContainerGenerator, Flow, Generator, Molecule, MoleculeGenerator, Pathway, Reaction, ReactionGenerator, WorldSimulator, WorldState |
| **[Execution](ABIO execution.md)** | Action, Context, Experiment, Measurement, Simulator, State, Step, Task, Test, TestHarness, Timeline, World |

---

## A
- **[Action](classes/execution/action.md)** — Agent action to perturb the system state
- **[Atom](classes/biology/Atom.md)** — Chemical element with symbol, name, and atomic weight

## B
- **[Bio](classes/infra/Bio.md)** — Loading, hydration, and persistence for biology objects in DAT folders

## C
- **[Chemistry](classes/biology/Chemistry.md)** — Container for molecules and reactions forming a chemical system
- **[Compartment](classes/biology/Compartment.md)** — Nestable container for molecules, reactions, and child containers
- **[CompartmentTree](classes/biology/CompartmentTree.md)** — Hierarchical topology of compartments with parent-child relationships
- **[ContainerGenerator](classes/biology/ContainerGenerator.md)** — Composable factory for Compartments
- **[Context](classes/execution/Context.md)** — Runtime pegboard for all major subsystems

## E
- **[Entity](classes/infra/entity.md)** — Base class for all biology objects
- **[Experiment](classes/execution/experiment.md)** — Single world setup with task, agent, scoring
- **[Expr](classes/infra/Expr.md)** — Simple functional expressions for operations and declarations

## F
- **[Flow](classes/biology/Flow.md)** — Membrane transport between parent-child compartments

## G
- **[Generator](classes/biology/generator.md)** — Base class for synthetic biology factories

## I
- **[Interpreter](classes/infra/Interpreter.md)** — Evaluates Expr trees and handles language dispatch
- **[IO](classes/infra/IO.md)** — Entity I/O: prefix bindings, formatting, parsing, persistence

## M
- **[Measurement](classes/execution/measurement.md)** — Function to observe system state
- **[Molecule](classes/biology/Molecule.md)** — Chemical compound composed of atoms with derived formula and weight
- **[MoleculeGenerator](classes/biology/MoleculeGenerator.md)** — Factory for synthetic molecules

## P
- **[Pathway](classes/biology/Pathway.md)** — Connected sequence of reactions

## R
- **[Reaction](classes/biology/Reaction.md)** — Transformation between molecules with reactants, products, effectors
- **[ReactionGenerator](classes/biology/ReactionGenerator.md)** — Factory for synthetic reactions

## S
- **[Scenario](commands/ABIO Scenario.md)** — Complete runnable unit (chemistry, containers, interface, briefing, constitution)
- **[Simulator](classes/execution/simulator.md)** — Execution engine for biology dynamics
- **[State](classes/execution/state.md)** — Snapshot of molecule concentrations
- **[Step](classes/execution/step.md)** — Single time advancement applying reactions

## T
- **[Task](classes/execution/task.md)** — Goal specification with scoring criteria
- **[Test](classes/execution/test.md)** — Batch of experiments across variations
- **[TestHarness](classes/execution/TestHarness.md)** — Execution runner with logging and result aggregation
- **[Timeline](classes/execution/timeline.md)** — Sequence of states with intervention hooks

## W
- **[World](classes/execution/world.md)** — Complete runnable setup with system, generators, initial conditions
- **[WorldSimulator](classes/biology/WorldSimulator.md)** — Multi-compartment simulation engine with reactions and flows
- **[WorldState](classes/biology/WorldState.md)** — Dense concentration storage for multi-compartment simulations
