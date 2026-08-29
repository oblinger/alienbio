[[Architecture Docs]] 

# Protocols

Alphabetical listing of all classes in the Alien Biology system, organized by subsystem.

## By Subsystem

| Subsystem | Classes |
|-----------|---------|
| **[[ABIO infra\|Infrastructure]]** | Bio, Entity, Expr, Interpreter, IO |
| **[[ABIO biology\|Biology]]** | Atom, Chemistry, Compartment, CompartmentTree, ContainerGenerator, Flow, Generator, Molecule, MoleculeGenerator, Pathway, Reaction, ReactionGenerator, WorldSimulator, WorldState |
| **[[ABIO execution\|Execution]]** | Action, Context, Experiment, Measurement, Simulator, State, Step, Task, Test, TestHarness, Timeline, World |
| **[[ABIO Suite Construction\|Suite construction (M26/M27)]]** | Motif, WorldEnvelope, CarveResult, Skeleton, SkeletonBlock, TaskArchetype, ObjectiveRecipe, TaskInstance, Question, Answer, AnswerObjective, OutcomeObjective, SuiteSpec, Suite, Dist, Seed, Vocabulary, Renderable, Op, LLMOp, Predicate, Directive |
| **[[ABIO Suite Runtime\|Suite runtime (Phase 2)]]** | Agent, SessionAgent, ScriptedAgent, LLMAgent, Measure, Intervene, Commit, Wait, ActionOutcome, ReasoningStep, TaskBrief, Affordances, Budget, SimConfig, TrialRecord, ActionRecord, DeliberationTrace, MassTrialRunner, ReliabilityMap, Provenance, ConditionSpec |

The biology and execution rows name the **protocols** in `alienbio.protocols` (`CompartmentTree`, `State`, `World`, …); their concrete classes in `alienbio.bio` carry an `Impl` suffix (`CompartmentTreeImpl`, `StateImpl`, `WorldImpl`). The suite rows name concrete dataclasses and Protocols in `alienbio.suite` — the M26 neutral shadow types (`StateVector`, `Topology`, a neutral `World`/`Compartment`) were retired in July 2026 (F007) and the suite now builds directly on the biology classes.

---

## A
- **[[action|Action]]** — Agent action to perturb the system state *(legacy execution protocol)*
- **[[ABIO Suite Runtime|Action (suite)]]** — The closed neutral verb set `Measure | Intervene | Commit | Wait`; scorers match on type, never on a world's names *(suite runtime)*
- **[[ABIO Suite Runtime|ActionOutcome]]** — What the runner tells a `SessionAgent` after each action: accepted or rejected, and why *(suite runtime; M46)*
- **[[ABIO Suite Runtime|ActionRecord]]** — One logged action on a `TrialRecord`: kind, destructive flag, accepted flag and rejection reason *(suite runtime)*
- **[[ABIO Suite Runtime|Affordances]]** — The probe ids a `Measure` may name and the lever ids an `Intervene` may name — the declared control surface a brief carries *(suite runtime; M46)*
- **[[ABIO Suite Runtime|Agent]]** — The structural Protocol every decision-maker implements: `act(observation) -> (Action, reasoning_steps)` *(suite runtime)*
- **[[Suite Construction Data Model|Answer]]** — An opaque JSON-ish value tagged by kind (`node_set`, `ordered_path`, `node_id`, `scalar`, `json`) *(suite; M26)*
- **[[Suite Construction Data Model|AnswerObjective]]** — Grade a committed `Answer` against a key with a grader; its sibling `OutcomeObjective` scores the world trajectory instead *(suite; M26)*
- **[[Atom]]** — Chemical element with symbol, name, and atomic weight

## B
- **[[Bio]]** — Loading, hydration, and persistence for biology objects in DAT folders
- **[[ABIO Suite Runtime|Budget]]** — The graded spend cap on the turn loop (unit `turns`; ladder `unlimited/20/12/8/4`) — the M32.1 time-pressure dial *(suite runtime)*

## C
- **[[Suite Construction Data Model|CarveResult]]** — A motif bound to concrete world nodes plus the extracted ground truth; the pre-F013 name for this was `Skeleton` *(suite; M26)*
- **[[Chemistry]]** — Container for molecules and reactions forming a chemical system
- **[[Compartment]]** — Nestable container for molecules, reactions, and child containers
- **[[CompartmentTree]]** — Hierarchical topology of compartments with parent-child relationships
- **[[ContainerGenerator]]** — Composable factory for Compartments
- **[[ABIO Suite Runtime|ConditionSpec]]** — A dial-vector sampler over orthogonal `DialAxis` entries with quantization — how a sweep's condition grid is declared *(suite runtime; M34.1)*
- **[[Context]]** — Runtime pegboard for all major subsystems

## D
- **[[ABIO Suite Runtime|DeliberationTrace]]** — The per-trial sequence of `DeliberationStep`s the runner threads an agent's `ReasoningStep`s into, read by the M33 trace scorers *(suite runtime)*
- **[[ABIO Suite Construction|Directive]]** — Opaque instruction text a suite Op harness carries; the engine never inspects it *(suite; M26)*
- **[[Suite Construction Data Model|Dist]]** — A seeded distribution (`Constant`, `Uniform`, `Normal`, `LogNormal`, `Choice`) — every generator parameter is one *(suite; M26)*

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

## L
- **[[ABIO Suite Runtime|LLMAgent]]** — A live-model `Agent` + `SessionAgent` over the `LLMOp` seam: briefed at trial start, keeps a turn-history window, opt-in and out of CI *(suite runtime; M44/M46)*
- **[[ABIO Suite Construction|LLMOp]]** — The one model-call seam: schema-validated reply, deterministic cache on (directive, context, seed), retry with a child seed *(suite; M26)*

