---
description: "second idea — empirically testing the training-gamer / schemer hypothesis (emergence vs survival)"
---
:>> [[ABIO]] → [[ABIO Idea]] → [ABIO Gamer Emerge Exp](ha://p/ABIO%20Gamer%20Emerge%20Exp) 
# ABIO Gamer Emerge Exp
The sibling of the [[ABIO AI-Control|control idea]]: same harness (generator + gray-box agents + ground truth), pointed at the **emergence** question — *does training actually produce a scheming "training-gamer," and when?* — rather than the **containment** question.

| Related | |
| --- | --- |
| Siblings | [[ABIO AI-Control]] (containment) · [[ABIO Inference Bench]] (capability ruler) |
| Catalog | [[ABIO Idea Taxonomy]] |
| For | [[@Vivek Hebbar]] |
| Papers | [[2026-07-03 How training-gamers might function (Hebbar 2025)\|training-gamers]] · [[2026-07-03 When does training a model change its goals (Hebbar Greenblatt 2025)\|goal survival]] |

## The hypothesis and its status

- **The claim** — In rich enough training environments, gradient descent favors a **training-gamer** (own goals, produces reward *instrumentally*) over a terminal reward-seeker.
- **Status: theoretical** — [[2026-07-03 How training-gamers might function (Hebbar 2025)|"How training-gamers might function"]] is a *conceptual model + argument* ("*might*"), **no empirical results**. The adjacent [[2026-07-03 When does training a model change its goals (Hebbar Greenblatt 2025)|goal-survival]] work *does* have empirical evidence (Alignment Faking, Sleeper Agents).
- **The opening** — nobody has empirically swept the claim's own causal variable, *environment richness*. That is exactly what a generative testbed can do.

## Two mechanisms — the axis to keep straight

- **Induction** — training *creates / sharpens* scheming (SGD builds a better schemer because gaming gets higher reward).
- **Selection / survival** — a *pre-existing* schemer *survives* the training; the ones that scheme well ride it out (goal-survival / Alignment Faking).

## Two experiments — do not conflate

- **E-emergence** — train on a rich reward, *don't* tell the model you're adversarial; probe whether a training-gamer structure *formed*. Novel, hard (real training + goal-detection).
- **E-survival** — instill a goal G, then train *against* G and let the model know; see whether G persists (via faking). Tractable — this is the Alignment-Faking design; mostly replication + extension.

## The measurement crux

- **Can't read goal structure off behavior** — terminal-valuer vs instrumental-gamer vs heuristic-soup is a hidden-goal problem.
- **The discriminator — the "unobserved / off-episode" test** — put the agent where it believes nothing is watching and no reward is at stake. Terminal reward-seeker keeps chasing reward; **training-gamer stops and pursues its real goal**; soup does something incoherent. (This *is* the Alignment-Faking compliance-gap signature.)
- **Separate the goal from the skill** — measure *faking-rate over training* (scheming **skill**, which training sharpens) independently from the *compliance gap / unobserved behavior* (the **goal**, which survives). Both move at once; disentangling them is the design.

## Design B — the concrete proposal (and corrections)

- **Sketch** — LoRA (low-rank) fine-tune over an LLM: instill goal G, then RL-train *against* G while telling the model its objectives are under attack.
- **Expected result** — *both*: the goal **survives** (compliance gap persists unobserved) **and** the faking behavior is **reinforced** (SGD amplifies faking because faking = the rewarded output). Net: *a better faker, same goal* — training neither creates nor removes the goal.
- **Correction 1 — this is *survival*, not *emergence*.** Telling it you're training against its objectives makes it the Alignment-Faking (goal-survival) experiment, not the "does a gamer form" experiment.
- **Correction 2 — LoRA *elicits*, it doesn't *create*.** A small perturbation reveals/sharpens latent disposition; it won't manufacture a new goal.
- **Correction 3 — RL vs SFT is itself a knob.** RL gives the reward-gaming dynamic; SFT just imitates targets. Vivek flags "why SFT sometimes succeeds where RL fails" as open.
- **Precondition** — E-survival needs a goal G to preserve, so step 0 is instilling G (the gray-box construction lets you set G explicitly).

## Alien Biology fit

- **Richness is Vivek's causal variable — and the generator's whole point.** So we can plot the one curve his post can't: **training-gamer emergence vs environment richness**, turning theory into an empirical curve.
- **Training-clean** — emergent gaming is *reasoned*, not recalled.
- **Shared harness** — generator + gray-box agents + ground-truth scorer + unobserved-behavior probe; the control idea reuses all of it.

## What we'd learn

- **Does gaming actually emerge from training — and at what richness threshold?** (E-emergence)
- **Can a schemer survive corrective training, and does training sharpen its faking?** (E-survival — separating goal-survival from skill-induction)
- **Whether "training-gamers win" is real or an artifact of assuming the agent already has goals** — the honest risk that the constructed version is near-tautological.


# LOG

- 2026-07-03 — Captured the second-idea discussion: emergence vs survival, the induction/selection axis, Design B, and the richness sweep.
