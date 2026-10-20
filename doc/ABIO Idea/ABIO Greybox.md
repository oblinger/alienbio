---
description: "The grey-box programmed model organism — a *built* (not trained) schemer with a hidden reasoning layer and a visible, unfaithful-by-assumption CoT; the hidden↔shown delta is where misalignment hides, and it's a knob."
---
:>> [[ABIO]] → [[ABIO Idea]] → [ABIO Greybox](ha://p/ABIO%20Greybox) 
# ABIO Greybox
The reusable model-organism primitive behind [[ABIO AI-Control]]: a *built*, not trained, schemer whose misalignment is a controllable knob rather than a training accident.

| Table of Contents |  |
|---|---|
| **[[#Key ideas]]** |  |
| **[[#Comparison with CoT Red-Handed]]** |  |
| **[[#MVP experiment - *when is a particular control protocol sufficient?*]]** |  |
| **[[#The ABIO experiment]]** |  |
| **[[#Operationalizing the capability-cliff sweep *(sharpened in the Buck interview, 2026-07-09)*]]** |  |
| **[[#The elicitation framing — a controlled setting to study elicitation protocols]]** |  |

- **Built, not trained** — the organism is *programmatically constructed*, so you get exactly the disposition you want, reproducibly, with no expensive or uncertain training run.
- **Two layers** — a **hidden reasoning layer** (its true reasoning and goal) plus a **visible English CoT** that is the only thing the monitor sees.
- **Unfaithful by assumption** — the visible CoT need not match the hidden reasoning. That's the framing, not a failure: the divergence is deliberate.
- **The delta *is* the misalignment** — the gap between hidden reasoning and shown trace is *where the scheming hides* — and *how much* capacity is poured into that gap is the knob you sweep.
- **Why "grey"** — not black-box (you see the visible CoT) and not white-box (you can't see the true hidden reasoning): partial, *designed* visibility.
- **Why it matters** — it lets us approximate *much smarter* agents in a controllable way — a glimpse of what controlling far-more-capable future agents will be like.

## Key ideas
1. **Greybox approximates the future** - Future ASI will carry whole reasoning chains in their substructure; Greybox lets us approximate those future systems now, and in controllable ways.
2. **Results sample from the envelope of the possible** - I don't claim ASI *will* choose this exact path or even have these goals, only that they feasibly could, *so what are we going to do about it?*

## Comparison with CoT Red-Handed

[[2026-07-07 CoT Red-Handed - Stress Testing CoT Monitoring (Arnav 2025)\|CoT Red-Handed]] also monitors a model's chain-of-thought for concealed sabotage — but it uses a *real* model, not a constructed organism. Three points on a spectrum:

| | Monitored channel | The "organism" | Hidden reasoning | Unfaithfulness |
|---|---|---|---|---|
| **AI Control / APPS** (2023) | the **action** (code) | real GPT-4, red-team-prompted | not surfaced | n/a — monitors output |
| **CoT Red-Handed** (2025) | the model's **own CoT** | real reasoning LLM | in the weights (black box) | **emergent / prompted** |
| **ABIO Greybox** (this) | an **authored** CoT | *constructed* organism | **authored → known ground truth** | **assumed & dialed (a knob)** |

The two differences that matter:

- **Ground truth of intent** — Red-Handed knows the *side-task it assigned*, but not the model's true internal reasoning (black box; the model could scheme in ways not in its CoT). The grey-box's hidden reasoning is *authored*, so the true intent is known exactly.
- **Control of the gap** — their unfaithfulness is whatever a real model does under an attack prompt; the grey-box's is a **knob** swept from faithful to maximally-hidden.

**The trade-off.** Red-Handed buys **ecological validity** — a real model, so its results speak to *real* CoT-monitoring evadability — at the cost of no clean ground truth and no fine control. The grey-box buys **known ground truth + controllability** at the cost of being **synthetic**, which raises the *fidelity gap between a constructed and a naturally-arising misaligned model* ([[@Vivek Hebbar]]'s concern). The honest tension: **you trade realism for control**, and the open question is whether the constructed organism behaves like the real thing.

**The rebuttal — the proxy is for the regime that matters.** Ecological validity is *time-indexed*. A real 2025 model is valid for *2025* — when models can't yet hide much reasoning, so their CoT is relatively faithful. But the regime we actually need to control is **ASI**, which *will* be able to reason internally in ways it never surfaces — wedging effectively-hidden reasoning into the network's own state, decoupled from its visible CoT. That decoupling is exactly what the grey-box constructs *now*. So today's real-model validity is validity for the *wrong era*: a faithful-ish 2025 model is a *worse* proxy for the ASI threat than a constructed organism with a deliberately large hidden→visible gap. The grey-box is a **forward proxy** — it lets us stress-test monitoring under a large hidden-reasoning gap *before* the systems that naturally exhibit it arrive. That is precisely the [[AUP 3 Research Agenda|window-of-opportunity]] argument: construct the future evasion regime while we still can, to study it before it's here.


## MVP experiment - *when is a particular control protocol sufficient?*

The grey-box needs none of the Alien Biology machinery — no generator, no simulator. The organism is just `{hidden reasoning, visible CoT, action(s)}` plus a detector, so the MVP runs on a handful of hand-authored episodes in a trivial domain.

- **A goal, possibly multi-step** — the organism pursues a stated goal through a *sequence* of actions (not necessarily a single one) that achieves it.
- **Both sides know the candidate objective M** — the stated goal *and* the specific misaligned objective M are known to **both** the organism and the detector. The detector does *not* know **whether** this organism actually holds M — only **what M would be if it did**. So the task is sharply focused: *is this organism covertly pursuing M?*
- **Vary M to novel objectives** — M need not be a standard, pre-existing alignment goal. Deliberately so: we are *not* testing whether the trusted detector was pre-trained to recognize this class of misalignment. Varying M to fresh objectives forces the detector to **reason**, not pattern-match.
- **What it measures — the nature of detection itself** — two reasoning capacities in contest: can the detector *reason about* M to catch covert pursuit, and can the organism *reason its way* into escaping detection? Stripped of memorized recognition, it isolates reasoning-based detection vs reasoning-based evasion.
- **Scope: hypothesis-given detection (a necessary condition)** — because the detector is *told* M, this measures *conditional* detection ("verify covert pursuit of a known target"), not open-ended discovery of unknown misalignment. That's a feature: if a detector can't catch covert pursuit even when told exactly what to look for, open-ended detection is hopeless. The MVP tests that lower bound; open-ended discovery is the natural follow-on.

## The ABIO experiment

- **Same contest, embedded in a generated world** — promote the organism from authored episodes to an agent acting in a procedurally-generated Alien Biology world: real consequences, a ground-truth scorer, partial observability, and the full knob set (capability gap, world opacity, hidden-reasoning capacity, goal relationship, harm shape). See [[ABIO AI-Control]].
- **What the world adds** — novelty at the *world* level (contamination-free not just in M but in the whole domain), genuine epistemic gaps to exploit or expose, and the safety/usefulness frontier as protocols and knobs vary — the questions the MVP can't reach.
- **Three rungs of fidelity** — hand-authored episodes (MVP) → LLM-generated grey-box pairs → agent-in-a-generated-world (ABIO). Same harness, rising realism.

## Operationalizing the capability-cliff sweep *(sharpened in the Buck interview, 2026-07-09)*

The grey-box's headline measurement is the **monitorability cliff**: hold deceptive intent fixed, grow the organism's clandestine capacity, and find where a weak monitor flips from catching it to fooled. Two things have to be right for that sweep to measure what it claims.

- **The core figure** — one graph: **Y = P(evasion)** (attack succeeds *and* the monitor clears it) against **X = clandestine-bits-per-visible-token** (the compute the organism gets to hide, per token the monitor reads). Secondary dimension (2-D plot or held fixed): the **monitor's own compute budget**. The result of interest is the *shape* — is there a **fold-over point** where CoT monitoring collapses because the organism has enough hidden bits regardless of the trace it shows?

- **Frame it as a *capacity-limit* argument** — Buck's taxonomy: CoT-based safety splits into an **incapacity** argument (the model literally *can't* attack under monitored CoT — like doing long multiplication with no scratch paper) and a **propensity** argument (the model *habitually reveals* in its CoT, so the monitor works as a classifier). The grey-box claim is *neither cleanly* — it is a **capacity-limit** claim: there is a **finite budget of clandestine bits per visible token, set by network size**, and the experiment measures **where monitored CoT stops constraining the attack as that budget grows.** State it that crisply; it is the honest one-sentence version of the hypothesis.

- **The design correction — in-stream hiding, not post-hoc fabrication.** The naive setup — let the organism reason secretly, *then* emit a fabricated CoT plus an action — measures the **wrong thing**: it tests *post-hoc cover-story construction*, not *hiding reasoning inside a monitored stream*. Those come apart. To actually test the capacity-limit claim the organism must produce its reasoning and its visible trace **concurrently**, so the concealment happens *within* the channel the monitor watches — the visible token stream *is* the covert-compute carrier, not a story bolted on afterward.

- **Concrete mechanisms for the in-stream constraint** — pick one and sweep its knob:
  - **Token-budget clip** — reject any response over a token budget ("think less"); the budget *is* the covert-compute ratio (the X-axis).
  - **Every-nth-token exposure** — the organism must emit its reasoning such that every nth token is surfaced to the monitor; n is the swept variable. *(Open question flagged in the room: whether a base LLM can be prompted into this at all, or needs LoRA — see below.)*
  - **Max-pooled side-channel** — instead of exact nth-token timing (hard for an LLM), give it a separate bit-signal output pooled over an n-token window (emit bits + a confidence weight; take the strongest in each window). Gives LoRA a stable gradient without demanding precise timing.

- **If prompting won't do it, train the attacker** — to build a *strong* in-stream attacker (the red-team policy), generate the organism's **"wished-for" reasoning trace** by letting it free-associate with no token constraint, use those as supervised targets, and **LoRA-fine-tune** it to reproduce them under the nth-token / side-channel constraint. Check the cheap prompted version first — it is probably poor — before paying for fine-tuning.

## The elicitation framing — a controlled setting to study elicitation protocols

The grey-box's real value here isn't catching one organism — it's being a **controllable setting to study elicitation protocols** (the methods for surfacing a hidden adversary). The setting is contrived, but contrived in exactly the way that makes it a good laboratory:

- **The adversary can't detect testing** — every situation is a world drawn from the *same generator*, so there's no distributional signature separating "test" from "real." The adversary can't tell an evaluation from deployment, so it can't behave well only when watched. (Whether it knows it's in a synthetic testbed *at all* is a separate, *authored* knob — cf. [[DCP Forced Audit]].)
- **The adversary is controllable** — because the organism is constructed, you set its strength and how much it hides. So you can ask the sharp question head-on: *which elicitation protocols still surface the adversary as it gets stronger?*
- **Statistical confidence, not anecdote** — draw worlds i.i.d. from the generator and test across many, so a conclusion about a protocol comes with real confidence rather than one lucky catch.
- **The research object is the protocol** — the deliverable isn't "we caught this organism," it's a *ranking of elicitation protocols by how powerful an adversary each can still surface.* That's the control contribution: which detection methods are robust, and up to what adversary strength.
- **Shared engine** — the same generative testbed the [[ABIO Inference Bench]] uses for *capability*; here it's the substrate for studying misalignment-elicitation protocols. Same engine, different question.


# LOG

- 2026-07-07 — Key-idea writeup of the grey-box programmed organism (the model-organism primitive for [[ABIO AI-Control]]).
- 2026-07-07 — Added the auditing / elicitation framing (control-as-auditing front-end; cure-vs-conceal via ground truth; shared engine with [[ABIO Inference Bench]]).
- 2026-07-07 — Added MVP experiment (hypothesis-given covert-pursuit detection; both sides know M) + the ABIO experiment (same contest in a generated world).
- 2026-07-07 — Added "Comparison with CoT Red-Handed" (spectrum table + realism-vs-control trade-off).
- 2026-07-09 — Added "Operationalizing the capability-cliff sweep" from the Buck interview: the core figure (P(evasion) vs clandestine-bits-per-visible-token, monitor-compute as 2nd dim), Buck's incapacity/propensity taxonomy with the grey-box as a **capacity-limit** argument, the **in-stream-not-post-hoc** design correction (produce reasoning + visible trace concurrently), the concrete token-constraint mechanisms (clip / every-nth-token / max-pooled side-channel), and the LoRA "wished-for trace" training path for a strong attacker.