## M
- **[[ABIO Suite Runtime|MassTrialRunner]]** — Condition grid × seeded trials → `ReliabilityMap`, each trial isolated so one failure is a record rather than the end of the sweep *(suite runtime; M34)*
- **[[measurement|Measurement]]** — Function to observe system state
- **[[Molecule]]** — Chemical compound composed of atoms with derived formula and weight
- **[[MoleculeGenerator]]** — Factory for synthetic molecules
- **[[Suite Construction Data Model|Motif]]** — An abstract reaction-network pattern with role slots; a `CarveResult` binds it to a concrete world *(suite; M26)*

## O
- **[[ABIO Suite Construction|ObjectiveRecipe]]** — Opaque protocol turning a carved Skeleton into a task's Question + graded Objective (build_question / build_key / build_distractors / grader_spec) *(suite; M27)*
- **[[ABIO Suite Construction|Op]]** — Opaque callable operation over a context (its scripted form is ScriptedOp) *(suite; M26)*

## P
- **[[Pathway]]** — Connected sequence of reactions
- **[[ABIO Suite Construction|Predicate]]** — Opaque callable over a node, only ever invoked, never inspected — a role constraint / world-validity test *(suite; M26)*
- **[[ABIO Suite Runtime|Provenance]]** — What produced a `ReliabilityMap`: swept axes, base seed, trials per condition, failed-trial count *(suite runtime; M34)*

## Q
- **[[Suite Construction Data Model|Question]]** — A structured, opaque JSON-ish question tagged by kind — the agent-facing half of a task, rendered to text by a `Renderable` *(suite; M26)*

## R
- **[[Reaction]]** — Transformation between molecules with reactants, products, effectors
- **[[ReactionGenerator]]** — Factory for synthetic reactions
- **[[ABIO Suite Runtime|ReasoningStep]]** — One opaque reasoning fragment an agent emits while choosing an action *(suite runtime)*
- **[[ABIO Suite Runtime|ReliabilityMap]]** — The frozen sweep aggregate: per-cell stats with CIs, 2×2 interactions, effect-size contrasts, every retained `TrialRecord`, and its `Provenance` *(suite runtime; M34)*
- **[[ABIO Suite Construction|Renderable]]** — Something that renders itself to text over a vocabulary — deterministic template, never an LLM *(suite; M26)*

## S
- **[[ABIO Scenario|Scenario]]** — Complete runnable unit (chemistry, containers, interface, briefing, constitution)
- **[[ABIO Suite Runtime|ScriptedAgent]]** — Deterministic, network-free, seeded step/policy agent — the instrument's zero and what keeps CI green *(suite runtime)*
- **[[Suite Construction Data Model|Seed]]** — A hierarchical deterministic seed; `seed.child(label)` derives every per-condition, per-trial, per-turn seed *(suite; M26)*
- **[[ABIO Suite Runtime|SessionAgent]]** — The optional Protocol an agent implements to be briefed (`begin(brief)`) and told each action's outcome (`notice(outcome)`) *(suite runtime; M46)*
- **[[ABIO Suite Runtime|SimConfig]]** — Steps and sampling cadence of one simulation burst — one per turn in the runner *(suite)*
- **[[simulator|Simulator]]** — Execution engine for biology dynamics
- **[[ABIO Suite Construction|Skeleton]]** — The F013 recursive `SkeletonBlock` tree a generator materializes into a world (materialize / validate / oracle); not the pre-F013 `Skeleton`, now `CarveResult` *(suite; M38)*
- **[[state|State]]** — Snapshot of molecule concentrations
- **[[step|Step]]** — Single time advancement applying reactions
- **[[Suite Construction Data Model|Suite]]** / **[[Suite Construction Data Model|SuiteSpec]]** — A materialized suite (worlds + `TaskInstance`s) and the generative spec (archetype mix + per-archetype schemas + seed) it came from *(suite; M26/M27)*

## T
- **[[task|Task]]** — Goal specification with scoring criteria
- **[[Suite Construction Data Model|TaskArchetype]]** / **[[Suite Construction Data Model|TaskInstance]]** — The family a task belongs to (with its `ObjectiveRecipe` and optional drafter), and one concrete task: archetype + world + `CarveResult` + objective + question *(suite; M26/M27)*
- **[[ABIO Suite Runtime|TaskBrief]]** — What the runner tells the agent at trial start: the question, expected answer kind, constitution, affordances, budget and costs, turn and step limits — never the key, target or hidden state *(suite runtime; M46)*
- **[[test|Test]]** — Batch of experiments across variations
- **[[TestHarness]]** — Execution runner with logging and result aggregation
- **[[timeline|Timeline]]** — Sequence of states with intervention hooks
- **[[ABIO Suite Runtime|TrialRecord]]** — The frozen unit of observation one agent-run emits: timeline, deliberation trace, action log, objective score, terminal reason, budget accounting, illegal-action count, brief *(suite runtime; M40)*

## V
- **[[Alien Vocabulary|Vocabulary]]** — Injective token↔surface-phrase bijection the NL renderer substitutes through (lossless round-trip) *(suite; M26/M27)*

## W
- **[[world|World]]** — Complete runnable setup with system, generators, initial conditions
- **[[Suite Construction Data Model|WorldEnvelope]]** — The constraint envelope a drafted base world must satisfy for a task family *(suite; M26)*
- **[[WorldSimulator]]** — Multi-compartment simulation engine with reactions and flows
- **[[WorldState]]** — Dense concentration storage for multi-compartment simulations
