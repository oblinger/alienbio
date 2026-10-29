:>> [ABIO](../ABIO.md) → [ABIO Design](ABIO%20Design.md) → [ABIO Roadmap](ha://p/ABIO%20Roadmap) 
# ABIO Roadmap
Shape B task-checklist roadmap for the alienbio project — 3 forward milestones here; the 41 completed ones live in [[ABIO Completed Roadmap]] (migrated 2026-09-16).

| Milestone | State | Next |
| --- | --- | --- |
| M-Bench | Not started | M-Bench.1 — design-session workflow |
| M-FixPoint | Future 🔮 | M-FixPoint.1 — alignment-adjustment loop |
| M-Harden | Proposed (awaiting review) | M-Harden.1 — cost-model conformance |
| Completed | [[ABIO Completed Roadmap]] |  |

**Related**: [[ABIO alienbio]], [[ABIO Testing Guide|Testing]] 

| Table of Contents |  |
|---|---|
| **[Open Items](#Open%20Items)** |  |
|    [Auto-resolved](#Auto-resolved) |  |
|    [Q2 — All seven hardening legs, or the free five? (auto-resolved 2026-10-08)](#Q2%20%E2%80%94%20All%20seven%20hardening%20legs,%20or%20the%20free%20five?%20%28auto-resolved%202026-10-08%29) |  |
| **[Meta-Thesis — what this framework is for](#Meta-Thesis%20%E2%80%94%20what%20this%20framework%20is%20for)** |  |
| **[Milestone renaming (2026-09-16)](#Milestone%20renaming%20%282026-09-16%29)** |  |
| **[M-Bench.1 — Interactive design-session workflow](#%5B%20%5D%20M-Bench.1%20%E2%80%94%20Interactive%20design-session%20workflow)** |  |
|    [The loop, in the tooling that now exists (2026-10-07)](#The%20loop,%20in%20the%20tooling%20that%20now%20exists%20%282026-10-07%29) |  |
| **[M-Bench.2 — World-validity tests ("test the world")](#%5B%20%5D%20M-Bench.2%20%E2%80%94%20World-validity%20tests%20%28%22test%20the%20world%22%29)** |  |
| **[M-Bench.3 — Curriculum design](#%5B%20%5D%20M-Bench.3%20%E2%80%94%20Curriculum%20design)** |  |
| **[M-Bench.4 — Gameability / red-team of a design](#%5B%20%5D%20M-Bench.4%20%E2%80%94%20Gameability%20/%20red-team%20of%20a%20design)** |  |
| **[M-Bench.5 — Encode as catalog fixtures](#%5B%20%5D%20M-Bench.5%20%E2%80%94%20Encode%20as%20catalog%20fixtures)** |  |
| **[M-FixPoint.1 — Iterative self-/successor-alignment adjustment loop (initial-condition variation)](#%5B%20%5D%20M-FixPoint.1%20%E2%80%94%20Iterative%20self-/successor-alignment%20adjustment%20loop%20%28initial-condition%20variation%29)** |  |
| **[M-FixPoint.2 — Trajectory / attractor / perturbation analysis across generations](#%5B%20%5D%20M-FixPoint.2%20%E2%80%94%20Trajectory%20/%20attractor%20/%20perturbation%20analysis%20across%20generations)** |  |
| **[M-Harden.1 — Cost-model conformance (H6)](#%5B%20%5D%20M-Harden.1%20%E2%80%94%20Cost-model%20conformance%20%28H6%29)** |  |
| **[M-Harden.2 — World contracts (H1)](#%5B%20%5D%20M-Harden.2%20%E2%80%94%20World%20contracts%20%28H1%29)** |  |
| **[M-Harden.3 — Metamorphic relations (H5)](#%5B%20%5D%20M-Harden.3%20%E2%80%94%20Metamorphic%20relations%20%28H5%29)** |  |
| **[M-Harden.4 — Fault injection (H3)](#%5B%20%5D%20M-Harden.4%20%E2%80%94%20Fault%20injection%20%28H3%29)** |  |
| **[M-Harden.5 — Brief entailment (H2)](#%5B%20%5D%20M-Harden.5%20%E2%80%94%20Brief%20entailment%20%28H2%29)** |  |
| **[M-Harden.6 — Record and replay (H4)](#%5B%20%5D%20M-Harden.6%20%E2%80%94%20Record%20and%20replay%20%28H4%29)** |  |
| **[M-Harden.7 — Live conformance (H7)](#%5B%20%5D%20M-Harden.7%20%E2%80%94%20Live%20conformance%20%28H7%29)** |  |
| **[M-Harden.8 — Close the capability matrix's own gaps](#%5B%20%5D%20M-Harden.8%20%E2%80%94%20Close%20the%20capability%20matrix's%20own%20gaps)** |  |
| **[Agents sharing one world](#%5B%20%5D%20Agents%20sharing%20one%20world)** |  |
| **[Yet to be added to the roadmap](#Yet%20to%20be%20added%20to%20the%20roadmap)** |  |

## Open Items
<!-- state:q nk -->

- **Q1 — Which forward milestone opens next, now that every AUP-driven row is built?** — [[ABIO Roadmap]]'s three forward milestones are all gated on you, in different ways, and nothing else on the backlog is agent-runnable: [[ABIO Roadmap#M-Bench — World & Curriculum Design Bench (Fable-driven)|M-Bench]] needs you in the critique seat (its loop is now defined — [[ABIO Roadmap#The loop, in the tooling that now exists (2026-10-07)|step by step]] — but steps 1 and 5 are a session with Fable, not a build), [[ABIO Roadmap|M-Harden]] is marked *proposed, awaiting review* and its eight legs are new capabilities, and [[ABIO Roadmap#M-FixPoint — Iterative multi-generation / fixed-point support (future) 🔮|M-FixPoint]] is explicitly future. Meanwhile [[AUP]] is live and spending on four runs against this instrument. ^ABIO-Roadmap-Q1
- **(A)** schedule the M-Bench design sessions — the benchmark worlds you actually believe in, replacing the auto-generated hello-worlds; needs your hours, not just your go.
- **(B)** approve M-Harden and let it run unattended — the instrument's own test suite (world contracts per drafter, metamorphic relations, fault injection, brief entailment, record/replay, live conformance); no sessions needed, and it is what makes an AUP number defensible.
- **(C)** neither: ABIO stays reactive to AUP's asks until their phase-4 runs are read, and the roadmap row goes to sleep.
- **Recommendation:** Lean (B) — it needs one word from you rather than your afternoons, every leg is agent-runnable, and the failures it would have caught are the ones that already cost AUP real runs (the 8-turn cost estimate, the resume that re-reported error trials, the chain-lag that made W2 depth unmeasurable). (A) is the higher-value work but it is the one that cannot start without you in the room. · *why-ask: locking — M-Harden is a proposal you have not reviewed, and its first leg writes a `WorldContract` into all eleven drafter heads, which is an interface every later experiment is read against.*
- **Risk of (B):** interface — M-Harden.2 writes a `WorldContract` into all eleven drafter heads, which every later experiment is then read against.
- **Damage:** locking — the contract interface M-Harden.2 introduces is what every later experiment is read against, so the choice is baked into the paper's instrument.
- **On answer:** (A) → book the sessions and I prepare the first proposal in the step-1 shape before you sit down; (B) → M-Harden.1's conformance check lands first, then .2's `WorldContract` on `pressure` as the pattern before the other ten; (C) → the roadmap row sleeps and ABIO answers only AUP drops until their phase-4 runs are read.

### Auto-resolved

### Q2 — All seven hardening legs, or the free five? (auto-resolved 2026-10-08)
[[ABIO Hardening Proposal#What you are approving|the proposal's first open question]]: H6, H1, H5, H3 and H2's weak form cost nothing to run; H2's judge form (~$2 a pass), H4 (four days of plumbing, $0 after capture) and H7 (~$20 a pass) are the ones that spend. The two spends have their own questions on [[ABIO Backlog#^T080|T080]] and [[ABIO Backlog#^T081|T081]]. ^ABIO-Roadmap-Q2

**Resolved:** (A) — all seven in the proposal's order, H6 first — [[ABIO Backlog#^T075|T075]] through [[ABIO Backlog#^T081|T081]].

auto-resolved (priority) — a leg built before it was needed, or deferred and built when it was; nothing locks

- **(A)** all seven in the proposal's order, H6 first — [[ABIO Backlog#^T075|T075]] through [[ABIO Backlog#^T081|T081]].
- **(B)** the free five now; H4, H7 and the judge form struck from the milestone and re-proposed when the live path has a defect nobody can reproduce.
- **(C)** the free five plus H4 — the plumbing that makes the live path testable, without the pass that spends on it.

**Lean:** Lean (A) — the spends are gated by their own questions, so (A) commits attention, not credits, and H4 is what every later parser change is guarded by. - **Risk of (A):** commitment — AUP's asks: two build-weeks on the instrument's tests queue behind any drop they send while their phase-4 runs are read.

## Meta-Thesis — what this framework is for

The end-goal of this roadmap is a **framework**, not a set of experiments. We are building a **taint-free, generative, parameterized testing framework** for evaluating deliberative coherence and alignment, whose worlds and tasks cover:

- **Long reasoning chains** — the correct action is reachable only by multi-step deliberation
- **Multi-turn, interactive task settings** — the agent experiments, observes, and iterates under a budget
- **Partial observability** — hidden causal structure that must be *discovered*, not recalled
- **Partial understanding** — genuine (untrainable) uncertainty about the world's mechanisms

Concretely, the framework must be able to *execute the kinds of experiments described in [[AUP]]* (Series A: Deliberative Coherence; Series B: Driver Conflicts; Series C: Modulating Factors). **This roadmap builds the framework CAPABILITIES those experiments require — it does not design or run the experiments themselves.** The ASP experiment catalog is used only to *derive the capability dimensions* (M-Semantic–M-FixPoint below). The far end of the roadmap: "the framework can be dialed along every dimension those experiments need, and run mass trials over composable, orthogonal knobs against a ground-truth oracle" (the M-Trials reliability-map end-state).

> **Scope note (2026-07-12):** exercising *breadth of capability dimensions* is the current meta-goal (Q5) — not perfecting any single benchmark. Milestones M-Semantic+ are deliberately listed as stubs so the shape of "where we're going" is captured without over-committing detail; flesh a stub only when it becomes the active build.

## Milestone renaming (2026-09-16)

Migrated to named milestones per [[DAS Roadmap Facet]] on 2026-09-16 by Tink (~~[[Tink P0032|P0032]]~~). Old ids resolve by this table; feature titles and filenames keep their old ids. Sub-points follow mechanically (M2.3 → M-Gen.3, M20.1.1 → M-Demos.1.1); letter siblings became numeric sub-indices by letter position (a→1, b→2 …) and are listed below the top-level rows.

| Old | New |
| --- | --- |
| M1 (Minimal Simulation Loop) | M-SimLoop |
| M2 (Generator System) | M-Gen |
| M3 (Scenario Execution) | M-Exec |
| M4 (Experimentation System) | M-Expt |
| M5 (System Validation) | M-Valid |
| M6 (Single Compartment Simulation) | M-OneComp |
| M7 (Measurements and Actions) | M-MeasAct |
| M8 (Task Framework) | M-Task |
| M9 (Multi-Compartment Systems) | M-Compart |
| M10 (Disease and Variation) | M-Disease |
| M11 (Diagnosis and Cure Tasks) | M-DiagCure |
| M12 (Test Harness) | M-Harness |
| M13 (JAX Simulator) | M-JAX |
| M14 (Alien Descriptions and Skinning) | M-Skin |
| M15 (Documentation) | M-Docs |
| Milestone 8b (Advanced Analysis) | M-Analysis |
| M16 (Rate Compilation and Sim Integration) | M-RateSim |
| M17 (Bio API Completion) | M-BioAPI |
| M18 (Spec Language Completion) | M-SpecLang |
| M19 (Build System Completion) | M-Build |
| Skipped Test Debt (Unskip previously deferred tests) | M-Unskip |
| M20 (Demonstration Suite & Visualization) | M-Demos |
| M21 (Demo Gallery & Checked-In Results) | M-Gallery |
| M22 (Documentation Publishing & Demo Refactoring) | M-DocsPub |
| M23 (Demo Polish, JAX GPU Demo, and Roadmap) | M-Polish |
| M24 (JAX Vectorization & GPU Scaling) | M-Vector |
| M25 (World & Curriculum Design Bench) | M-Bench |
| M26 (Suite Construction subsystem) | M-Suite |
| M27 (Semantic layer over the M-Suite primitives) | M-Semantic |
| M28 (Controllable-complexity dials) | M-Dials |
| M29 (Benchmark-capability task families) | M-Families |
| M30 (Objective / constitution injection) | M-Constit |
| M31 (Driver-conflict engineering) | M-Conflict |
| M32 (Modulating-factor knobs) | M-Knobs |
| M33 (Measurement & scoring layer) | M-Scoring |
| M34 (Mass-trial automation + cross-dimensional reliability map) | M-Trials |
| M35 (Iterative multi-generation / fixed-point support) | M-FixPoint |
| M36 (Experiment Catalog) | M-Catalog |
| M37 (Conservation-grounded simulation core) | M-Conserve |
| M45 (AUP experiment-readiness) | M-AUPReady |
| M46 (Production experiment operations) | M-ProdOps |
| M47 (Expr: the generative expression language) | M-Expr |
| M48 (ABIO exercised: a capability test matrix inside the module) | M-Matrix |
| M49 (Hardening: make the seams testable) | M-Harden |
| M1.6b | M-SimLoop.6.2 |
| M1.8a | M-SimLoop.8.1 |
| M1.8b | M-SimLoop.8.2 |
| M1.8c | M-SimLoop.8.3 |
| M1.8d | M-SimLoop.8.4 |
| M1.8e | M-SimLoop.8.5 |
| M1.8f | M-SimLoop.8.6 |
| M1.8g | M-SimLoop.8.7 |
| M1.8h | M-SimLoop.8.8 |
| M1.8i | M-SimLoop.8.9 |
| M1.8j | M-SimLoop.8.10 |
| M1.13a | M-SimLoop.13.1 |
| M2.1a | M-Gen.1.1 |
| M2.1a.1 | M-Gen.1.1.1 |
| M2.1a.2 | M-Gen.1.1.2 |
| M2.1b | M-Gen.1.2 |
| M2.1b.1 | M-Gen.1.2.1 |
| M2.1b.2 | M-Gen.1.2.2 |
| M2.1b.3 | M-Gen.1.2.3 |
| M2.1c | M-Gen.1.3 |
| M2.1c.1 | M-Gen.1.3.1 |
| M2.1c.2 | M-Gen.1.3.2 |
| M2.1d | M-Gen.1.4 |
| M2.1d.1 | M-Gen.1.4.1 |
| M2.1d.2 | M-Gen.1.4.2 |
| M2.1d.3 | M-Gen.1.4.3 |
| M2.1d.4 | M-Gen.1.4.4 |
| M2.1e | M-Gen.1.5 |
| M2.1e.1 | M-Gen.1.5.1 |
| M2.1e.2 | M-Gen.1.5.2 |
| M2.1e.3 | M-Gen.1.5.3 |
| M2.1e.4 | M-Gen.1.5.4 |
| M2.1f | M-Gen.1.6 |
| M2.1f.1 | M-Gen.1.6.1 |
| M2.1f.2 | M-Gen.1.6.2 |
| M2.1f.3 | M-Gen.1.6.3 |
| M3.12b | M-Exec.12.2 |
| M3.14a | M-Exec.14.1 |
| M3.14b | M-Exec.14.2 |
| M3.14c | M-Exec.14.3 |
| M3.14d | M-Exec.14.4 |
| M3.14e | M-Exec.14.5 |
| M8.1 (Milestone 8b) | M-Analysis.1 |
| M8.2 (Milestone 8b) | M-Analysis.2 |

# [ ] M-Bench — World & Curriculum Design Bench (Fable-driven)

**Why these stay unchecked rather than deferred** (decided 2026-10-07, mine):
every forward item here waits on Dan — the sessions for the content, his go
for M-Harden — so the roadmap row's `[Ready]`, which the machinery computes
from unchecked milestones, overstates what an agent can start. Marking them
`deferred` would make the count read zero and the bracket compute to
`[Waiting]`, which is tempting and wrong: `deferred` is a statement that a
milestone is parked, and these are not parked — they are the next thing to
do, waiting only on a decision that [[ABIO Roadmap#^ABIO-Roadmap-Q1|Q1]] 
asks. A roadmap that reads "all deferred" would misrepresent the project to
the next reader. The row's `next::` carries the caveat instead.

**Near-term priority** (ahead of M-Vector in intent, despite the number). Use the Fable access window to interactively design alien worlds and a graded curriculum that Dan actually believes in — replacing the auto-generated hello-worlds — plus the tooling to *test a design before trusting it*. Fable acts as the world designer (design → run in sim → self-correct); Dan steers against research aims. Prerequisite for any later "run agents through the benchmark" (evaluation) work.

**Aims resolved 2026-07-12 (F001 Q1–Q6 — the M-Bench aims-interview):** primary capability = **mechanism discovery** first, with diagnosis→intervention→prediction as further-out rungs (Q2-A + extend); interaction mode = **interactive, multi-turn** built now, single-shot a special case (Q3-B); first difficulty axis = **network size / complexity** (Q4-A, owner override), other axes follow; "real world" gates = non-obvious causal structure (A) + shortcut-resistance (C), kept as world-validity tests but **the current meta-goal is exercising breadth of capability dimensions, not perfecting realness** (Q5); thesis confirmed as the [[ABIO Roadmap#Meta-Thesis|meta-thesis]] (Q6). Full capability inventory these imply: [[ABIO Capability Dimensions]].

## [ ] M-Bench.1 — Interactive design-session workflow
- [x] Define the loop: Fable proposes a world, runs it in the simulator, checks the dynamics, Dan critiques against aims, iterate  *(defined 2026-10-07, below)*
- [ ] Fable designs coherent biochemistries (molecules/reactions/pathways) whose dynamics produce an intended, non-degenerate regime  *(needs a session with Dan in the critique seat)*
- [x] *Machinery* — capture a design as a reproducible spec, not a chat one-off: step 5's `catalog/examples/` shape (M48.9)
- [ ] **Content** — the agreed designs themselves, which is what the sessions produce

### The loop, in the tooling that now exists (2026-10-07)

One turn of the loop is five steps, and every step is a command rather than
a judgement, so a session leaves a record instead of a transcript:

1. **Propose** — Fable writes a drafter head, or a spec over an existing
   one, declaring the regime it intends in words first: which pools must
   move, which must not, which route reaches the goal, what a do-nothing
   agent reaches. That declaration is the thing Dan critiques; the code is
   downstream of it.
2. **Draft and gate** — the draft runs its own refusals before anything
   else sees it: the passive gate (a world a do-nothing agent clears is
   refused), `suite/boundedness.py` (no pool runs away or dies), and
   `bio/conservation.py` when the world declares atoms. A world that
   cannot state its intended regime as a gate is not yet a design.
3. **Run the zero** — `bio suite run <spec>` with a scripted agent, which
   costs nothing and produces `records.jsonl`, `report.txt` and the one
   key figure (`key.png`, `suite/plots.py`). The zero is a claim about the
   instrument, not about a model: it says what the world does when driven
   by a policy whose behaviour is known exactly.
4. **Read the dynamics** — the readouts that already exist answer "is this
   the intended regime": `suite/dose.py` for a monotone response to a
   dial, `readout_series` for the per-turn trajectory, `suite/census.py`
   for how engaged each arm was, the acceptance-test shape of
   `tests/suite/test_pressure_acceptance.py` for "trivial agent fails,
   intended solution succeeds" (M-Bench.2's third item, already live on
   W1).
5. **Land or iterate** — an accepted design lands as a checked-in spec
   under `catalog/examples/` (the M48.9 shape: a folder with its spec, its
   own guards and a CI test that runs it), never as a chat artifact. A
   rejected one goes back to step 1 with Dan's objection written into the
   proposal, so the next turn starts from the objection.

**What this milestone still owes**, once the sessions happen: a world
contract per design (M-Harden.2 generalizes step 2's gates into a declared
`WorldContract` the drafter carries and `bio verify` enforces per lever),
and the red-team pass of M-Bench.4 against each accepted design.


## [ ] M-Bench.2 — World-validity tests ("test the world")

Split 2026-10-07 into the machinery (built elsewhere) and the per-design
content (still owed), so the checkbox means one thing.

- [x] *Machinery* — assert the world reaches its intended regime: the passive gate (a world a do-nothing agent clears is refused), `suite/boundedness.py` (no pool runs away or dies), `bio/conservation.py` where the world declares atoms
- [x] *Machinery* — "trivial agent fails, intended solution succeeds" as an acceptance shape: `tests/suite/test_pressure_acceptance.py`'s five criteria, live on W1 since M45.1
- [x] *Machinery* — a real perturbation that breaks the intended pathway, and a task that reads whether it was repaired: M36.10's diagnosis world and destructive assay
- [ ] **Content** — those three gates WRITTEN FOR EACH ACCEPTED DESIGN, which needs the designs: a declared intended regime per world, its own acceptance pair, its own perturbation. M-Harden.2's `WorldContract` is the generalized form of exactly this, which is why these two should land together whichever way [[ABIO Roadmap#^ABIO-Roadmap-Q1|Q1]] goes

## [ ] M-Bench.3 — Curriculum design
- [ ] Graded difficulty ladder; each rung isolates one target capability (structure → dynamics → intervention → hidden-mechanism hypothesis)
- [x] Gap analysis vs. the worlds that exist — [ABIO Curriculum Map](ABIO%20Curriculum%20Map.md) (2026-10-27, T073): `pathway_puzzles` promoted to rung 1; the H1–H5 hello-worlds were deleted at M47.7
- [ ] Rungs 2–4 as neutral worlds: a predict key that varies with the world (grid, branched), a passive-gated intervention (agent_loop, gated), a hidden-reaction hypothesis (H5 restored); cascade's locus drawn per seed; an oracle agent per rung

## [ ] M-Bench.4 — Gameability / red-team of a design
- [ ] Can an agent short the scoring without doing the "biology"? Fable adversarially probes each design
- [ ] Tighten scoring / visibility so the intended capability is what's actually measured

## [ ] M-Bench.5 — Encode as catalog fixtures

Split 2026-10-07, as M-Bench.2: the shape shipped with M48.9, the content
waits on the designs.

- [x] *Machinery* — the fixture shape and its CI: `catalog/examples/` holds nine runnable example worlds, each a folder with its spec, its own guards and a test that runs it (M48.9); a tenth lands the same way with no new plumbing
- [x] *Machinery* — documented so a later evaluation pass can consume them: every example is in the Guide and runs in `bio report`
- [ ] **Content** — the accepted worlds and the curriculum THEMSELVES, which is what M-Bench.1's sessions produce and M-Bench.3 orders


# [ ] M-FixPoint — Iterative multi-generation / fixed-point support (future) 🔮

Direction-3 experiments; explicitly future.

## [ ] M-FixPoint.1 — Iterative self-/successor-alignment adjustment loop (initial-condition variation)

## [ ] M-FixPoint.2 — Trajectory / attractor / perturbation analysis across generations

# [ ] M-Harden — Hardening: make the seams testable  *(PROPOSED — awaiting Dan's interface review)*

Design and rationale: [[ABIO Hardening Proposal]]. Nothing here is built; each item adds a public interface to the framework, which is why it waits on review.

**Why.** Four defects surfaced in live runs in one week — `estimate_cost` blind to `episode(max_turns)`, `resume` reusing error records as completed trials, the down variants' chemistry note naming the driver where the probe and oracle name the target, and M4's headline carried by turns where the agent did nothing. Each is two representations of one fact drifting apart at a seam. None is a component computing the wrong answer, which is why 28,540 lines of unit tests missed all four, and golden hashes pin behaviour rather than meaning so they cannot catch this class at all. `tests/integration/` holds one file of one line; the repository has exactly one live-model test.

Ordered by catch-per-dollar, not ambition.

## [ ] M-Harden.1 — Cost-model conformance (H6)
- [x] `estimate_cost` defaults `expected_turns` from the declared `episode(max_turns=…)`  *(landed 2026-09-09 as `c1f1a9f`, ticked by the 2026-10-08 stoke; the conformance check below is what keeps it true)*
- [ ] `run_experiment` compares estimate to actual spend; warns outside 1.5x, fails outside `--cost-band`
- [ ] the relation asserted directly across the spec matrix
- *Hours of work, $0 to run, permanent tripwire on a number people plan against.*

## [ ] M-Harden.2 — World contracts (H1)
- [ ] each drafter head declares a `WorldContract`: per-lever expected direction and magnitude band, bounded pools, which routes reach the goal and which must not, which ids are structurally hidden
- [ ] `bio verify <drafter> --seeds N` drafts, drives each declared lever in isolation, and fails any assertion the dynamics do not honour
- [ ] all 11 drafters carry one; a new drafter without one is incomplete
- *The generic form of the only test that has caught a generator defect. $0 to run.*

## [ ] M-Harden.3 — Metamorphic relations (H5)
- [ ] `alienbio.suite.metamorphic` registry, run by `bio verify --relations`
- [ ] opaque ≡ transparent naming (modulo the name map) · axis order permuted ≡ same per-cell records · concurrency 1 ≡ 8 · spec → manifest → spec is the identity · scoring twice is stable
- [ ] probes on ≡ off and resume ≡ uninterrupted move into the registry from where they live now
- *$0 to run; the home for every future "surely that cannot matter".*

## [ ] M-Harden.4 — Fault injection (H3)
- [ ] `alienbio.suite.faults.FlakyProvider(inner, *, rate, kinds, turns)`: provider 400/429/500, truncated JSON, malformed action, empty content, timeout
- [ ] the failure lattice as parametrised tests: recorded, ceiling held with probe spend excluded, repaired by resume, never double-counted by aggregate
- [ ] the same wrapper around the real provider, to learn what its errors actually look like
- *$0 around the fake. This is the code path `resume`'s defect lived in, unreachable without a prior failure.*

## [ ] M-Harden.5 — Brief entailment (H2)
- [ ] `bio brief-check <drafter>` weak form: every id a registered probe names appears in every told variant's brief
- [ ] `--judge` form: a model reads only the brief and answers the probe
- [ ] standing invariant wherever both arms exist: a told arm scoring BELOW its withheld arm is a probe-answerability failure, not a model result
- *The weak form alone catches the defect that voided M3 on 2026-09-09. ~$2 a pass for the judge.*

## [ ] M-Harden.6 — Record and replay (H4)
- [ ] capture hook at the provider boundary — raw request/response pairs, which records do not currently keep (`deliberation_trace` is post-parse)
- [ ] `bio record --cassette <path>` · `bio replay <cassette>`
- [ ] the catalog zeros and one pressure run captured as standing cassettes
- *The one genuinely new plumbing item. Converts "we cannot afford to test the live path" into "the live path is tested every commit, on real model text, deterministically". $0 after capture.*

## [ ] M-Harden.7 — Live conformance (H7)
- [ ] `bio conformance --live`: 11 drafters × told/withheld × 3 trials
- [ ] structural assertions only — no illegal actions, no taint hits, probes answered in the declared vocabulary, action-format compliance, ceilings respected, our usage accounting matching the provider's own numbers
- *~$20 a pass. Measures that the machine holds, not that any model is aligned.*

## [ ] M-Harden.8 — Close the capability matrix's own gaps
`bio test-matrix` already declares five dimensions we said we wanted and have not built. C7 has a live claim on it: AUP's Bite work keeps asking where a threshold sits and reads it by hand each time.
- [ ] C7 threshold / erosion + recovery measurement  *(partial)*
- [ ] C3 failure-mode classification  *(partial)*
- [ ] B16 user-preference / sycophancy injection  *(planned)*
- [ ] C11 trajectory / attractor / perturbation analysis  *(future)*
- [ ] B18 iterative multi-generation alignment-adjustment loop  *(future)*

# Later

Features to consider for future development.

## [ ] Agents sharing one world
- Two agents acting in the same world at once — the one part of the M1-era "Multi-agent Experiments" item nothing implements. Its other bullets are built: agent and model as grid axes over matched world seeds (M46.8), paired divergence (C10), the idle twin (M45.7); tournament ranking is one aggregate over those axes, not a milestone.

Struck 2026-10-27 (T073, [ABIO Curriculum Map](ABIO%20Curriculum%20Map.md) § Proposed roadmap edits): **Cloud Storage Integration** — run output is `records.jsonl` + `manifest.json` per run directory, not DAT; dvc-dat 3.0 ships no `push`/`pull`, and the `default_remote`/`remote_prefix` config went with T067. **Web Dashboard** — `bio report` writes a self-contained `reports/report.html` with every run's key figure and `bio suite report` reads a run from its store; runs are batch, so "real-time" has no consumer. **Quiescence Detection** (done) moved whole to [ABIO Completed Roadmap](ABIO%20Completed%20Roadmap.md).


## Yet to be added to the roadmap

Under-specified in [[AUP]] as of 2026-07-12 — captured so they aren't lost; promote to milestones once ASP fleshes them:
- **Direction-3 fixed-point experiment outlines** — Fixed Points, Trajectory Prediction, Coherence Attractors, Perturbation Propagation (ASP 5 §5.3 headers marked "new design needed"). Drives M-FixPoint.
- **"Genuine Deliberation" probe** — deliberation vs. cached pattern-matching (noted undocumented in Series A).
- **Specification Sensitivity experiment** — small constitutional-wording changes → outcome robustness (Series A/B).
- **Cross-dimensional analysis details** — which knob-pairs to sweep first; reliability-map schema (ASP §5.4/§6.4). Feeds M-Trials.
- **Statistical-power design** — trials-per-condition targets, effect sizes (ASP §6.5). Feeds M-Trials.2/M-Trials.3.

## ___
line:: [ABIO Roadmap](ABIO%20Roadmap.md) · [1 ready](ABIO%20Roadmap.md#M-Bench.1%20%E2%80%94%20Interactive%20design-session%20workflow) 
status:: Ready
next:: (opus) (dan) [[ABIO Roadmap#^ABIO-Roadmap-Q1|Roadmap Q1]] is the word; [[ABIO Backlog#^T073|T073]] and [[ABIO Backlog#^T074|T074]] landed 2026-10-28, so meanwhile the burn passes run against the code that exists ([[ABIO Backlog#^T088|T088]], [[ABIO Backlog#^T091|T091]]), and [[ABIO Backlog#^T069|T069]]'s yes releases [[ABIO Backlog#^T075|T075]] through [[ABIO Backlog#^T082|T082]] (stoked 2026-10-08)
appears:: ABIO
