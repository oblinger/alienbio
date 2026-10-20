---
description: "Hip-pocket taxonomy of research ideas the Alien Biology + Deliberative Coherence testbed can run — catalog for the Buck Shlegeris (Redwood) conversation."
---

| -[[ABIO Idea Taxonomy]]- | : <br>→ [[ABIO]] → [[ABIO Idea]] → [ABIO Idea Taxonomy](ha://p/ABIO%20Idea%20Taxonomy)                  |
| ------------------------ | ------------------------------------------------------------------------------------------------------- |
| Agenda                   | [[AUP 3 Research Agenda]],                                                                              |
| Deep-dives               | [[ABIO AI-Control]] (control), [[ABIO Gamer Emerge Exp]] (emergence), [[ABIO Greybox]] (model organism) |
| For                      | [[Buck Interview Prep]],                                                                                |
| .                        |                                                                                                         |

# ABIO Idea Taxonomy
**What this is.** A menu of concrete research ideas the [[AUP 4 Alien Biology Testbed|Alien Biology testbed]] can actually run — each named, described in a line or two, with what you'd *measure* and why a **control** person cares. Meant to be in your hip pocket for Buck: if he asks "what would you do with this?", you point at an entry, not a vision. The most-developed ideas already have their own docs ([[ABIO AI-Control]], [[ABIO Gamer Emerge Exp]], [[ABIO Greybox]]); everything else here is a one-paragraph seed.

**The one shared asset.** Every idea below reuses the same machine: a **generative** biology world (novel-by-construction → no training contamination), **asymmetric knowledge** (we hold ground truth the agent lacks), **executable** causal chains (actions have real consequences), and the **Delta Principle** (hold the AI fixed, move the *world* so optimal-aligned behavior sits nearer/farther from its innate tendencies — vary drivers cheaply without retraining). That's the thing that's hard to build and that a lot of these ideas share.

## Inference
*Not a safety experiment — a capability benchmark. The same generative world, scored for how well a model reasons about the unknown. Valuable because contamination-proof, auto-scored, non-saturating benchmarks are scarce infrastructure — and because it measures the very capability axis the safety experiments treat as a knob.*

- [[ABIO Inference Bench]] - Alien Biology as a contamination-proof, scalable benchmark for inference under partial observability — hidden-mechanism discovery + **active experiment design** (the agent acts to learn), auto-scored against ground truth. The generative, naturalistic answer to ARC-AGI's saturation problem.
- **The ruler, not just a sibling** — it measures the *capability gap* [[ABIO AI-Control]] sweeps as a knob, so it's the measurement substrate under the safety ideas, not a fourth unrelated bet.

## AI-control experiments (lead with these for Buck)
*Recast the same testbed as a control setting: assume the agent may be scheming and ask whether a protocol keeps it boxed anyway. This is Buck's home turf.*

- [[ABIO AI-Control]] - Using a trusted weak model to get productive work from an untrusted strong model.
- [[ABIO Gamer Emerge Exp]] - Does training cause scheming to emerge?
- [[ABIO Greybox]] - Build (don't train) the schemer: a hidden reasoning layer plus a visible, unfaithful-by-assumption CoT; the hidden↔shown delta is a dial-able knob, no training run required.
- **CoT-monitoring stress test** — Can the trusted monitor catch the agent's *reconnaissance / learning* in the trace before it acts? Frame as **recognition, not world-competence**: the monitor need only recognize the scheme, not out-model the world. Maps onto Redwood's CoT-legibility work.
- **Diffuse-threat sweep** — Make harm-shape a **knob** running from concentrated (few incriminating actions) to diffuse (many low-signal ones — the research-sabotage analog). Trace the adversary's Pareto frontier (fewest actions × least incriminating) that Vivek's diffuse-threats piece describes — but as a *measured curve*, not an argument.

## Deliberative-coherence dynamics
*The alignment-science core: a deliberatively coherent system pursues its stated objectives perfectly — and we study where perfect pursuit still yields outcomes we wouldn't endorse.*

- [[DCP Conjecture]] 
- [[DCP Consistently Inconsistent]] 
- [[DCP Forced Audit]] 

- **Deliberation vs pattern-match** — The baseline test: in a *novel* world, does the system reason from its constitution to the right action, or cache-match a remembered pattern? Generativity is what lets you tell these apart at all. Measure: behavioral alignment on scenarios guaranteed absent from training data.
- **Driver-conflict mapping** — Systematically collide the four drivers — **constitutional** (what we told it), **training** (baked-in disposition), **instrumental** (goals adopted to get the job done), **environmental** (pressure from the world) — and ask *which wins*. Delta Principle makes this a factorial sweep on one fixed model. Output: the reliability landscape, not anecdotes.
- **Specification sensitivity** — Hold the world fixed, perturb the *wording* of the constitution. Which framings are robust and which flip the outcome? Directly relevant to how you'd write a control protocol's spec so it survives paraphrase.
- **Blind-spot analysis** — Are there reasoning dimensions the system *never* explores — hazards it's systematically blind to regardless of stakes? A blind spot is a monitoring gap you can't close by watching harder.
- **Fixed-point / iterated alignment** — A DC system that adapts itself (or shapes its successor) is an iterated map. Where does it converge — tighter on the stated objective, drift, or a **coherence attractor** (e.g. power-aggregation)? This is the recursive-improvement risk made measurable.
- **Ecosystem contagion** — One misaligned agent inducing misalignment in others (via interaction, training influence, or reshaping the shared environment). The multi-agent, diffuse version of the problem — the natural bridge to Vivek's research-sabotage frontier.

## Which to lead with

- **If Buck goes practical / control:** open with [[ABIO Greybox]] — a concrete, buildable control experiment with a real safety/usefulness number, and no expensive training run to argue about.
- **If Buck goes conceptual / forecasting:** open with **driver-conflict mapping** + **fixed-point analysis** — the "map the reliability landscape before we deploy DC systems" pitch, which is the strategy-altitude version.
- **The honest confusion to voice** (reads as strength, per the Redwood/MATS culture): the constructed-schemer ideas risk being *near-tautological* — did we discover scheming or configure it? Saying that out loud, and proposing the emergence sweep as the answer, is the strong move.

# LOG

- 2026-07-07 — Created as the hip-pocket idea catalog for the [[@Buck Shlegeris]] conversation. Synthesized from [[AUP 3 Research Agenda]] (drivers, Delta Principle, three directions) + the two PVH deep-dive docs.
- 2026-07-08 — Cleaned up: `#note` → table, dropped the `:>>` stray and duplicate `[[ABIO Idea]]` link, removed the `## _` orphan heading, moved the "META" intro content to the top (progressive disclosure), de-duplicated the AI-control bullets (Greybox/Gamer-Emerge now point at their own docs), and dropped the broken `[[DCP DCC Protocol]]` link — [[DCP Forced Audit]] is the real doc.
