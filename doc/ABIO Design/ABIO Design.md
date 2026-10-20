---
description: "the design home for the Alien Biology Framework"
---

| -[[ABIO Design]]- | : the design home for the Alien Biology Framework<br>→ [[ABIO]] → [ABIO Design](ha://p/ABIO%20Design)                                                                                             |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Related           | [[ABIO Docs]],  [[ABIO Idea]],  [[ABIO Roadmap]],  [[ABIO Backlog]],  [[AUP]],                                                                                                                    |
| Plan              | [[ABIO PRD\|PRD]],  [[ABIO Completed Roadmap\|Completed Roadmap]],  [[ABIO Capability Dimensions\|Capability Dimensions]],  [[ABIO Experiment Catalog\|Experiment Catalog]],                      |
| Architecture      | [[ABIO Architecture\|Architecture]],  [[ABIO Skeleton Arch\|Skeleton]],  [[ABIO Expr\|Expr]],  [[ABIO Semantic Layer\|Semantic Layer]],  [[ABIO Unified Protocol Model\|Unified Protocol Model]], |
| Proposals         | [[ABIO Phase-2 Design Brief\|Phase-2 Brief]],  [[ABIO Refactor Proposals\|Refactor]],  [[ABIO Hardening Proposal\|Hardening]],  [[ABIO Suite Protocol Assessment\|Suite Protocol Assessment]],    |
| ...               |                                                                                                                                                                                                   |

# ABIO Design
The design home for the Alien Biology Framework (`code` trait).

## Native design docs (this folder)

| Doc | What it is |
|---|---|
| [[ABIO Semantic Layer]] | **M27 semantic-layer build spec** — the archetype catalog + vocabularies + world-validity predicates + end-to-end wiring that supply the M26 neutral engines their opaque content. Grounded in the real `suite/` seams; backs [[ABIO Backlog#^F005\|F005]]. |
| [[ABIO Experiment Catalog]] | **M36 coverage-driver** — 10 experiment TYPES, all fleshed into fully-specified sample experiments (EXP-1…10); reads off the framework capabilities each forces. Backs [[ABIO Backlog#^F011\|F011]]. |
| [[ABIO Capability Dimensions]] | The 35-dimension capability inventory the catalog exercises (the ⬜/🟡/✅ status source). |
| [[ABIO Phase-2 Design Brief]] | **Phase-2 integration architecture** — agent-loop / scenario runner + M31 generators that turn the PR #155 primitives into live capabilities; the load-bearing (simulator-binding / agent-loop-shape) decisions D1–D4 with recommendations. D2–D4 resolved (owner, 2026-07-18); **D1 promoted to the Skeleton subsystem** below. |
| [[ABIO Skeleton Arch]] | **The composition subsystem (resolved D1)** — worlds assembled from typed, stackable building blocks so a small control surface reaches a buried crux only through indirection. Folder-doc: overview + [[ABIO Skeleton Data Model]] + [[ABIO Skeleton Block Catalog]]. The generative substrate behind M31; **for owner review before implementation**. |
| [[ABIO Expr]] | **The Expr language (F007 G4 design note, 2026-08-28)** — the one call-shaped generative form over YAML data that `Motif`/`WorldEnvelope`/`ObjectiveRecipe`/`TaskArchetype`/`SuiteSpec` collapse into; folder-doc: the language + [[ABIO Expr Templates]] (catalog with examples) + [[ABIO Expr Python Escapes]]. |
| [[ABIO Refactor Proposals]] | **What the F253 deep scan says should change (T051 box 5, 2026-09-10)** — eight proposals strongest belief first: delete the M1 remnants, one frozen-state ration on both simulators, one pre-flight, split `experiment.py`, one condition key, live Protocols, one parser per verb; proposals only, nothing executed. |
| [[ABIO PRD]] | **The product statement (rewritten 2026-08-30, T018)** — what ABIO is, its ten requirements with build status, the unified-protocol design principle, the safety-adjacency rule, what is out of scope, and where everything lives. |

Product-level intent and the conceptual benchmark design live here; the **detailed architecture corpus is published from the code repo** and mirrored into `[[ABIO Docs]]` (`ABIO Docs/Architecture/`), so it is *referenced* from here rather than duplicated.

## Benchmark concept (in `[[ABIO Idea]]`)

| Doc | What it is |
|---|---|
| [[ABIO Inference Bench]] | The core benchmark idea ABIO realizes. |
| [[ABIO Inference Bench Detail]] | Skeleton-first generation architecture + question-type catalog. |
| [[ABIO Idea]] | Idea index (control, containment, greybox, DCP conjecture). |

## Architecture corpus (published — mirrored in `[[ABIO Docs]]`/Architecture)

These are the authoritative design/architecture documents. They live in `ABIO Docs/Architecture/` because they are mirrored to the code repo's `docs/` and published on the docs site; edit them there.

| Doc | What it is |
|---|---|
| [[ABIO Architecture Docs]] | The architecture index (start here). |
| [[ABIO Suite Construction]] | Suite Construction subsystem — suite spec → auto-graded tasks over verified worlds. |
| [[ABIO Suite Construction Data Model]] | The neutral contract the M26 primitives close over. |
| [[ABIO biology]] | Molecule / Reaction / Chemistry / Pathway / Compartment substrate. |
| [[ABIO Suite Runtime]] | The suite runtime — the turn loop, agents, sweeps, experiments as artifacts. |
| [[ABIO PRD Docs]] | Scenario Generator PRD — the world-generation layer. |
| [[ABIO Expr Spec]] | The Expr language by example (the spec DSL as built). |
| [[ABIO Notes]] | Design notes. |

## Tracking (in `[[ABIO Track]]`)

Milestones + backlog + open decisions are tracked separately: [[ABIO Roadmap]] · [[ABIO Backlog]] · [[ABIO queries]].

## Structural resolution — corpus stays in the mirror (resolved 2026-07-13)

The architecture corpus stays in `ABIO Docs/` (the mirror), referenced from here rather than re-homed. Rationale (owner, 2026-07-13): the two copies are one corpus in two representations, and the flow is single-directional — **`vault → repo → site`**:

1. **Author** in the vault (`ABIO Docs/`).
2. **Sync leg** — the `.anchor` mirror `ABIO Docs ↔ grove/alienbio/docs` writes the repo copy **read-only** (the derived snapshot). This is the "publish into the repo" step.
3. **Publish leg** — `just docs` (`mkdocs build`, reading the repo `docs/`) → `just docs-deploy` copies `site/` into `oblinger.github.io/abio-docs` and pushes. Published at `https://oblinger.github.io/abio-docs/`.

The publish step **sources from the repo copy, not the vault**, so what is pushed in the repo and what is served on the web are guaranteed consistent. The repo is "the source" for *publishing*; the vault is "the source" for *editing*. A direct vault→website mirror was rejected because the publish leg is a **build** (mkdocs), not a file copy.
