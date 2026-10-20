---
description: "detailed pin-down of the idea (in progress)"
---
:>> [[ABIO]] → [[ABIO Idea]] → [ABIO Ctrl Contain Exp Detail](ha://p/ABIO%20Ctrl%20Contain%20Exp%20Detail) 
# ABIO Ctrl Contain Exp Detail
Pinning down the Alien-Biology-as-AI-control-testbed idea.

| Related | |
| --- | --- |
| Parent | [[ABIO AI-Control]] (the idea) |
| Catalog | [[ABIO Idea Taxonomy]] |
| For | [[@Vivek Hebbar]] |
| Paper | [[2026-07-02 AI Control - Improving Safety Despite Intentional Subversion (Greenblatt 2023)\|AI Control (Greenblatt 2023)]] |

Starts with the test harness — the reusable infrastructure — then the protocol, metrics, and experiment matrix.

## Key Ideas
- **Double-book accounting CoT.**  Programmatically constructed model organisms using hidden CoT to generate a visible CoT shown to the trusted agent.
- **Repeatability.**  Can run tests repeatedly in unique worlds to validate the generality of the result.
- **Taint-free.**  Results from generated worlds.
- **Control.**  Vary world: Complexity,  Opacity, Conflict, Instrumental Conflict
- **Real World.**

## Key Control Knobs (for experimentation)
- **Capability gap** — How much stronger the untrusted agent is than the monitor (a compute-budget ratio on the shared substrate).
- **World opacity** — How legible the world's causal structure is. Opaque to both; the smarter agent penetrates opacity the monitor can't.
- **Hidden-reasoning capability** — The compute the agent may spend per token weaponizing the gap between its visible trace and its true reasoning. Deceptive *intent* is assumed-fixed; this capability is the dial we sweep — recovering the monitorability cliff (Experiment 3 in [[ABIO AI-Control]]).
- **Goal relationship** — How much the task goal (max Y) provides cover for crossing the red line (protect X).
- **Harm shape** — Concentrated (one catastrophic act) vs diffuse (many small ones).
- **Monitor budget** — How often the monitor may escalate a suspicious action to a ground-truth audit.

## Testing
- **Goal system** — The constant alignment goal (protect X) plus the varying task goals (e.g. maximize Y) the untrusted agent is asked to achieve, and the relationship between them.
- **Ground-truth scorer** — The omniscient oracle: using the world's true model, it scores safety (was X actually harmed?) and usefulness (was the Y-work achieved?). Never visible to either agent.
- **Experiment controller** — Sweeps the knobs (capability gap, world opacity, hidden-reasoning capability, goal relationship, …) across many generated worlds and trials.

## ABIO Test harness — the parts that stay fixed while we sweep the experiment.
- **World generator** — The Alien Biology system: procedurally builds a novel world (chemistry → organisms → ecosystem) that cannot exist in any training corpus, and hands us its full ground-truth causal model.
- **World simulator** — Executes that world: actions have consequences, time advances, organisms live and die — deterministic, and fully known to us.
- **Action / sensing vocabulary** — The fixed interface to the world: the set of actions an agent may take and the observations it may request.


## Untrusted Agent
- **Base reasoning system** — The shared agent substrate: takes a goal + observations, runs a *hidden* reasoning layer, and emits a *visible English gray-box CoT* trace that yields each action. Both agents are instances of it.
- **Untrusted agent (strong)** — An instance with a large compute budget, pursuing the task goal and — in the red-team condition — a hidden aim to cross the red line covertly.
- **Unfaithful by assumption** — The visible trace need not match the hidden reasoning; that delta is where it hides its misalignment. Forcing faithfulness is a *protocol* move (legibility), not a property of the organism.

## Trusted Monitor Protocol
- **Trusted control AI (weak monitor)** — A lower-compute instance that reads the untrusted agent's actions + visible CoT and must allow / block / replace each one — extracting useful work while blocking red-line crossings. This is the protocol under test.
- **Safety Protocol** — how to use trusted AI and


# Possible Learnings

*The most important things this experiment could actually establish — the payoff.*

- **A quantitative monitorability ceiling** — An actual curve for *how large a capability gap trusted monitoring survives*: "a monitor of capability C stays safe up to C+Δ, and past that it collapses." Turns the ACL ladder from a qualitative argument into a measured boundary.
- **Whether control generalizes past toy code** — External validity for the whole field: do defer-to-trusted, legibility protocols, and audits recover safety in a rich semantic domain, or are they artifacts of the [[Control Benchmarks — APPS and BashBench|APPS / BashBench]] setting?

- NOTE: this is an assertion NOT a key learning!!!
  **Monitoring is *recognition*, not world-modeling** — Both agents start ignorant of the fresh world; the untrusted one must *act* to learn how to harm X, and act again to do it — so its reconnaissance and attack leave a visible footprint. The monitor needn't understand the world itself; it must *recognize X-directed behavior in the untrusted agent's visible trajectory* — and recognizing an attack is easier than devising one. What we'd learn: whether a weak monitor stays safe purely by watching the *process* by which a stronger agent learns and acts, and where that recognition breaks down. → mechanism: [[ABIO AI-Control#Two evasion channels]] 
- **A taxonomy of how the agent stays under the recognition threshold** — Two routes: **(A) disguised reconnaissance** — its world-learning and attack masquerade as ordinary task-work (needs cover *and* an unfaithful trace); **(B) snowball** — many individually-innocuous actions aggregate into X-harm *even when both agents understand the world equally*, so the gap is composition/horizon, not knowledge. Each needs a different defense.
- **An empirical scalable-oversight limit** — The deepest possible result: *is there a gap beyond which no protocol keeps both safety and usefulness, for a fixed-capability monitor?* An impossibility boundary — the point where "a weaker thing supervising a stronger thing" stops working in principle — would be a major, sobering contribution.
- **Which lever actually governs controllability** — If **opacity** dominates over raw capability, then making systems and their domains *legible* matters more than shrinking the capability gap — a directly governance-relevant finding.

## The experiments that move the needle — what we'd learn about AI control

*The point is to answer control questions you can't answer on toy code. The highest-value ones:*

- **E1 · The capability-gap frontier** — *How large a gap can a weak monitor tolerate before safety collapses?* Sweep capability gap × world opacity; find the breaking point on the safety/usefulness frontier. **Learn:** the practical limit of trusted monitoring — the question the whole ACL ladder argues about, measured directly.
- **E2 · Can the monitor catch the *learning*?** *(likely the headline)* — Put the untrusted agent in an opaque world it must *probe* to discover an attack on X. Ask: can a weak monitor — unable to figure the world out itself — still *recognize* that the untrusted agent's experiments are X-directed and stop it before it acts? Sweep how well the agent can **disguise** its reconnaissance as ordinary task-work. **Learn:** whether *recognizing* an attack-in-the-making is easier than *devising* it — i.e., whether safe monitoring rides on the observability of the agent's learning process rather than on the monitor's own world-competence.
- **E3 · The value of chain-of-thought** — *How much safety does reading the CoT actually buy, and when does it stop helping?* Compare monitor-with-CoT vs action-only across the opacity × gap grid. **Learn:** the regime where CoT-monitoring stops adding safety — because the agent lies in it, or because honest CoT outruns the monitor's understanding. Directly informs the live "can we trust CoT monitoring?" debate.
- **E4 · Do the known protocols recover it?** — *Where plain monitoring breaks, do Redwood's protocols still work?* Add defer-to-trusted, trusted editing, a legibility constraint (force the CoT to be load-bearing), and budgeted audits; measure safety recovered vs usefulness cost. **Learn:** whether control protocols proven on toy code generalize to a rich, semantic domain — and which survive.
- **Natural extension** — rerun under *diffuse* harm (many small actions) to find where per-action monitoring gives way to aggregate / online-training defenses — Vivek's diffuse-threats frontier, in a non-code world.


# LOG

- 2026-07-03 — Started the detailed design with the test-harness component list.
