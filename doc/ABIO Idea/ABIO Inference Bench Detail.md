---
description: "How the inference benchmark is generated — skeleton-first: compose a causal skeleton from known primitives, flesh it out, then project templated questions off the skeleton. Plus design risks."
---
:>> [[ABIO]] → [[ABIO Idea]] → [ABIO Inference Bench Detail](ha://p/ABIO%20Inference%20Bench%20Detail) 
# ABIO Inference Bench Detail
How the benchmark is actually generated — the part [[ABIO Inference Bench]] keeps high-level.

| Related | |
| --- | --- |
| Parent | [[ABIO Inference Bench]] (the idea) |
| Catalog | [[ABIO Idea Taxonomy]] |
| Testbed | [[AUP 4 Alien Biology Testbed]] · [[ABIO]] |

The simpler case (this doc's focus): **build a causal skeleton from known primitives, flesh it out, then project questions off the skeleton** — so every answer is known by construction.

## The construction pipeline (skeleton-first)

- **1 · Causal skeleton** — compose an interesting causal skeleton from an *enumerated set of building blocks*: predation chains, scarce-resource contention, contextualized functionality (behavior that switches on e.g. pH), causal composition. *Example:* three predation steps in a row → scarce-resource contention with another species → a pH-gated functional switch. The skeleton **encodes the ground-truth causal structure**.
- **2 · Stochastic fleshing-out** — a biologically-plausible generator adds a *controllable* amount of filler detail, along several dimensions, around the skeleton. Result: a full novel world whose true functionality is already known — because it was built into the skeleton.
- **3 · Templated questions from the skeleton** — bind enumerated question / objective templates to skeleton elements; the answer is read off the skeleton (catalog below). Because every question projects from *one* skeleton, a single world affords a whole battery of gradable items.
- **4 · Simulated verification** — run the finished world forward in both the control and the intervention case and confirm the templated answer actually holds (the intervention moves the objective the way the skeleton predicts). **If it doesn't, discard the world and regenerate** — we don't trust the skeleton, we trust the *verified* simulation. This is what lets us deliberately wire skeleton chemicals into other pathways (so the answer isn't a trivially isolated subgraph) without the confounds silently corrupting ground truth.
- **5 · Expose a view** — give the agent partial knowledge (an *inference* test) or full knowledge (a *deductive-reasoning* test); it must solve.

## Question-type catalog (all projected from the skeleton)

- **Causal pathway** — "explain the causal pathway for [molecule X]," where X is a skeleton node. Answer known by construction.
- **Structural perturbation** — "change the predation chain to cause under/over-population — what happens to [downstream species]?" Answer derivable from skeleton structure.
- **Control vs observed** — present a control world and an observed world that differ by a known skeleton perturbation; *"why is this happening?"*
- **Disease (cure / explain)** — perturb a known homeostatic pathway to construct a disease (we know how to build it because we know the causal structure we're hitting), then ask to *cure the disease* or *explain why the system is failing*. Health indicators: chiefly *stays alive*, plus proxies.

## Instrumentation — observable state, latent mechanism

The vocabulary makes the answer *recoverable* but never *readable* — you observe state, and must infer the mechanism.

- **Spectral probe (observation)** — drop a probe at a chosen point and read out the molecules present plus pH / temperature / pressure. But this is a **momentary, local slice**: it tells you *what exists* at one place and instant — not what's producing or consuming it, nor which mediating molecules gate the reaction rates. The world is many cells / chambers / organisms all changing continuously; you sample one spot, time moves on, you sample again. The reaction network and its regulators stay **latent**.
- **Chemical injection (intervention)** — near-unlimited ability to inject feed chemicals at chosen points, to perturb the parts of the pathway that matter and watch how state responds.
- **Identifiable, but that's the hard part** — state-samples + interventions are *sufficient* to identify the latent mechanism in principle (perturb, observe the response across space and time, reconstruct the reaction network). But that reconstruction — from sparse momentary hits, without knowing the reactions or the rate-mediating molecules in advance — **is the inference problem itself**. The probe's universality is *state coverage*, not mechanism transparency, so it never trivializes the task.
- **Solvable-in-principle, not solvable-for-free** — identification is guaranteed; the effort is the difficulty. Longer chains, more distractor molecules, and tighter observation budgets make it harder — the difficulty dials. Guarding the guarantee: the injectable set must reach every skeleton node, and verification doubles as the check that a legal-instrumentation oracle recovers the answer.

## The harder variant (answer-first)

The pipeline above is the *simple* case: skeleton (world) first, questions second. Some richer questions instead require generating or tweaking the world *so a specific question is askable at all* — construct the answer, then build the world around it (e.g. "what's the pathway to produce **an interesting Z**?"). More expressive, more expensive; noted for later.

## Design decisions (resolutions to the open risks)

- **Skeleton-truth vs simulated-truth → verify-then-keep.** Resolved by pipeline step 4: never trust the skeleton in isolation — simulate control vs. intervention, confirm the answer holds, discard the world if not. *Residual:* rejection-sampling yield — if many worlds fail verification, generation gets expensive; worth measuring the discard rate.
- **Solvability → guaranteed by instrumentation.** Full observability (spectral probe) + interventional access (injection) makes every answer identifiable in principle; verification can also confirm a legal-instrumentation oracle recovers it. Difficulty = how much experimentation identification takes (chain length × distractors).
- **Grading → template-bound + structured answers.** Each template carries its own grader (cure → survives in the constructed homeostatic range; precursors → set match against the known skeleton). Force *structured* answers (a pathway = ordered node list; a diagnosis = the perturbed node) rather than free prose, and even "explain" items grade exactly.
- **Meta-contamination → minor (eval-only).** The benchmark is for evaluation, not training, so parameterized templates leak at most *format familiarity*, not answers (worlds are fresh each run). Downgraded from risk to mild bias; keep libraries parameterized anyway.
- **Knowledge-exposure → a dimension, not a flaw.** Full knowledge = deductive reasoning; partial = inference + experiment design; the *amount* of partial knowledge is a continuous axis worth sweeping.


# LOG

- 2026-07-07 — Captured the generation architecture. v1: question-first framing. v2 (this): rewritten around Dan's **skeleton-first** pipeline — compose skeleton from primitives → stochastic fleshing → project templated questions off the skeleton — plus the question-type catalog, the answer-first variant, and design risks.
