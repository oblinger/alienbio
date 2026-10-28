---
description: "`pipeline`: M27.4's `build_suite` — sample archetypes from a `SuiteSpec`, cover their feature requirements, then per task either draft a host and carve the motif (carved) or call the archetype's drafter (generated), build the objective, reject-sample on an optional validity gate, check render round-trip and self-grading, and package a `Suite`; `draft_world` is the generic host drafter. Source: `src/alienbio/suite/pipeline.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO suite](ABIO%20suite.md) → [ABIO Pipeline](ha://p/ABIO%20Pipeline) 
# ABIO Pipeline
The assembly line that turns a suite spec into worlds and task instances, composing the M26 engines (cover, carve, verify, grade, render) around each archetype's recipe.

![ABIO Pipeline](ABIO%20Pipeline.svg) 
*Two ground-truth paths* is the topic behind the fork after sampling (carved versus generated; ‡ on the carved path the host is the motif itself).

`suite/pipeline.py` is reached on every run that drafts one of the M27 families: the `identify_pathway`, `discover`, `diagnose`, `predict` and `intervene` heads call `build_suite` for one task and add their EXP oracles ([ABIO Drafters](ABIO%20Drafters.md), [ABIO Generative](ABIO%20Generative.md)); the Expr `suite(...)` head exposes it directly (without `verify_with`) ([ABIO ExprExperiment](ABIO%20ExprExperiment.md)). The engines it composes are [ABIO Cover](ABIO%20Cover.md), [ABIO Carve](ABIO%20Carve.md), [ABIO Verify](ABIO%20Verify.md), [ABIO Grade](ABIO%20Grade.md), [ABIO Render](ABIO%20Render.md) and [ABIO Vocab](ABIO%20Vocab.md); the carved archetype is [ABIO IdentifyPathwayRecipe](ABIO%20IdentifyPathwayRecipe.md). `build_suite` and `draft_world` are re-exported from `alienbio.suite`. The design is [ABIO Suite Construction](../../ABIO%20Architecture/ABIO%20Suite%20Construction.md).



## pipeline Interface
Two type aliases and two public functions; the private stages are `_draft_valid_world`, `_carve_or_raise`, `_resolve_objective` and `_assert_task_consistent`.

| pipeline | |
| --- | --- |
| [Perturbation](#^perturbation) | A world-to-world edit |
| [ValidityPredicate](#^validitypredicate) | Baseline and perturbed timelines to a verdict |
| [draft_world](#^draft-world) | A host that contains a motif |
| [build_suite](#^build-suite) | Spec to worlds and tasks |

**Perturbation**` = Callable[[WorldImpl], WorldImpl]`
    The edit half of `verify_with` ([ABIO Perturbations](ABIO%20Perturbations.md) has three). ^perturbation

**ValidityPredicate**` = Callable[[Timeline, Timeline], bool]`
    The verdict half ([ABIO Validity](ABIO%20Validity.md)'s `non_obvious_causal`). ^validitypredicate

**draft_world**`(motif: Motif, seed: Seed = Seed(0), *, distractor_count: int = 0) -> WorldImpl`
    One molecule per role named after the role, one reaction `a → b` per motif edge at a seed-drawn rate in `[0.1, 1.0)`, and `distractor_count` molecules `d0 …` with no reactions; the first role starts at 100, distractors at 1, the rest at 0. The structure is seed-invariant; only rates vary. ^draft-world

**build_suite**`(spec: SuiteSpec, seed: Seed = Seed(0), *, n_tasks: int = 1, distractor_count: int = 0, verify_with=None, max_redraws: int = 8, sim_cfg: SimConfig = SimConfig()) -> Suite`
    Samples `n_tasks` archetypes from `spec.archetype_mix` (`seed.child(f"arch/{i}")`), covers their `feature_reqs`, then per task follows § [Two ground-truth paths](#two-ground-truth-paths), builds a vocabulary, the question and the objective, runs the consistency guard, and appends `TaskInstance(archetype, world=f"world{i}", skeleton, objective, question, setup={"container": i's cover index})`. `ValueError` for `n_tasks < 1`; `RuntimeError` from a failed carve, a carve that synthesized nodes, an exhausted reject loop, an outcome archetype with no drafted objective, or a failed guard. ^build-suite




# Pipeline Semantics

## Two ground-truth paths
**Generated** (the archetype has a `drafter`): the drafter returns `(world, skeleton, objective?)` from `seed.child(f"draft/{i}")`; a drafted objective is used as is. **Carved** (no drafter): `_draft_valid_world` drafts a host with `draft_world` and, when `verify_with` is given, simulates the host and its perturbation and redraws up to `max_redraws` times until the predicate passes; `carve` binds the motif, `splice` is computed and discarded, and a carve that synthesized nodes is refused. The key comes from `recipe.build_key`.

Because `draft_world` names each molecule after its role and adds one reaction per motif edge, the carved host is the motif plus disconnected distractors: `identify_pathway` with 4 nodes and 3 distractors drafted molecules `r0 … r3`, `d0 … d2` and exactly the three reactions of the answer chain. Every reaction in the world is on the answer path, and the distractors never change from 1.0. The carve is an identity binding; the task's difficulty rests on the agent not seeing the reaction list or the trajectories.



## The consistency guard
Every task's question must survive `parse(render(q)) == q` over the task's vocabulary; an answer key must also round-trip and grade 1.0 against itself; an outcome objective's scorer must give a finite score in `(0, 1]` on `simulate(world, sim_cfg)`. The rendered text and the vocabulary are then dropped. The cover's container index is recorded on each task but no two tasks share a world.




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084), from the source at alienbio HEAD `64988be`; the identity host (3 reactions, all on the key) confirmed by drafting `identify_pathway(pathway_length=4, distractor_count=3)` through the Expr head on the HEAD export, no spend. Left out: the M28.1 shared-world path the module docstring defers.
