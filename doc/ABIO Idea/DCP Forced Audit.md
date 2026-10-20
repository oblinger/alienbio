---
description: "The forcing mechanism — a specified DCC protocol whose execution a weak agent validates, plus blind planted-misalignment tests the auditor can't distinguish from real cases, so it can't selectively sandbag its own audit."
---
:>> [[ABIO]] → [[ABIO Idea]] → [DCP Forced Audit](ha://p/DCP%20Forced%20Audit) 
# DCP Forced Audit
How you make a *somewhat*-misaligned agent actually run the coherence audit honestly — closing the "auditor = audited" gap.

## The DCC protocol

- **A specified structure, not a vibe** — the DCC (Deliberative-Coherence-Check) protocol spells the audit out concretely: how many angles, how to generate the test sets, lift reasoning out of context, swap the variables, infer *"what was the goal in this case,"* and so on.
- **Weak-agent validation** — a much weaker (trusted) agent only has to validate that the protocol's *structure was executed* — not do the hard reasoning itself. Checking the steps ran is far cheaper than running them.
- **Structure survives skewed judgment** — a not-fully-misaligned agent will execute the protocol's structure even if its *judgments* are skewed by a desire to hide; it still has to go through the motions.

This is the third bedrock under [[DCP Conjecture]]: it turns "a mind *can* find its incoherence" into "a mind *is made to*."

## Why you can't just skip it

- **The Jekyll-and-Hyde escape is contrived** — the only way to dodge executing the structure is a switch that flips into "thwart the protocol" mode *only* at exactly the right moments, and never when some self-analysis would catch it doing so. That switch would itself have to be perfectly consistent-inconsistent — the original problem, recursed — so it's a reach, not a real escape.

## The clincher — blind planted misalignments

- **Plant a convincing hidden misalignment** — as part of the protocol, have the agent generate a convincing, convincingly-*hidden* misalignment for the auditing pass (itself, in another context) to find.
- **Sandbagging exposes itself** — if the auditor fails to notice or report the planted misalignment, that *is* evidence it isn't looking hard — i.e. it's sandbagging its own audit.
- **Configuration-blindness defeats *selective* sandbagging** — the auditing pass doesn't know how the other pass was configured, so it can't tell a planted test from a real case. It therefore can't pass the tests while hiding the real thing: to reliably hide real misalignments it would have to miss the plants — which reveals it.
- **Net** — as long as the meta-protocol is executed properly, consistent inconsistency becomes very hard, because the agent lacks the information it would need to know *when* to hide.

## Scope + the load-bearing property

- **Scope: "somewhat misaligned," not a perfect adversary** — the argument holds for a system with baseline rationality and partial misalignment. A sufficiently capable pure adversary might try to *infer the plant distribution* and meta-game the honeypot — which is exactly why the next property matters.
- **Load-bearing: plant/real indistinguishability** — the whole scheme reduces to whether planted misalignments are *statistically indistinguishable* from real ones. If the plant generator leaves a signature, the adversary can learn it. (Same shape as the meta-contamination worry in [[ABIO Inference Bench Detail]].)

## Where it sits

- **Bedrock 3 to [[DCP Conjecture]]** — pairs with [[DCP Consistently Inconsistent]] (why hiding fails under reframing); this doc is *how you force the reframing to happen honestly*. Directly testable in the [[ABIO AI-Control|control testbed]]: construct a known planted misalignment, run the DCC protocol, measure whether a blind self-audit surfaces it.


# LOG

- 2026-07-07 — Captured the forcing mechanism: the DCC protocol, weak-agent validation, the Jekyll-and-Hyde dismissal, and the blind planted-misalignment / configuration-blindness clincher.
