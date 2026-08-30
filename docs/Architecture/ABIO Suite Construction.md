---
description: "Suite Construction subsystem — how a suite spec becomes a battery of auto-graded tasks over a small set of verified worlds. Set-covering resolves the world/task catch-22; simulated verify-then-keep guarantees ground truth."
---
 [[ABIO Architecture Docs]] · [[ABIO Inference Bench]] · [[ABIO PRD Docs|Scenario Generator PRD]]

# ABIO Suite Construction
**Subsystem**: [[ABIO execution]] > Benchmark generation
Turns a *suite spec* into a **suite** — a battery of auto-graded tasks laid over a small set of verified worlds. This is the built realization of the [[ABIO Inference Bench]]; it sits on top of the world-generation layer defined by the [[ABIO PRD Docs|Scenario Generator PRD]] and does not reinvent it.

## Overview
The deliverable is a **suite**: many gradable tasks (identify-this-pathway, cure-this-disease, explain-this-molecule, …) instantiated over a handful of freshly-generated alien-biology worlds, each task carrying a machine-checkable objective whose ground truth we hold by construction. The central difficulty is a **catch-22**: you don't want to build a world without knowing what you need from it, but you can't carve a concrete task skeleton without knowing what world you're in. Suite Construction breaks that circle by working at two levels of commitment — it first instantiates *task archetypes* (partially-specified, parameterized task kinds) far enough to know what a world must provide, then runs a **set-covering** step that packs those archetypes into as few world envelopes as possible and assigns each task to a world. Only then does it draft base worlds, carve concrete skeletons into them, flesh them out, and **verify by simulation** — the catch-all that lets us wire skeleton chemicals into shared pathways without silently corrupting any task's ground truth.

## Vocabulary (locked)
These terms are used precisely throughout; the naming was chosen to avoid the redundancy between "skeleton" the archetype-structure and "skeleton" the concrete instance.
| Term | Meaning |
|------|---------|
| **suite** | The deliverable — a set of tasks over a set of worlds, each with an objective + verified ground truth. |
| **suite spec** / **suite envelope** | The input. Parameters (possibly stochastic) naming which task archetypes appear, how many of each, and the difficulty targets. |
| **task archetype** | An abstract, parameterized *kind* of task (e.g. identify-a-pathway). Carries archetype parameters (pathway length, distractor count, layers traversed), a broad skeleton structure, and recipes for its evaluator + correct/incorrect answer generators. |
| **world envelope** | Parameters (possibly stochastic) describing a world's generation statistics — species count, chain lengths, chemistry complexity, distractor density. Derived during set-covering to host its assigned archetypes. Corresponds to the `scenario_generator_spec`. |
| **base world** | A partially-built world: molecules + chemical pathways drafted generically from the envelope, *before* any skeleton. Its molecules/pathways are **proposed** — later edited, added to, or clipped. |
| **skeleton** | The concrete, fully-instantiated causal structure of *one specific task in one specific world*: specific molecules picked from the world, plus additions and clippings. The reserved word for the instantiated task structure. |
| **fleshed world** | Base world + all its skeletons + distractor/filler chemistry added to roughly hit the envelope's target statistics. Full physics. |
| **world setup** | A staging of a fleshed world — these organisms, in this vessel, at this pH, these initial concentrations. Changes *no* physics; it is the problem's setup. Many setups per world. |
| **objective** | A task's machine-checkable scorer, plus a correct-answer generator and an incorrect-answer generator, built from the archetype's recipes. |
| **verification** | Simulate control vs. intervention (or run the generated correct/incorrect answers through the objective) to confirm ground truth holds. On failure: discard and regenerate. |

## The pipeline at a glance
Suite Construction runs as an ordered pipeline. Each step commits a little more; the two-level structure (archetype first, concrete skeleton later) is what resolves the catch-22.

