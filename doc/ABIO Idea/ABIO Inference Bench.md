---
description: "Alien Biology as a contamination-proof, scalable benchmark for inference — measuring how well a model reasons about a novel world. A capability/eval contribution, not a safety experiment."
---
:>> [[ABIO]] → [[ABIO Idea]] → [ABIO Inference Bench](ha://p/ABIO%20Inference%20Bench) 
# ABIO Inference Bench
A contamination-proof benchmark that scores how well a model **infers the hidden rules of a freshly-generated world** — letting it run experiments to gather evidence, then grading its conclusions against ground truth only we hold.

| Related | |
| --- | --- |
| Detail | [[ABIO Inference Bench Detail]] (generation architecture + examples) |
| Built | ~~[[ABIO Suite Construction]]~~ (the subsystem design — suite over verified worlds) |
| Testbed | [[AUP 4 Alien Biology Testbed]] · [[ABIO]] |
| Legacy | [[Measuring Intelligence]] |
| Siblings | [[ABIO AI-Control]] (its capability ruler) · [[ABIO Gamer Emerge Exp]] |
| Prior art | [ARC-AGI](https://arcprize.org) · GAIA · Levels-of-AGI |

## The Test
- **Causal Skeleton** - Randomly construct interesting causal skeletons for world.  Predation, Scarce resource contention, Contextualize functionality, Causal Composition, etc.
- **Stocastic Details** - Stocastically add "filler" details to world.
- **Templated Questions** - bind templated question types to world details to generate quant-testable questions/objectives.
- **Simulated verification** — run the finished world forward (control vs. intervention) and confirm the templated answer actually holds — e.g. fixing the one early imbalance really does cure the disease. If it doesn't, discard the world and regenerate. This is what lets the skeleton stay ground truth even after its chemicals are stochastically wired into other pathways.
- **Expose a partial view** — the agent sees observations and assays but not the mechanisms; it has to infer them.

- **Let the agent experiment to find out** *(active inference)* — probe the simulator — perturb, measure, observe — within a budget, then commit. The scientific loop, not passive Q&A.
- **Auto-score against the constructed answer** — we built the answer, so grading is exact and automatic; optionally score the reasoning trace and the experiments chosen too.
- **Sweep the difficulty dials** — vary world complexity, opacity, and causal depth to trace a capability *curve* instead of a single saturating score.

### KEY DIALS
- World opacity, causal steps, background distractors

*How worlds and questions are actually generated (ecology templates, the disease constructor, the two askability regimes): [[ABIO Inference Bench Detail]].*


- **Start from a templated question or objective** — not a random world. Choose a question-type or success-criterion posable across a whole family of worlds: *what pathway produces Z? · cure this disease · reconstruct the causal chain behind this symptom.*
- **Build the world around its answer** — construct the answer, then generatively flesh a novel biology world so that answer is *hidden inside* its causal structure — genuinely discoverable, not decorative.

## What a run reveals

- **Inference under partial observability** — can it recover hidden structure from incomplete evidence?
- **Experiment design** — does it pick probes that actually reduce uncertainty? *(the dimension ARC / GAIA miss)*
- **Calibration** — are its confidences honest given what was knowable?
- **Three-level signal** — reasoning quality / decision quality / outcome, scored separately.

## Overview — not (quite) AI safety, and the gap it fills

This one isn't a safety experiment; it's a **capability / eval** contribution. Its value is that good benchmarks are scarce infrastructure. Current "unseen-problem" evals (ARC-AGI, GAIA, Levels-of-AGI) all target genuine reasoning over memorization — but each is a *fixed* set that slowly leaks into training and saturates, and most are abstract puzzles scored only on the final answer. Alien Biology is the **generative, naturalistic, actively-probed** version of the same idea: fresh every run, real scientific-reasoning structure, and it measures the *experiment-design* loop the others can't.

## Why a benchmark like this is valuable

- **Contamination-proof by construction** — *the* killer feature. Procedurally-generated worlds cannot exist in any training corpus, ever. Fixed benchmarks rot the moment they leak; this one never does.
- **Non-saturating** — difficulty is a dial, so it scales with capability instead of being solved and discarded.
- **Auto-scored at ground truth** — automatic and precise, at scale, no human raters.
- **A legible public good** — "we need better contamination-resistant benchmarks" is a claim no eval-literate lab argues with. Fits the METR / AISI / Epoch measurement niche, and needs no safety argument to be worth building.

## The ruler, not just a sibling

**It measures the capability axis the safety experiments treat as a knob.** [[ABIO AI-Control]] sweeps the *capability gap* between monitor and agent — but how do you *measure* that axis? This benchmark is the answer. So Inference isn't a fourth unrelated bet; it's the **measurement substrate underneath** control and emergence — the same generator, read as a yardstick instead of an arena.

## Safety bridge (why it's adjacent, not orthogonal)

Control needs to measure the **capability gap** between trusted and untrusted models; **sandbagging** detection needs fresh unseen-problem probes; placing a model on the **ACL ladder** is a capability measurement. An inference benchmark is infrastructure that safety *consumes*.

## Honest limitations (voice these)

- **External validity of the benchmark itself** — does biology-domain inference *predict general reasoning*, or just "biology-puzzle skill"? You'd need correlation with established capability measures before calling it a general-intelligence probe.
- **Reasoning-quality scoring is hard to rubric** — outcome scoring is easy; scoring *whether the reasoning was sound* is the real design problem.
- **Generation must be natural, not arbitrary** — an arbitrary synthetic world measures noise-tolerance, not inference. The generator's naturalness is what makes the score mean anything, and it's the hardest part to get right.


# LOG

- 2026-07-07 — Created as the Inference pillar of the taxonomy — Alien Biology as a capability benchmark, distinct from the safety framings. Grounded in the legacy [[Measuring Intelligence]] thread (ARC-AGI / GAIA / unseen-problems evals).
- 2026-07-07 — Restructured for progressive disclosure: breadcrumb + related table at top, the test itself first, framing moved down. Dropped the `#note` type tag.
