---
description: "developer documentation"
---

| -[[ABIO Dev Docs]]-                          | : developer documentation<br>→ [[ABIO]] → [ABIO Dev Docs](ha://p/ABIO%20Dev%20Docs)                                                                                                                                                                                                                                                                                    |
| -------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [Files](ha://ABIO%20Docs/Architecture/ABIO%20Files) |                                                                                                                                                                                                                                                                                                                                                                        |
| **bio/**                                     | [WorldSimulatorImpl](ABIO%20bio/ABIO%20WorldSimulatorImpl.md),  [JaxWorldSimulator](ABIO%20bio/ABIO%20JaxWorldSimulator.md),  [ChemistryImpl](ABIO%20bio/ABIO%20ChemistryImpl.md),  [RateExpr](ABIO%20bio/ABIO%20RateExpr.md),  [TransportFlux](ABIO%20bio/ABIO%20TransportFlux.md),  [PopulationLaw](ABIO%20bio/ABIO%20PopulationLaw.md),  [WorldImpl](ABIO%20bio/ABIO%20WorldImpl.md),  [WorldStateImpl](ABIO%20bio/ABIO%20WorldStateImpl.md),  [ReactionImpl](ABIO%20bio/ABIO%20ReactionImpl.md), |
| **suite/**                                   | [Runner](ABIO%20suite/ABIO%20Runner.md),  [TaskBrief](ABIO%20suite/ABIO%20TaskBrief.md),  [NameMap](ABIO%20suite/ABIO%20NameMap.md),                                                                                                                                                                                                                                                                                   |
| ...                                          | [[ABIO bio]],  [[ABIO suite]],                                                                                                                                                                                                                                                                                                                                         |

# ABIO Dev Docs
One doc per source module of `~/ob/grove/alienbio`, each named after its primary class and opened by a hand-drawn figure, under folders that mirror `src/alienbio/`.

A folder row above lists the module docs written so far; a module with no link has no doc yet. The order of work is the one [[ABIO Architecture]] § Subsystems gives, riskiest first: `bio/` (the chemistry substrate — one compiled rate grammar and two simulators that must agree to 1e-9, where a wrong number corrupts every trial silently), then the `suite/` runtime (the live loop, the brief, the real-model agent), then the experiment pipeline, the generators, `expr/`, the operator surface and `infra/`. The synthesis layer lives elsewhere: [[ABIO Architecture]] for the eight subsystems and their seams, the published [[ABIO Docs]] tree for the user-facing guide.

# BRIEF

- 2026-10-18 — opened on Tink's burn-night ask (deep-scan box 3, [[ABIO Backlog#^T084|T084]]): module docs per [[DAS Module Doc Facet]] with a figure per [[DAS SVG Diagram Facet]], one doc per step, the burn guard (`~/.cache/burn-guard/state`) read before each.
- **Names carry the class as the source spells it** (`WorldSimulatorImpl`, not `WorldSimulator`) because the published class pages under `ABIO Docs/Architecture/Classes/` already hold the bare names, and a second file of the same basename makes every wiki-link ambiguous.
- **Rows are links only** (R-dispatch-table-06); a module's one-line description is its doc's `description:` frontmatter.
- **The Files page is not linked back here.** It is a mirrored repo page, published by mkdocs; a wiki-link to a vault-only doc would publish broken. This page is the index.
- **Vault-side, no commits.** The docs live in the vault, which is a commons swept hourly; the repo mirror does not cover this folder, so "commit each doc" is the sweep's job.
