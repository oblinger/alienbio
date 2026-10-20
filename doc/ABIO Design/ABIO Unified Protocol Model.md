---
description: "The proposed unified biological protocol model for ABIO (F007-A): two kinds of thing — typed objects that have behavior, and generative spec-expressions (spec DSL / Expr) that evaluate into them. A class only where there's real behavior; everything generative is a declarative expression. Biology-named, with documented factory + id conventions."
---
:>> [[ABIO]] → [[ABIO Design]] → [ABIO Unified Protocol Model](ha://p/ABIO%20Unified%20Protocol%20Model) 
# [[ABIO]] · Unified Protocol Model (proposed)
The proposed target-state model for the framework ([[ABIO PRD]] § Design principle, F007-A): a small, cohesive, biology-named protocol set understood entirely at the protocol level, drawn as one architecture to discuss.

## The shape — two kinds of thing

The whole system reduces to **two kinds of thing**, plus algorithms over them:

1. **Typed objects** — a real class/protocol **only where there is genuine behavior or a specialized meaning**. Two flavors: *behavioral protocols* (they *do* something — `Chemistry` queries its graph, `Simulator` advances state, `Objective` grades, `Dist` samples) and *specialized value types* (typed data with meaning but no real methods — `Question`, `Answer`, `GraderSpec`).
2. **Generative spec-expressions** — everything that *describes how to build* a typed object is **not a bespoke class**; it is a declarative expression in the **existing spec DSL / `Expr`**, which the **`Interpreter` evaluates into its concrete counterpart (or errors).** `Motif`, `WorldEnvelope`, `ObjectiveRecipe`, `TaskArchetype`, `SuiteSpec` all collapse to this — no per-template subclasses, no template "methods."

This is the core simplification: the template→instance pairs (`Motif`→`Skeleton`, `TaskArchetype`→`TaskInstance`, `SuiteSpec`→`Suite`, `ObjectiveRecipe`→`Objective`, `WorldEnvelope`→`World`) stop being **two classes each**. The template side becomes a spec-expression; only the instantiated side is (sometimes) a typed object.

## Two documented conventions (not type-enforced)

- **Readable ids by convention — three naming layers.** Every thing in a world is addressable by three overlapping naming layers (all three already carried by the shared `Entity` base — this is convention over that base, not new machinery):
  1. **Generated full name** — a symbol built from a **prefix + a number** for generated things (`M…` molecules, `R…` reactions, `C…` compartments, …). Unique within its parent; must be a valid identifier (no spaces). *(Entity `local_name`.)*
  2. **Instance path** — an instance living inside a compartment is uniquely addressed by the **dotted path** from the world root down through its containing compartments to its full name (e.g. `organism1.heart.M07`). This is what disambiguates "the same molecule in two compartments." *(Entity `parent`/`children` hierarchy → dotted path from `root()`.)*
  3. **Skin name (optional)** — an alternative human/biology-facing alias that **may or may not exist**: a specific compartment within a specific organism ("its heart"), or the common name of a molecule or reaction. Defaults to the full name when absent, and may differ when present. *(Entity `name`, which defaults to `local_name` and may diverge.)*

  The docs state the schema; each factory follows it; the system does **not** enforce it.
- **Flavored factories by convention.** A small general protocol; factories mint **kind-labeled instances** of it. The convention (which factory tags which `kind`) is documented in the world-generator guide; the code does **not** crash if you don't follow it. Recurs across the model:

| One general protocol | Flavored instances (factory-minted, `kind`-tagged) |
|---|---|
| **Flow** | membrane · general |
| **Compartment** | organism · organ · cell · organelle |
| **Dist** | constant · uniform · normal · lognormal · choice |
| **Op** | scripted · LLM |
| **Objective** | answer · outcome |

## Group 1 — Biological substrate (behavioral protocols)

Biology-named; the model you read to understand the system. Each absorbs its retired M26 neutral shadow.

| Protocol | Role | Absorbs |
|---|---|---|
| **Chemistry** | the container — **holds atoms + molecules + reactions** — and the reaction network **+ graph queries** (`neighbors`/`paths`/`subgraph`/`match`) | neutral `ReactionNetwork` |
| **Atom** | element — symbol, name, atomic_weight; **part of `Chemistry`** (typically a fixed/constant set, swappable) | — |
| **Molecule** | species/node — atoms, bdepth, name, symbol, molecular_weight; part of `Chemistry` | neutral `Species` |
| **Reaction** | transformation — reactants, products, modifiers, rate; part of `Chemistry` | neutral `Reaction` |
| **Compartment** | container node — id, `parent`, `kind`, volume; **the `parent` links _are_ the tree** (flavors: organism/organ/cell/organelle) | neutral `Compartment` **+ `CompartmentTree`/`Topology`** (folded — no separate tree type; `World` owns the set, navigation is free helpers) |
| **Flow** | transport/edit over state (flavors: membrane/general) | consolidates `Flow`/`MembraneFlow`/`GeneralFlow` → one |
| **WorldState** | concentrations [compartments × molecules] + multiplicity; axis = ordered compartment ids | neutral `StateVector` (+ single-compartment `State` → 1-compartment `WorldState`) |
| **Timeline** | time-ordered sequence of states | neutral `Trace` |
| **World** | runnable setup — `Chemistry` + compartments + initial `WorldState` (owns the compartment set/ordering) | neutral `World` |
| **Simulator** | advances a `World` → a `Timeline`; **pluggable** (reference / JAX) | — |

**10 biological protocols** (from ~15: Flow-trio→1, `CompartmentTree` folded, `State`→`WorldState`, the 8 neutral shadows absorbed).

## Group 2 — Evaluation / runtime behavioral protocols

Neutral (no biological parallel), but they *do* things, so they're typed protocols.

| Protocol | Behavior |
|---|---|
| **Dist** | samples a value (flavors: constant/uniform/normal/lognormal/choice) |
| **Op** | runs an operation over a context (flavors: scripted/LLM) |
| **Vocabulary** | token↔phrase bijection — renders / parses |
| **Renderable** | renders itself given a `Vocabulary` |
| **Objective** | grades an answer / scores an outcome (flavors: answer/outcome) |

## Group 3 — Specialized value types

Typed data with specialized meaning, no real methods.

| Value type | What it is |
|---|---|
| **Question** / **Answer** | opaque payloads tagged by `kind` |
| **GraderSpec** | grader config (tolerance / partial-credit) |
| **FeatureSet** | a bundle of named predicates a world must satisfy |
| **Skeleton** | a `Motif` bound to concrete nodes (the instantiated pattern) |
| **TaskInstance** | a materialized task (world + skeleton + objective + question) |
| **Suite** | materialized worlds + task instances |

## Group 4 — Generative spec-expressions (spec DSL / `Expr`)

**Not classes.** Declarative expressions the `Interpreter` evaluates into a concrete counterpart (or errors). This is where the biggest reduction lives.

| Spec-expression | Evaluates into | (concrete counterpart) |
|---|---|---|
| **Motif** | → `Skeleton` | bound pattern |
| **WorldEnvelope** | → `World` | (samples via `Dist`, checks its `FeatureSet`) |
| **ObjectiveRecipe** | → `Objective` (+ `Question`) | the "how it's graded" |
| **TaskArchetype** | → `TaskInstance` | a concrete task |
| **SuiteSpec** | → `Suite` | a materialized suite |

Five bespoke template classes → five expression forms in one existing DSL. No per-archetype subclasses; the "methods" (build the question, build the key) *are* the interpreter evaluating the expression.

## Suite-construction engines

The operations that construct and evaluate suites over the concrete model — **cover** · **carve/splice** · **augment** · **verify/simulate** · **grade** · **render**. Biology-free. (Whether any of these should surface as a formal *suite-construction protocol* — e.g. to make an engine pluggable — is left open; today they are functions.)

## The figure

![[ABIO Unified Protocol Model.svg|3000]] 

## What this simplifies

- **8 neutral shadow types → 0** (absorbed into biology names).
- **`Flow`/`MembraneFlow`/`GeneralFlow` → 1**; **`CompartmentTree` folded**; **`State`→`WorldState`**.
- **5 template classes (`Motif`/`TaskArchetype`/`SuiteSpec`/`ObjectiveRecipe`/`WorldEnvelope`) → spec-expressions** (0 new classes).
- Net typed surface: **10 biological + 5 eval-behavioral + 7 value types + 6 engines**, plus a handful of spec-expression forms — down from the ~33 M26 neutral types + ~15 bio protocols.

## Resolved decisions

- **Atom** — kept (a real, named primitive).
- **Simulator** — its own protocol; pluggable implementations.
- **CompartmentTree** — folded into `Compartment.parent`; no separate tree type.
- **Id scheme** — three naming layers by documented convention (generated full name `local_name` + dotted instance path + optional skin-name alias); not enforced. See § Two documented conventions.
- **Time** — simulation time is a **floating-point number of seconds** into the run; there is **no fixed tick grain**. A `Timeline` stamps each recorded state with a real float-seconds timestamp (`times` array parallel to `states`); spacing may be uneven. Biology is expressed as differential/delta dynamics, so integrators emit timestamps rather than assuming a tick index.
- **Factory pattern** — documented convention in the world-generator guide; not enforced by classes.
- **Spec-as-expression** — the load-bearing decision; adopted (F007-A, this design).
