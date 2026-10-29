---
description: "the demonstration suite: eight sequential tutorial demos and three combination experiments"
---

| -[ABIO Demos](ABIO%20Demos.md)- | : the demonstration suite: eight sequential tutorial demos and three combination experiments<br>→ [ABIO](../ABIO.md) → [ABIO Demos](ha://p/ABIO%20Demos) |
| ------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Demos                           | [Gallery](ABIO%20Demo%20Gallery.md),                                                                                                                     |
| ...                             |                                                                                                                                                          |

# ABIO Demos
The M1-era demonstration suite (Milestone 20), kept as history: its runtime, its scripts and the `bio.sim()` pipeline below were deleted in M47.7 and T056 (2026-09-10). What remains is in the [Demo Gallery](ABIO%20Demo%20Gallery.md); the runnable examples today are under `catalog/examples/`.

Eight focused demos form a sequential tutorial covering the full system, plus three combination demos showing realistic multi-feature experiments.

All demos used the M1 pipeline: YAML spec (M18) → rate compilation (M16) → `bio.sim()` → fetch/store (M17), with scenarios generated from templates (M19).

---

## Focused Demos (Tutorial Sequence)

**01 — Quick Start** — From YAML to simulation in 10 lines. Define a scenario, compile it, run it, store the results. The complete pipeline in one workflow.

**02 — Equilibrium & Stability** — How alien biochemistry self-regulates. Run a homeostatic system to convergence, analyze stability with variance tracking.

**03 — Perturbation & Recovery** — What happens when you poke it? Concentration spikes recover; structural damage causes drift.

**04 — Disease Investigation** — Alien diseases from symptoms to diagnosis to cure. Measure baselines, detect symptoms, run diagnostic and curative agents.

**05 — Multi-Compartment Organisms** — Real organisms have structure. Generate complex organisms from templates with build guards, simulate inter-compartment transport.

**06 — Life & Survival** — Life has rules. Operating envelopes, predator/prey dynamics, reproduction thresholds, and viability checking.

**07 — Generating & Skinning** — Making biology alien. Generate scenario variants from templates, skin with opaque alien names, produce descriptions at multiple detail levels.

**08 — Agent Evaluation** — How good is your agent? Difficulty scaling, multi-agent comparison, capability thresholds, and leaderboards.

---

## Combination Demos

**Combo A — Full Disease Investigation** — The complete pipeline: generate a multi-compartment organism from templates, run to equilibrium, apply disease, detect symptoms, diagnose with competing agents, cure, verify recovery.

**Combo B — The Alien Biology Exam** — The core use case: generate biology from specs, skin it with alien names, scale difficulty, run an agent battery on opaque tasks, produce a leaderboard. Can an AI reason about unfamiliar biology?

**Combo C — Ecosystem Under Stress** — Survival under pressure: multi-compartment ecosystem with predation and operating envelopes, hit with environmental stress, monitor population dynamics and viability through recovery.

---

## Optional

**LLM Agent Demo** — Run Claude on a skinned diagnosis task and compare against oracle and random baselines. It needed `ANTHROPIC_API_KEY`; the live-model agent today is `suite.llm_agent`.
