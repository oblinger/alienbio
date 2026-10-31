 [[ABIO]] 
# Architecture Docs

Comprehensive specification of the Alien Biology system's design and operation.
(See [[ABIO Alienbio User Guide]] for usage tutorials and [API Docs](../ABIO%20Ref/ABIO%20API/ABIO%20API.md) for class and module signatures.)


## Alienbio Specification Languages

- **[[ABIO Expr Spec]]** — Core language: YAML foundation with tags, scopes, hydration, and evaluation
- **M1 Scenario (deleted in M47.7)** — Runnable world (molecules, reactions, interface, scoring)
- **[[ABIO Suite Runtime|Experiment]]** — Multi-run experiment over axes

## Indexes

- **[[ABIO Protocols]]** — Alphabetical index of classes
- **[[ABIO Modules]]** — Alphabetical index of modules
- **[[ABIO Commands]]** — Command reference (CLI and Python)

## Subsystems

- **[[ABIO infra]]** — Infrastructure: entity base classes, serialization, data management, configuration.
- **[[ABIO biology]]** — Biology: molecules, reactions, pathways, containers, and generators.
- **[[ABIO Suite Runtime]]** — Execution: simulation engine, agent interface, experimentation framework.

## Benchmark generation

- **[[ABIO Suite Construction]]** — How a suite spec becomes a battery of auto-graded tasks over a small set of verified worlds (realizes the [ABIO Inference Bench](https://github.com/oblinger/alienbio/blob/main/doc/ABIO%20Idea/ABIO%20Inference%20Bench.md), sits atop the [[ABIO PRD Docs|Scenario Generator PRD]]).
- **[[ABIO Suite Runtime]]** — The Phase-2 layer that runs an agent against those tasks: the turn loop, the agent Protocols (scripted and live-model), the per-trial record, and the mass-trial sweep.

## Project Tracking

- **[ABIO Roadmap](https://github.com/oblinger/alienbio/blob/main/doc/ABIO%20Design/ABIO%20Roadmap.md)** — Milestones and release plan
- **ABIO Todo** — Tasks, open questions, and documentation todos