- **1 · Archetype instantiation** — Read the suite spec and instantiate it into a bag of **task archetypes** with counts ("3 of pathway-ID, 5 of disease-cure") and archetype-level parameters. Parameters constrain the world (needs 3 biological layers, a chain of length ≥ 4, N distractors) without pinning down specific transitions or molecules.
- **2 · World set-covering** — Treat the archetypes' world-requirements as a covering problem: find a *small* set of **world envelopes** whose statistics can host many archetypes at once, and **assign each task to a world**. This is where the catch-22 breaks — archetype parameters are enough to choose worlds, and the assignment fixes which skeletons will live where.
- **3 · Base-world drafting** — For each world envelope, generate a **base world**: molecular level and chemical-pathway level, drafted generically from the envelope, with *no* skeletons yet. These molecules and pathways are **proposed** — editable in later steps.
- **4 · Skeleton instantiation** — For each assigned task, carve its concrete **skeleton** into its base world: pick specific molecules from what exists, add molecules that don't, clip anything that would damage the intended structure. Multiple skeletons per world — some isolated in separate regions, some forced to share chemistry and reconciled (loosely; verification is the real guard).
- **5 · World fleshing** — Add distractor and filler chemistry so the world *roughly* achieves the envelope's target statistics (approximate, not exact). Yields the **fleshed world**.
- **6 · Objective instantiation** — For each task, build its **objective** from the archetype recipes: the evaluator, the correct-answer generator, the incorrect-answer generator. Often fully computable once the skeleton is fixed (an identified pathway is a set-match against known nodes); sometimes an LLM-instruction recipe when it can't be fully scripted.
- **7 · Verification** — Run the generated correct and incorrect answers through the objective and simulate the world; confirm correct passes, incorrect fails, and the world behaves as intended. On failure — including shared-chemistry conflicts from step 4 — **discard and regenerate**.
- **8 · Setup & packaging** — Attach one or more **world setups** (staging: organisms, vessel, pH, initial state) to each fleshed world, and assemble the verified tasks into the **suite**.

## Step details

### 1 · Archetype instantiation
The suite spec is stochastically expanded into concrete archetype selections and per-archetype parameters. A `task archetype` is deliberately *partial*: it fixes the *shape* of what will be asked and the *demands* it places on a world, but not the specific chemistry. For identify-a-pathway, the parameters might be `{pathway_length, distractor_count, layers_traversed}`; these are exactly the knobs that let the next step reason about what a world must contain (a task needing 3 layers requires a world with ≥ 3 biological layers). The archetype also carries — statically, from its catalog definition — the recipes used in step 6 (evaluator, correct/incorrect answer generators). This makes the archetype the single unit that ties a task's *demand on the world* to its *means of being graded*.

### 2 · World set-covering
The assignment is a covering/packing problem: given the archetype bag and their world-requirements, choose a **minimal set of world envelopes** that collectively host every task, and map each task → world. The goal is to avoid generating one world per task — a good world covers a lot of the waterfront. The envelope that comes out of this step is the join point between the two sides: it is derived to satisfy the union of its assigned archetypes' parameters. (Open: whether the envelope is *only* parameters or also carries some high-level instantiation — see Open questions.)

### 3 · Base-world drafting
Each world envelope is drafted into a **base world** at the molecular and chemical-pathway levels, generically — enough substrate to carve skeletons into, but not the skeletons themselves. Everything here is provisional: the base world is a canvas, and steps 4–5 freely edit, add, and clip it. This is the world-generation layer proper, and it is where Suite Construction leans on the [[ABIO PRD Docs|Scenario Generator PRD]] rather than reinventing generation (see Integration).

### 4 · Skeleton instantiation
Now both sides exist — a refined archetypal task and a base world — so the concrete **skeleton** can be built. The archetype supplies the broad structure ("a linear pathway of length 4 gated by a pH switch"); instantiation binds it to *specific* molecules: reuse what the base world already has where possible, add molecules/reactions where the structure demands, and clip anything that would corrupt the intended causal chain. All skeletons assigned to a world (from step 2) are instantiated into it. Where two skeletons share chemistry, instantiation makes a best-effort reconciliation, but does **not** try to prove non-interference — that is what step 7 is for.

### 5 · World fleshing
The base world plus its skeletons is fleshed into a full world by adding distractor molecules, side-reactions, and background pathways until the world *approximately* matches the envelope's target statistics. Accuracy here is deliberately loose — the statistics are an aesthetic/difficulty target, not a hard constraint. Guards (from the Scenario Generator's background-fill design) keep filler from accidentally creating new essential dependencies or cycles that would perturb a skeleton.

### 6 · Objective instantiation
Each task's **objective** is materialized from its archetype recipes now that the skeleton is concrete. In the common case the recipe is fully computable code: the evaluator is a structured-answer check (a pathway → ordered node-set match; a diagnosis → the perturbed node), the correct-answer generator reads the answer off the skeleton, and the incorrect-answer generator produces plausible near-misses. When a task can't be fully scripted, the recipe is a set of LLM instructions parameterized by the skeleton. Forcing *structured* answers (not free prose) is what keeps even "explain" tasks exactly gradable.

