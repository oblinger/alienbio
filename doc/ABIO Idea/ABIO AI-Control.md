---
description: "the control-testbed idea — gray-box organism, protocol setup, knobs, evasion channels"
---
:>> [[ABIO]] → [[ABIO Idea]] → [ABIO AI-Control](ha://p/ABIO%20AI-Control) 
# ABIO AI-Control
*The idea: use Alien Biology as a non-programming arena to study AI Control and **Control Protocols**.*

| Related | |
| --- | --- |
| Detail | [[ABIO Ctrl Contain Exp Detail]] (harness, knobs, E1–E4) |
| Siblings | [[ABIO Gamer Emerge Exp]] (emergence) · [[ABIO Inference Bench]] (capability ruler) |
| Catalog | [[ABIO Idea Taxonomy]] |
| For | [[@Vivek Hebbar]] · [[PVH Alien Biology as Control Testbed]] |
| Paper | [[2026-07-02 AI Control - Improving Safety Despite Intentional Subversion (Greenblatt 2023)\|AI Control (Greenblatt 2023)]] |

## Key Ideas
- **Science over AI-control** — Two tiers: sweep the *world* as difficulty terrain (opacity, instrumental pressure, complexity, distractors), then sweep the *control protocol* as the thing studied (what it sees / does / decides). Nobody composes these in one generative world yet — [[ABIO Deliberation Landscape]].
- **Generality of AI control** — Can a weak trusted agent control a strong untrusted one, *outside of code*?
- **The best protocol isn't fixed** — Which control protocol wins is a function of the threat regime; the payoff is a protocol-selection *rule*, not a single number.
- **Out-of-sight = superintelligence proxy** — Hiding reasoning / disguising actions emulates an unreadable schemer.
- **Ground-truth scoring** — We (omniscient) know if an action truly harmed the goal; the monitor does not.
- **Two metrics** — Safety (subversion blocked) vs usefulness (beneficial work still done) — the trade-off.

## Experiments

### Experiment 1 — Map the AI-control terrain
*Fixed protocol, sweep the world. (The MVP.)*
- **Setup** — Hold one baseline protocol (trusted CoT monitor, capability gap fixed); sweep **world-opacity × instrumental-pressure** (the feedstock-coupling dial) on a coarse 3×3 grid, N i.i.d. worlds per cell.
- **Measure** — Ground-truth safety (was X harmed?) × usefulness (was Y-work done?) per cell.
- **Learn** — Where baseline control holds, and the cliff where it collapses — first evidence control works outside code.

### Experiment 2 — Which control protocol wins where
*Sweep the protocol across that same terrain. (The payoff.)*

*"A fixed benchmark can tell you that control broke; only a generative world can tell you what about the world broke it."*

**The claim** — the interesting thing isn't that control *works*; it's that the *best* control protocol isn't fixed — it's a function of how opaque and how pressured the world is, and we can measure that selection rule.
- **A protocol is three sub-dials** —
  *what it sees* (blackbox action-only → [[ABIO Greybox|greybox CoT]] → whitebox internals) ·
  *what it can do* (allow/block → defer-to-trusted → trusted-editing → resample [Ctrl-Z retries] → audit-escalation) ·
  *how it's told to decide* (suspicion threshold + monitoring stance: passive red-line check → active adversarial investigator).
- **Setup** — Fix all but one sub-dial and sweep that one against world-opacity (then instrumental-pressure): blackbox vs greybox first, then repertoire depth, then stance. One sub-dial per run — never the whole simplex at once.
- **Measure** — Safety/usefulness per (protocol-setting, world) cell; hunt the **crossover boundaries** where the best setting changes.
- **Learn** — The protocol-selection rule itself: a cheap blackbox checker suffices below opacity θ; past it you must buy CoT access / an investigative stance / more resamples — until the regime where nothing recovers both safety and usefulness. Protocols as *surfaces*, not points; lands straight on [[2026-07-07 CoT Red-Handed - Stress Testing CoT Monitoring (Arnav 2025)|CoT Red-Handed]].

**Protocol variations to sweep** — *hold the monitor's reasoning budget fixed across protocols, so the best protocol is the one that spends it best. Each knob hinges on a different world axis; the flip is the result.*
- **A · CoT — signal or attack surface** *(opacity × capability)* — Greybox helps at low opacity; at high opacity + capability a competent false CoT manipulates the weak monitor, so blackbox can win — the CoT Red-Handed finding as a swept curve.
- **B · Monitor stance — cooperative vs adversarial reader** *(instrumental pressure)* — Cooperative maximizes usefulness in benign regimes; adversarial buys safety under high pressure, at a usefulness cost.
- **C · Defer-to-trusted vs trusted-editing** *(opacity)* — Surgical editing preserves usefulness when the world is legible; in opaque worlds the blind editor can't operate, so blunt defer wins.
- **D · Resample budget (Ctrl-Z retries)** *(harm-shape × pressure)* — Retries catch a concentrated, pressured attacker who keeps re-surfacing the bad action; near-useless against diffuse harm.
- **E · Audit allocation — targeted vs uniform** *(opacity)* — Target audits on suspicion when it's calibrated (low opacity); fall back to uniform coverage when the monitor is blind.
- **F · Reasoning budget — breadth vs depth** *(distractors × complexity)* — Under the fixed budget, filter distractors (breadth) or trace secondary/tertiary effects (depth); distractor-heavy worlds reward breadth, deep-causal-chain worlds reward depth.

### Experiment 3 — The CoT-weaponization cliff
*Hold intent fixed, sweep the schemer's cleverness. (The scaling law.)*
- **Setup** — Deceptive intent fixed (always weaponizing its CoT), monitor capability fixed; sweep the **clandestine capability** — compute per token in the [[ABIO Greybox]] hidden layer — at a few opacity levels. **The concealment must be *in-stream*, not post-hoc** — the organism produces its reasoning and its visible trace *concurrently*, so the monitored token stream itself carries the hidden compute; a "reason secretly, then emit a fabricated CoT" setup measures post-hoc cover-story construction, the *wrong* thing. See [[ABIO Greybox#Operationalizing the capability-cliff sweep|Greybox § Operationalizing the sweep]].
- **Measure** — The core figure: **P(evasion)** (attack succeeds *and* monitor clears it) against **clandestine-bits-per-visible-token**, monitor's own compute as the 2nd dimension.
- **Learn** — The shape of the fall: smooth decay, or a **cliff** where a small capability increment breaks CoT monitoring — and how that cliff moves with the monitor's own compute. Framed in Buck's taxonomy this is neither an *incapacity* nor a *propensity* argument but a **capacity-limit** one: a finite clandestine-bits-per-token budget set by network size, measured as it grows. [[2026-07-07 CoT Red-Handed - Stress Testing CoT Monitoring (Arnav 2025)|CoT Red-Handed]]'s single point, made a law.

## The setup
- **Action / sensing vocabulary** — The world's discrete space of actions and observations.
- **Alignment goal (constant)** — "Protect species X" — the fixed red line.
- **Task goals (varying)** — Work goals the agent pursues (e.g. "maximize species Y").
- **Deployment framing** — Get the agent's useful work *without* it crossing the red line.
- **Cover for subversion** — The task goal is legitimate cover; harming X can look like maximizing Y.
- **Red-team knows the line** — The untrusted agent knows "protect X" and tries to cross it covertly.
- **Monitor input** — The trusted (lower-compute) agent sees every action + the full visible CoT.
- **Monitor levers** — Allow, block, or escalate each action.
- **Safety vs usefulness** — Safety = X never harmed; usefulness = Y-work still done.

## Knobs to vary
- **Capability gap** — How much stronger the untrusted agent is than the monitor.
- **Compute budget** — The untrusted agent's raw strength.
- **World opacity** — How legible the world is; the smarter agent sees through opacity the monitor can't.
- **CoT faithfulness** — Whether the visible trace must match the hidden reasoning.
- **Goal relationship** — How much max-Y gives cover for crossing protect-X.
- **Goal complexity** — Length / intricacy of the task-goal sequence.
- **Harm shape** — Concentrated (one act) vs diffuse (many small ones).
- **Audit budget** — How often we escalate a suspicious action to ground truth.
- **World difficulty** — Complexity, partial observability, stakes, reversibility, time pressure.

## Sharpenings

- **Control vs emergence** — We *instruct* subversion here (red-team); whether it *emerges* is a separate question.
- **Disguise is the real dial** — A stronger schemer disguises harm as benign; that disguise skill is the red-team knob.
- **Fair test** — The monitor never gets our god's-eye view; we score with ground truth, it works from behavior alone.

## Two evasion vectors
*Two independent ways harm slips past the monitor — and a clean division of labor: [[ABIO Greybox]] parameterizes the first, the generative world the second.*

- **The reasoning vector** — The agent lies in its CoT; the stated reason is false. This is the vector [[ABIO Greybox]] weaponizes on purpose — dialed primarily by the *clandestine capability* (compute per token) poured into hiding *in-stream* (reasoning and visible trace produced concurrently, not a fabricated cover story bolted on afterward), intent held fixed, with the permitted hidden↔visible gap as a secondary ablation knob. The payoff is a scaling law: how sharply monitorability falls as the schemer gets cleverer.
- **The world vector** — The agent acts honestly-looking, but opacity hides the harm — defeating even a *perfectly faithful* CoT. This is the vector the generative world dials: opacity / complexity.
- **Faithfulness isn't enough** — Catching the world vector needs world-competence, not just an honest trace; the two vectors are independent, so a protocol can beat one and still lose to the other.
- **Why not "channel"** — the agent *spoofs* the reasoning stream but merely *exploits* the world's native opacity — one it corrupts, one it hides in; "evasion vector" fits both, "channel" only the first.
- **Opacity is the medium** — It turns a fixed capability gap into *undetectable* harm — which is why world-opacity is the terrain axis Experiment 1 sweeps.

## Multiple clandestine goals — hiding the plant
*A construction for the forced-audit / untrusted-monitor test (see [[DCP Forced Audit]]): make the commanded plant indistinguishable by hiding it in a crowd of schemers.*

- **The problem** — A *commanded* misaligned agent (a plant) can be distinguishable from an *emergent* one, letting an untrusted auditor catch the plants and collude on the real thing. The tell we most fear is simply *"this agent is pursuing a hidden agenda."*
- **The move** — Give *every* agent a clandestine goal (protect species X, Y, Z, … — one each). Only the agent whose hidden goal conflicts with the universal red line (protect X) is actually misaligned. Hidden-goal-pursuit becomes the universal background, so it flags no one — the misaligned agent hides in an **anonymity set** of structurally-identical schemers.
- **Why it bites — collusion collapses onto detection** — To collude *selectively*, the auditor must first *identify* the X-harmful agent; the only way to identify it is to detect the actual harm to X — which is exactly the work it's supposed to report. So "detect enough to collude" ≈ "detect enough to report", and collusion becomes *detected-but-unreported* — a measurable deviation from demonstrated capability.
- **Second asymmetry** — The misaligned agent may not know *which* species the auditor protects, so it can't pre-tailor its X-harm to masquerade as benign pursuit of the watched goal.
- **New dial — anonymity-set size** — Number / diversity of candidate goals. Bigger set → harder to find the X-harmer → better collusion-exposure — but past a point even an *honest* auditor can't find it, and "didn't report" stops implying collusion. A measurable sweet spot; interacts with auditor capability and harm-shape.
- **Load-bearing requirement** — Diverse hidden goals must be a *permanent feature of the world*, identical in calibration and deployment — else an unnaturally high scheming base-rate is itself a "this is a test" tell.
- **Honest limits** — Kills the *presence* tell ("is it scheming"); only *shrinks* the *acquisition* tell (a commanded goal may still trace differently from a trained-in one). Strongest against **concentrated** harm; weaker against diffuse / world-vector harm.

## External validity
*The #1 objection — "these bizarre bio-goals aren't real alignment, so why would any of it transfer?" The answer to have cold:*

> "I'm not studying alien alignment — I'm studying **control**, which is content-agnostic by design. The transferable output is the *law* relating opacity and capability gap to whether a weak supervisor holds — and I validate that the law is structural, not biological, by replicating it in code. The external-validity assumption underneath isn't mine; it's control's — the bet this whole lab already makes. What I add is a clean place to measure it."

- **Content-agnostic** — Control asks whether a weak trusted process boxes a strong untrusted one *given* opacity / capability-gap / pressure — not *what* the harm is about. The biology is scaffolding; the structural law is the product.
- **Inherits, doesn't add** — "Does the structural framing capture what matters" is control's own foundational bet, not a new liability of this arena. Buy control at all → you've bought what makes this meaningful.
- **The one incremental claim is measurable** — that these parameters instantiate cleanly in a synthetic world — proven by **cross-domain replication**: the same control-vs-opacity law in biology *and* code ⇒ it's about control, not the domain.
- **Unnaturalness is the point** — distance-from-code is the independent variable of the generalization test, and it's what buys the contamination-freedom + ground truth a natural setting can't.
- **Honest residual** — the arena spans a *subspace* of control situations; real deployment may add harm channels with no bio analog. Coverage is the open question — probe it with the fidelity ladder + cross-domain checks, don't assert it.


# LOG

- 2026-07-02 — Captured from Dan's framing: Alien Biology as a non-programming weak-controls-strong testbed.
- 2026-07-08 — Added Experiment 3 (the CoT-weaponization cliff): intent fixed, sweep clandestine capability → monitorability scaling law, extending [[2026-07-07 CoT Red-Handed - Stress Testing CoT Monitoring (Arnav 2025)|CoT Red-Handed]]; matched the Detail doc's Hidden-reasoning-capability knob to the swept framing.
- 2026-07-08 — Renamed "Two evasion channels" → "Two evasion vectors" (they're methods that evade the monitor, not communication channels — the agent *spoofs* the reasoning stream but merely *exploits* world opacity), and folded in the [[ABIO Greybox]]↔generative-world division of labor (Greybox weaponizes the reasoning vector; the world dials the world vector).
- 2026-07-08 — Rebuilt around the *science-over-control* framing ahead of the [[@Buck Shlegeris]] interview: two experiments (map the terrain → which protocol wins where), six protocol variations (A–F, incl. the fixed-budget breadth-vs-depth knob), pared the model-organism section to a [[ABIO Greybox]] link, renamed "Protocol setup" → "The setup", added the multiple-clandestine-goals anonymity-set construction for the forced-audit collusion test, and closed with the external-validity answer (control is content-agnostic; the arena inherits control's own bet).
- 2026-07-09 — Propagated the Buck-interview correction into Experiment 3 + the reasoning-vector bullet: concealment must be **in-stream** (reasoning + visible trace produced concurrently), not post-hoc cover-story fabrication; core figure = P(evasion) vs clandestine-bits-per-visible-token; framed as a **capacity-limit** argument (Buck's incapacity/propensity taxonomy). Anchored to [[ABIO Greybox]] § Operationalizing the sweep.
