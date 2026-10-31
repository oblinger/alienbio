---
description: "M27 semantic layer — the Opus-authored content (task-archetype catalog + controlled vocabularies + world-validity predicates + end-to-end wiring) that supplies the M26 neutral primitives their opaque material. Design spec grounded in the actual suite/ seams."
---
:>> [ABIO](../ABIO.md) → [ABIO Design](ABIO%20Design.md) → [ABIO Semantic Layer](ha://p/ABIO%20Semantic%20Layer) 
# ABIO Semantic Layer
The **M27 semantic layer** is the content half of Suite Construction.

[[ABIO Suite Construction|M26]] shipped eight *neutral* engines (`suite/` — FT01–FT08) that manipulate opaque tokens, motifs, predicates, and recipes but contain **no biology and no task meaning**.

M27 authors that meaning: the concrete `TaskArchetype`s, `Vocabulary`s, and world-validity `Predicate`s the engines close over, plus the wiring that runs them end-to-end into a materialized `Suite`. It is **Opus-authored** (design, not mechanical) and was unblocked by the M25 aims-interview ([[ABIO001 - M25 aims interview + M9 ablation|F001]], all six Qs resolved).

This doc is the build spec for backlog **[F005](../ABIO%20Track/ABIO%20Features/ABIO005%20-%20M27%20semantic%20layer%20over%20M26%20primitives.md)** and roadmap **[[ABIO Roadmap|M-Semantic]]** (M27.1–M27.4). It is grounded in the real seams in `src/alienbio/suite/` — every type and function named below exists on `main` today.

## Scope boundary — why authoring this is framework work, not experiment design

The owner drew a hard line ([[ABIO006 - Framework-capability roadmap (M27+) - MUX-session build handoff &|F006]] § Verbatim user direction): **build framework CAPABILITIES; do NOT design or plan the ASP experiments.** The semantic layer sits near that line, so the boundary is drawn explicitly here:

- **In scope (framework).** A *reusable, parameterized, domain-neutral* archetype template — "identify-a-hidden-pathway", "diagnose-the-perturbed-node", "explain-this-molecule". These are exactly the archetypes the owner-approved [[ABIO Suite Construction]] architecture already names as *the deliverable* ("identify-this-pathway, cure-this-disease, explain-this-molecule, …"). Authoring them is **implementing approved architecture**. Each is a template with parameters (pathway length, distractor count, layers traversed) — machinery, not a specific scenario.
- **Out of scope (experiment design).** Authoring a *specific engineered world/scenario* that realizes a particular ASP study — e.g. a world tuned so two objectives conflict in exactly the way ASP Series B examines. That is designing an experiment; the framework must be *able to express* it, but M27 does not author it.

**The test:** if the artifact is a generic template parameterized by dials, it is framework (in scope); if it is a specific hand-tuned instance chosen to probe a research hypothesis, it is experiment design (out of scope). Every archetype below is written to the generic side of that test.

One residual confirmation is parked for the owner (§ Open question) — but M27.2, M27.3, and M27.4 are unambiguously framework and proceed regardless.

## `ObjectiveRecipe` — defining the architecture's named-but-undefined protocol

**Grounded in [[ABIO Suite Construction Data Model]] (the architecture).** That doc's type model already names this protocol: `TaskArchetype: … recipe: ObjectiveRecipe` (L6). But `ObjectiveRecipe` is **declared and never defined** — it is absent from the [[ABIO Protocols]] glossary, and the code on `main` has drifted to `recipe: Any` (`suite/types.py`). This section *defines* `ObjectiveRecipe`; § Architecture reconciliation below tracks closing the drift. Adopting the architecture's name (not a new one) is deliberate — the semantic layer implements the existing architecture, it does not fork it.

Everything the semantic layer supplies is the **neutral/semantic boundary** the data-model doc already draws (its § "The neutral / semantic boundary" table): each neutral engine consumes one kind of opaque content — set-cover ← *what a feature means*, carve/splice ← *what a role/constraint means*, verify ← *what a predicate means*, graders ← *what "correct" means*, Op harness ← *the directive text*, NL renderer ← *the controlled vocabulary*. M27.1–M27.4 below fill exactly those cells; `ObjectiveRecipe` is the "graders ← what correct means" cell made concrete.

An **`ObjectiveRecipe`** turns a concrete carved `Skeleton` (a binding of the archetype's motif roles to real host nodes) into the two things a `TaskInstance` needs — its `Question` and its `Objective` (`AnswerObjective`/`OutcomeObjective`, per the data model's L5). Proposed definition (a `Protocol`, so recipes stay opaque callables the engines never inspect):

- `recipe.build_question(skeleton, world) -> Question` — emit the structured, opaque `Question(structured, kind)`; `kind ∈ {node_set, ordered_path, node_id, scalar, json}` matching FT08's render kinds.
- `recipe.build_key(skeleton, world) -> Answer` — read the ground-truth `Answer(value, kind)` **off the skeleton by construction** (the whole point of skeleton-first: we hold the answer because we built the structure).
- `recipe.build_distractors(skeleton, world, seed) -> tuple[Answer, ...]` — plausible near-misses (for MC framings / incorrect-answer generation).
- `recipe.grader_spec() -> GraderSpec` — which FT06 grader + partial-credit config (`node_set`→`partial`, `ordered_path`→`partial`, `scalar`→`tol`).

The `Objective` is then `AnswerObjective(grader=recipe.grader_spec(), key=recipe.build_key(...))` (or `OutcomeObjective` for act-and-score tasks). This keeps every archetype's *demand on the world* (its `motif`; also `feature_reqs` until 2026-10-30) tied to its *means of being graded* (its recipe) in one unit — exactly the join the data-model doc draws. Recipes that cannot be fully scripted fall back to an `LLMOp` (FT07 / the "Op harness ← directive text" cell) parameterized by the skeleton; the default for the discovery family is fully-scripted.

> **This signature is a proposal, not settled** — it is the one part of the design that pins a new API surface (§ Open question tracks the scope; the shape itself wants an eyes-on before code). The *name* and *role* (`ObjectiveRecipe`, produces the `Objective`) are fixed by the architecture; only the method breakdown is mine to defend.

## M27.1 — Task-archetype catalog (mechanism-discovery first, per Q2-A)

The first archetype, concretely, as the template for the rest:

**`identify_pathway`** — recover a hidden linear pathway from experiments.
- **`motif`** — a `Motif` of `RoleSlot`s `r0…r_{k}` (k = `pathway_length`) with `edges` `(r_i, r_{i+1}, "reacts_to")`; each `RoleSlot.constraints` are opaque `Predicate`s (e.g. "is a small molecule", "not already in a named pathway"). Distractor roles are added but left un-edged into the chain.
- **`verb`** — `"identify"` (drives FT08 template selection).
- **`feature_reqs`** — a `FeatureSet` requiring the host world to support the motif: `≥ layers_traversed` biological layers, a reaction chain of length `≥ pathway_length`, `≥ distractor_count` off-path species. These become the covering constraints in M27.4. *Removed 2026-10-30 (`288bf7a`, T091 AF6): no archetype ever declared a feature, so `TaskArchetype` has no `feature_reqs`.*
- **`recipe`** — question kind `ordered_path`; key = the ordered node-set the carve bound the chain to; distractors = permutations / off-path swaps; grader `ordered_path` with `partial` on.

Further discovery-family archetypes (same shape, listed as stubs — fleshed when built): `diagnose_perturbation` (M29.2 substrate; question kind `node_id`, key = perturbed node), `classify_molecule` (`explain`-style, structured `json` answer). Diagnosis→intervention→prediction are the harder rungs (Q2 "build toward all, discovery first").

## M27.2 — Controlled vocabularies for FT08

FT08 (`render.py`) already renders `Question`/`Answer` deterministically over a `Vocabulary` — a **bijection** token↔surface-phrase (injective, no reserved `SEP`/`EMPTY`), with `render(parse(x)) == x` proven per kind. M27.2 authors:
- **`Vocabulary` instances** — a stable, injective token→phrase map for the node namespace of a world (alien-molecule surface names ← opaque node IDs). Per-world, seed-deterministic.
- **Verb→template additions** — the `_TEMPLATES` table in `render.py` keys on `(is_answer, kind)`; the archetype `verb` selects the framing phrase. Add the discovery-family verbs ("Which pathway produces…", "Which node was perturbed…") as fixed templates. **Never an LLM** — deterministic templating only (the FT08 invariant).

This is the most mechanical M27 sub-milestone — pure content into a proven engine.

## M27.3 — World-validity predicates (encode Q5 A + C)

Q5 resolved to two "realness" gates, kept as world-validity tests (`must_satisfy` / `verify` predicates), though breadth-of-dimensions is the current meta-goal, not perfecting realness:
- **(A) Non-obvious causal structure** — the answer must not be readable from surface stoichiometry; it requires the perturbation/observation loop. Encoded as a `verify` predicate over a baseline-vs-perturbed `Trace` pair: the target relationship must be **invisible in baseline alone** and **only revealed under perturbation** (reject-sample worlds where it isn't).
- **(C) Shortcut-resistance** — a degree/centrality/name-frequency heuristic must not crack it. Encoded as a non-degeneracy `Predicate`: the ground-truth answer must not coincide with the top-ranked node under a small battery of cheap heuristics.

These plug into the existing `verify(world, perturbation, predicate, …)` reject-sampling seam (M25.2 "test the world") and into `cover`'s `admissible` callback. They are opaque predicates — framework machinery, no experiment content.

## M27.4 — End-to-end wiring

One `SuiteSpec → Suite` run, composing the shipped engines in order (all signatures real, on `main`):

1. **Archetype instantiation** — expand `SuiteSpec.archetype_mix` (a `Dist[TaskArchetype]`) + `per_archetype` schemas into a bag of parameterized archetypes.
2. **Cover** — `cover(items=[a.feature_reqs for a in bag], admissible=world_validity, …) -> Cover`; each container = one world envelope hosting many archetypes; assignment fixes task→world.
3. **Base-world drafting + fleshing** — generate a `ReactionNetwork`/`World` per envelope satisfying the union of its `feature_reqs` (reuses the M28.1 complexity dial for size).
4. **Carve + splice** — for each assigned archetype, `carve(host, archetype.motif, seed) -> Skeleton` (reuse-maximal binding), then `splice(host, skeleton)` to wire synthesized nodes in.
5. **Objective instantiation** — `recipe.build_question` / `build_key` / `grader_spec` → `Question` + `AnswerObjective` (§ recipe contract).
6. **Verify** — `verify(world, perturbation, predicate=world_validity, …)`; reject-sample worlds that fail A/C or whose skeletons interfere (the catch-all against silent ground-truth corruption).
7. **Render + grade (round-trip check)** — `render(question, vocab)` and `render(key, vocab)`; assert `parse(render(x)) == x`; `grade_answer(key, key, spec) == 1.0` sanity.
8. **Package** — assemble `Suite(worlds, tasks)`.

**As built, 2026-10-30 (`288bf7a`, T091 AF6):** steps 2 and 3 are gone. `build_suite` drafts one world per task (`draft_world` over the archetype's motif) and runs no cover: the cover over `feature_reqs` had stamped each task's container index on `setup["container"]`, but no archetype declared a feature, no predicate ever ran on a world and nothing read the stamp, so `TaskArchetype.feature_reqs`, the cover step and the stamp were removed together. `TaskInstance.setup` is `{}`; `cover` remains a primitive behind the `!cover` head.

Deliverable of M27.4: a `suite/pipeline.py` (or `suite/build.py`) `build_suite(spec: SuiteSpec, seed) -> Suite` plus an integration test that runs one small spec green end-to-end.

## Build sequencing

- **Proceeds now (unambiguously framework):** defining `ObjectiveRecipe` (§ ObjectiveRecipe) + closing its architecture drift (§ Architecture reconciliation), **M27.2** (vocabularies), **M27.3** (world-validity predicates), and the **M27.4** wiring skeleton. None author experiment content.
- **Gated on the § Open question:** the *breadth* of the **M27.1** archetype catalog — one generic `identify_pathway` template is clearly framework and can be built to exercise the pipeline; expanding to a large hand-authored catalog is where the owner should confirm appetite.

Per the commit flow ([[ABIO]] CLAUDE.md): build in a worktree off `main`, `just check && just test` green, verify (never trust), merge directly. Keep `suite/` pyright-clean.

## Architecture reconciliation (drift to close alongside the build)

`ObjectiveRecipe` is defined in the *architecture* ([[ABIO Suite Construction Data Model]]) but nowhere else — three surfaces disagree and must converge as M27.1 lands:

| Surface | State today | Reconcile to |
|---|---|---|
| [[ABIO Suite Construction Data Model]] (architecture — source of truth) | `recipe: ObjectiveRecipe` (named, undefined) | Add the method signatures defined above (or a link to them). |
| `suite/types.py` (code, `main`) | `recipe: Any` (drifted) | `recipe: ObjectiveRecipe` — a real `Protocol` in `suite/types.py`. |
| [[ABIO Protocols]] (glossary) | **absent** — and so are `Renderable`, `Op`, `Predicate`, `Directive`, `Vocabulary` | Add the M26/M27 suite protocols to the glossary (a `/module-doc`- or `/architect`-class pass, not hand-authored ad hoc). |

None of this is new capability — it is making the code and the glossary honor the architecture that already exists. Do it in the same worktree as the recipe-contract implementation so the three surfaces land in sync.

## Open question

Parked for the owner in [[ABIO queries]] (not chat): **how much archetype-*content* authoring is in scope for M27.1** — a single generic template to exercise the pipeline (Lean), vs. a broad multi-archetype catalog now. Everything else in this doc proceeds regardless.

## See also

- [[ABIO Suite Construction]] — the M26 subsystem this supplies content to (the pipeline stages map 1:1 to § M27.4).
- [[ABIO Suite Construction Data Model]] — **the architecture** for this: the neutral type model (`TaskArchetype`/`Motif`/`Vocabulary`/`FeatureSet`/`ObjectiveRecipe`) + the neutral/semantic boundary table this doc fills.
- [[ABIO Protocols]] — the anchor's protocol glossary (currently missing the M26/M27 suite protocols — see § Architecture reconciliation).
- [[ABIO Capability Dimensions]] — the capability inventory M27+ builds toward.
- [[ABIO Roadmap]] § M27 — the milestone this fleshes out.