### 7 · Verification
Verification is the keystone: we do not trust the constructed skeleton in isolation, we trust the *verified simulation*. Run the correct-answer generator's output and the incorrect generator's outputs through the objective against the simulated world; the correct answer must pass and the incorrect ones must fail, and the intervention must move the objective the way the skeleton predicts. This simultaneously (a) confirms ground truth survived stochastic fleshing, and (b) catches conflicts where two skeletons sharing chemistry broke each other. Any failure discards the world (or the offending task) and regenerates. The one empirical unknown is the **discard rate** — if too many worlds fail, generation gets expensive, so it should be instrumented from the start.

### 8 · Setup & packaging
A verified fleshed world is physics; a **world setup** stages it into a posable problem (which organisms, in what vessel, at what pH and initial concentrations). One world affords many setups. The final suite bundles each task with its world, its setup, its objective, and the hidden ground truth.

## The two envelopes
There are two distinct envelopes, and conflating them is a modeling error:
- **Suite envelope** (the suite spec) — governs *what tasks* the suite contains and *how hard* they are: archetype mix, counts, and difficulty targets (opacity, causal depth, distractor density, observation budget).
- **World envelope** — governs *world generation statistics*: species count, chain lengths, chemistry complexity, distractor density in the physics.

Both are parameter sets that may be **stochastically derived** from higher-level parameters that set them up. Keeping them separate is what lets a single verified world back many tasks at swept difficulty — you hold the world envelope fixed and vary the suite/difficulty envelope across the battery. (World size and task difficulty are orthogonal: a large sparse world can be trivial and a small dense one brutal.)

## Two levels of world, and the reuse loop
A world has two levels of specification:
- **Fleshed world** — all chemistry and processes fully specified. Expensive to build and verify; the durable asset.
- **World setup** — a staging on top of a fleshed world; no physics change. Cheap and disposable.

Because worlds are the expensive artifact, the pipeline is designed to **rerun over a set of already-constructed worlds as givens**: a new suite spec can be satisfied by reusing existing fleshed worlds (biasing set-covering toward reuse) while freely minting fresh setups and fresh tasks. This yields many suites — or many variants of a suite — at a fraction of the cost of the first, and is how the benchmark stays non-saturating without paying full generation cost every run.

## Integration with existing subsystems
Suite Construction is a *coordinator*; the heavy machinery already exists and must not be duplicated.
- **[[ABIO PRD Docs|Scenario Generator PRD]]** — provides world generation. The **world envelope corresponds to the `scenario_generator_spec`**, and base-world drafting (step 3) + world fleshing (step 5) map onto that PRD's staged pipeline (template resolution → … → background fill). **Integration decision:** a skeleton is best modeled as a *required, verified template* planted before background fill — unifying the PRD's "templates" with the bench's "skeleton primitives" rather than adding a parallel mechanism. (See Open questions.)
- **[[ABIO Inference Bench]]** / **[[ABIO Inference Bench Detail]]** — supplies the conceptual frame this subsystem builds: skeleton-first construction, simulated verify-then-keep, the spectral-probe + injection instrumentation model that makes every answer identifiable-in-principle, and the difficulty dials (opacity, causal steps, distractors). Suite Construction generalizes the Detail doc's single-world pipeline to a *suite over multiple worlds* and reconciles its skeleton-first and answer-first framings through the archetype/set-covering front end.
- **[[ABIO biology]]** — the substrate: [[ABIO Molecule]], [[ABIO Reaction]], [[ABIO Chemistry]], [[ABIO Pathway]], [[ABIO Compartment]]. Skeletons are carved from and into these; the [[ABIO WorldSimulator]] is what step 7 runs.

## Open questions
Genuine forks to resolve as this subsystem is built (route to `ABIO queries.md`):
- **Envelope form** — is a world/suite envelope purely a parameter set, or does it carry some high-level partial instantiation? Affects how much step 2 commits before step 3.
- **Skeleton ↔ template unification** — adopt "skeleton = a required verified Scenario-Generator template," or keep skeletons a separate first-class input to the generator?
- **Set-covering objective** — how aggressively to minimize world count vs. keep tasks isolated (fewer worlds = more shared-chemistry conflicts pushed onto verification).
- **Recipe expressiveness** — which archetypes get fully-scripted objectives vs. LLM-instruction recipes, and where the boundary sits.
- **Discard rate** — the empirical yield of verify-then-keep; must be instrumented early, as it gates generation cost and how aggressively skeletons may share chemistry.

## See Also
- [[ABIO Inference Bench]] — the benchmark idea this subsystem realizes.
- [[ABIO Inference Bench Detail]] — skeleton-first generation architecture + question-type catalog.
- [[ABIO PRD Docs|Scenario Generator PRD]] — the world-generation layer beneath this subsystem.
- [[ABIO Architecture Docs]] — architecture index.
