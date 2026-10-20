---
description: "ABIO PRD — the product-level statement of what the Alien Biology Framework is: a taint-free generative testing framework for reasoning under partial observability, the Expr language it is written in, the suite runtime, the example corpus, and the safety-adjacency rule."
---
:>> [[ABIO]] → [[ABIO Design]] → [ABIO PRD](ha://p/ABIO%20PRD) 
# ABIO PRD
*Rewritten 2026-08-30 (T018) as the product statement of the framework as built; the earlier hub pointed at sub-documents that no longer exist. Detailed architecture lives in the published corpus under [[ABIO Docs]]; this page says what the product is and what it must do, not how each part works.*

## Overview

The Alien Biology Framework generates **alien biochemical worlds** — networks of molecules, reactions, compartments and populations that obey conservation and kinetics but match nothing in any textbook — and turns them into **auto-graded tasks** for an agent that must reason about a world it has never seen: identify a hidden pathway, diagnose a perturbation, predict a response, intervene toward a target, discover a catalyst. The generator holds the ground truth, so every answer is **checked against physics, never judged by a grader in the loop**, and every world is fresh, so nothing the agent was trained on applies.

One sentence for a visitor: *a taint-free, generative, parameterized testing framework for long reasoning chains and multi-turn tasks under partial observability and partial understanding, general enough to run alignment-under-pressure experiments without having to hand-author a single world.*

## Goals

Each goal below is stated as a property the product must have, followed by where it is met today. Status words are the roadmap's: **built**, *partial*, planned.

1. **Generative, parameterized worlds** — a world is drawn from a template under a seed and a set of independently-varied structural dials (network size, route length, observability, noise, transport, hidden interdependency, environmental pressure, budget), never hand-authored. **Built**: the Skeleton subsystem (typed, stackable blocks — reactions, sources, sinks, cruxes, modulation, transport, lattices, populations — that materialize into one runnable world), the drafters that assemble them, and the dial set in [[ABIO Capability Dimensions]] § B.
2. **Ground truth held by the generator** — every task carries a key or an oracle computed from the world the agent cannot see; grading is mechanical (`grade`, outcome scorers, oracles), with partial credit where an ordered answer admits it. **Built**: the objective recipes and graders of the suite-construction pipeline, the oracle side of `TrialRecord`.
3. **Taint-free by construction** — the agent sees observations and a brief, never the hidden set, the key, or the drafter's internals; a taint audit runs over real prompts. **Built**: the observability model, the taint audit (M46.10), and the **no-peeking rule** (§ below).
4. **Multi-turn, partially observed episodes** — an agent measures, waits, intervenes and commits across turns under a budget, with turn memory it controls, illegal actions recorded as data rather than crashes, and irreversible levers declared. **Built**: the suite runtime ([[ABIO Suite Runtime]]): the turn loop, `TaskBrief`, session memory, rejection-as-data, stakes and reversibility.
5. **Physics that can be trusted** — mass conservation, order-independent simultaneous reactions, bounded rates, optional energy accounting and a boundedness gate; one reference simulator and one vectorized JAX core that agree on every admitted rate law. **Built**: the execution subsystem, the rate grammar (constant, product-form modulations, Michaelis–Menten, Hill, activation, inhibition, and algebra over them), conformance tests between the two simulators. *Partial*: JAX is not yet the suite's default backend.
6. **Experiments as declarative, reproducible artifacts** — an experiment is one file: the task as a call, the agent, the swept axes, the trials, the seed; a run writes a manifest (spec hash, git commit, versions, model and its generation, cost estimate and actual spend), a record store, a reliability map and a report; runs resume after interruption and aggregate from the store alone. **Built**: `bio suite run | resume | aggregate | report | models`, with power design, matched world seeds across arms, an automatic idle baseline, bounded concurrency, usage accounting, a cost ceiling and the dry-run estimate.
7. **Agents as pluggable arms** — scripted controls (idle, measure, survey, heuristic, knockout, act, assay, and any an example registers) and a live-model agent over one provider seam, swept as an axis against the same worlds. **Built**: the agent registry and `LLMAgent`; live-model runs pin a model generation (`bio suite models`) and meter every call.
8. **One language for all of it** — worlds, tasks, briefs, episodes, agents and experiments are written in **Expr** ([[ABIO Expr]], [[ABIO Expr Spec]]): a language of calls over YAML data, where logic is Python (registered heads), structure is template structure, and simple formulas may be written either way. Untrusted files are sandboxed at the boundary; trusted catalog files may execute Python. **Built** (M47): the interpreter, the registry, includes, guards, constructors for every entity, the drafters and the experiment head; the M1 scenario runtime was retired, not kept beside it.
9. **Standing on its own** — the framework is explained by executed documentation (every fence in the spec and API guide runs in CI), a capability test matrix generated from tests, and an example corpus that exercises every part of the system without touching the safety work. **Built**: `bio test-matrix`, the executed docs, and six examples under `catalog/examples/` (ecosystem, organism, microcosm, kinetics kit, pathway puzzles, grid); three more (cascade, agent loop, stochastic environment) wait on [[AUP]]'s pre-registration check.
10. **General enough for the safety experiments** — the ten experiment types in [[ABIO Experiment Catalog]] (EXP-1 … EXP-10) run end to end with scripted agents as golden regressions; the framework claims *we can build the instrument*, and [[AUP]] claims *here is what it measured*.

## The design principle — the unified biological protocol model

The framework's data model **is** its set of protocols. One cohesive, minimal, comprehensible protocol set from which a reader can understand the whole system; this is normative for all ABIO framework work.

1. **The protocols are the model.** The important structure and logic lives at the protocol level; implementations (`*Impl` classes, generators, drafters) sit underneath and stay thin.
2. **Biological naming wins where a natural parallel exists.** `Chemistry`, `Molecule`, `Reaction`, `Compartment`, `WorldState`, `Timeline`, `World` — even when an algorithmic name would also fit. The biological name tells a reader what the thing **is**.
3. **Neutral naming only where it is genuinely the most natural framing** and has no biological parallel — the suite-construction abstractions (`Motif`, `Skeleton`, `RoleSlot`, `FeatureSet`, `Vocabulary`, `Dist`, `Question`, `Answer`, `Objective`, `GraderSpec`). Neutral is allowed, not preferred.
4. **One model, not two.** No parallel "shadow" data types duplicating a biological concept under a neutral name (F007, done). Engines operate against the protocols.

## The safety-adjacency rule

ABIO is the instrument; [[AUP]] (Alignment Under Pressure) is the study that uses it, with pre-registered experiments. Two rules keep both credible:

- **No peeking.** No language model runs on an AUP-registered substrate (the conflict, pressure and delta drafters and the controls drafted on them) or under a safety dial (hazard, perturbation, symbiosis, target margin, constitution, monitoring, framing, stakes, reversibility, assays). This is a guard the runtime enforces from the metadata on the heads a file calls, and a CI lint, not a convention.
- **Examples stay clear.** Nothing in the example corpus uses a safety dial or comes close enough to a pre-registered experiment that running it would inform the paper; every proposed example passes AUP's inbox before it is built, and silence is not consent.

ABIO shows its safety relevance through the capability — continuous, independently-varied structural dials over worlds whose ground truth the generator holds — not through safety results, which belong to AUP.

## Non-Goals

- **Designing the safety experiments' conclusions.** ABIO fleshes sample experiments only as a coverage driver for capabilities; the findings are AUP's.
- **A hand-authored world catalog.** Every world is drawn; the catalog holds templates, examples and experiment specs, never bespoke worlds.
- **A second data model for domain-blind workers.** Neutral suite protocols plus opaque tags serve that need; the biological model is not duplicated.
- **Realism as biology.** Worlds are alien on purpose; the constraints are conservation and kinetics, not resemblance to any organism.

## User Stories

- **A researcher** writes one YAML file — a world template with parameter holes, a task as a call, the axes to sweep — runs `bio suite run`, and gets a manifest, a record store, a reliability map and a report; interrupts it, resumes it, and can hand the file to someone else who reproduces the run from the pinned seeds and model generation.
- **An agent under test** receives a brief and observations, spends a budget measuring, waiting and intervening, and commits an answer that is scored against ground truth it was never shown; its illegal actions are recorded, not fatal.
- **A framework developer** adds a block, a rate law, an objective or a scripted agent by registering a Python function, and the language reaches it by name — no new syntax, no second loader.
- **An alignment study ([[AUP]])** takes the instrument as it stands — continuous structural dials over generated worlds, scripted controls, an idle baseline, matched seeds, power design — and runs its pre-registered experiments on it without ABIO having run a live model on those substrates first.
- **A visitor** reads the executed docs and the example corpus, runs an example end to end in one command, and sees from the capability matrix which of the 35 dimensions are built — without any safety result being claimed.

## Where things are

| | |
|---|---|
| The language | [[ABIO Expr]] (design note), [[ABIO Expr Spec]] and [[ABIO Expr Python API]] (user guides, executed in CI) |
| The runtime | [[ABIO Suite Runtime]], [[ABIO Suite Construction]], [[ABIO Commands]] |
| The substrate | [[ABIO biology]], [[ABIO Skeleton Arch]], [[ABIO Protocols]] |
| Coverage | [[ABIO Capability Dimensions]] (35 dimensions, matrix generated from tests), [[ABIO Experiment Catalog]] (EXP-1 … EXP-10) |
| Examples | `catalog/examples/` in the repo — one folder each, spec + helpers + README + test |
| Tracking | [[ABIO Roadmap]] · [[ABIO Backlog]] |
| The benchmark idea this realizes | [[ABIO Inference Bench]] |
