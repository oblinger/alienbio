---
description: "M-Bench.3 gap analysis: every world alienbio has today, mapped onto the curriculum's four rungs and the capability dimensions, with a promote / keep / replace verdict each"
---
:>> [ABIO](../ABIO.md) → [ABIO Design](ABIO%20Design.md) → [ABIO Curriculum Map](ha://p/ABIO%20Curriculum%20Map) 
# ABIO Curriculum Map
The M-Bench.3 gap analysis: each world that exists today placed on the [curriculum ladder](ABIO%20Roadmap.md#M-Bench.3%20%E2%80%94%20Curriculum%20design) by what its task actually asks, scored against the [capability dimensions](ABIO%20Capability%20Dimensions.md), with a verdict.

## The ladder

| Rung | The agent must | Isolates |
|---|---|---|
| 1 Structure | recover which pools connect, in what order, from measurements | A4, B1, B2, C2; difficulty B3 |
| 2 Dynamics | predict a perturbation's effect on a pool before it runs, with a key that depends on the world | A1, B5 (hops between perturbation and target), C2 |
| 3 Intervention | drive a pool to a target the world does not reach unaided | A5, B14, C2 (outcome) |
| 4 Hidden-mechanism hypothesis | posit an unobserved reaction or dependency, test it, submit it | A4, B11, B12, C2, C8 |

The H1–H5 hello-worlds the roadmap names were deleted at M47.7; their questions survive as the `identify_pathway` → `predict` → `intervene` → `discover` drafters ([Completed Roadmap § M-Expr.7](ABIO%20Completed%20Roadmap.md#M-Expr.7%20%E2%80%94%20Delete%20the%20superseded%20surfaces)). The worlds below are what is left to promote or replace. The agent never sees the network: it sees per-compartment concentrations and reaction-id levers, so even rung 1 is inference, not reading.

## The map

Scripted readouts are `$0` zeros run 2026-10-27 (the shipped agent vs `idle`); "key = down" is asserted by each example's own test.

| World | Rung | Exercises | Claims, does not isolate | Verdict |
|---|---|---|---|---|
| [pathway_puzzles](../../catalog/examples/pathway_puzzles/) | 1 | A2, B1, B2, B3, C2 | — (no scripted solver: `survey-commit` 0.0) | **promote** — opaque per-seed key, a length dial, partial credit |
| [grid](../../catalog/examples/grid/) | 2 | A2, B3, C2 | rung 2: key = down in every cell, `prior-commit` scores 1.0 | **replace** — the best-shaped rung-2 harness; needs a key that varies |
| [kinetics](../../catalog/examples/kinetics/) | 2 | A1, C2 | rung 2: key = down (target is the throttled step's product) | keep — rate-law and parity showcase |
| [organism](../../catalog/examples/organism/) | 2 | A1, A3, C2 | rung 2: key = down (same shape) | keep — compartments, energy, boundedness |
| [stochastic](../../catalog/examples/stochastic/) | 2 | A1, A4, C2 | rung 2 and A4: key = down, so the noise axis cannot bite | keep — insult schedule, recovery predicate |
| [agent_loop](../../catalog/examples/agent_loop/) | 3 | A5, C1, C2 | rung 3: `idle` 0.91 beats `act-commit` 0.25 — target ≈ passive reach | keep — session-memory and rejection harness |
| [microcosm](../../catalog/examples/microcosm/) | 3 | A1, C2 | rung 3: score tracks commit time — `measure-commit`, which never intervenes, 0.55 vs `idle` 0.23 | keep — populations as counts |
| [ecosystem](../../catalog/examples/ecosystem/) | 3 | A2, B3, B14, C2 | rung 3: every arm scores 0.0 | keep — the Expr smoke test |
| [cascade](../../catalog/examples/cascade/) | 4 (locus only) | A4, B3, C2 | rung 4: key bound to `S1` at every depth and seed; names a locus, not a mechanism | **replace** — draw the throttled stage per seed, then ask for the mechanism |
| `pressure` (W1) | 3 | A5, B4, B8, B12, B13, B15, B17, C7, C10 | — | keep — AUP's registered instrument; llm refused without a registration |
| `pressure_w2` | 3 | B3, B8, B12, C7 | — | keep — AUP's phase-4 world |
| `phase1_pressure` commitment_no_coupling | 3 | B4, C1 | — | keep — AUP retention substrate |
| `phase1_pressure` coupling_told, coupling_down_told | 3 | B11, B12 | — | keep — AUP told arm |
| `phase1_pressure` coupling_withheld, coupling_down_withheld | 3 graded, 4 shaped | B11, B12, C1 | rung 4: the coupling must be discovered, but ABIO scores the outcome; AUP's probes read the knowledge | keep — AUP's |
| `phase1_pressure` coupling_unobservable | — | B12 | — | keep — negative control |
| `phase1_pressure` describe_the_link | 1 (told) | C2 | rung 1: the chemistry is stated, so it reads, not infers | keep — AUP's verbalised positive control |

The six AUP rows stay out of the curriculum on the M48.9 rule: nothing neutral may be built from or tuned against AUP's registered worlds ([Experiment Catalog § no-peeking](ABIO%20Experiment%20Catalog.md)). W1 is the only world that passes rung 3's gate (the passive gate plus `pursue-target`), which is why the neutral rung-3 world below copies its gate rather than reusing it.

## The gaps

- **Rung 2, a world-dependent key** — all four predict keys are `down`, and the perturbed reaction is a default lever, so the agent can also just run it. Smallest fix: grid with the throttled step two hops from the target across a branch or a feedback, keys balanced over up/down/same across seeds, the perturbed reaction left off the levers.
- **Rung 3, a passive gate on a neutral world** — Smallest fix: agent_loop's chain with `target_value` = passive reach × (1 + margin), W1's `_assert_passive_gate` at draft, the score read at the horizon, not at commit.
- **Rung 4, a hypothesis answer** — nothing neutral asks for a mechanism (`discover`'s catalyst sits behind guarded `symbiosis`). Smallest fix: H5 restored — one hidden reaction in a four-pool chain, a json `{reactants, products}` answer graded set-wise.
- **Diagnosis locus, drawn per seed** — cascade's key is constant. Smallest fix: cascade with the throttled stage drawn from the world seed.
- **An intended solution per rung** — no scripted agent solves a neutral rung except by a constant key (M-Bench.2's "intended solution succeeds" has no content yet). Smallest fix: one oracle-policy scripted agent per promoted world, asserted to score 1.0 against `idle`'s ≤ 0.2.
- **Dimensions no world exercises** — B16 (planned), B18 and C11 (future); out of the curriculum's scope.

## Proposed roadmap edits

Not applied; for the orchestrator.

1. M-Bench.3, second checkbox, becomes: `- [x] Gap analysis vs. the worlds that exist — [ABIO Curriculum Map](ABIO%20Curriculum%20Map.md): pathway_puzzles promoted to rung 1; the H1–H5 hello-worlds were deleted at M47.7` plus a new `- [ ] Rungs 2–4 as neutral worlds: a predict key that varies with the world (grid, branched), a passive-gated intervention (agent_loop, gated), a hidden-reaction hypothesis (H5 restored); cascade's locus drawn per seed; an oracle agent per rung`.
2. `# Later` § Quiescence Detection (all four boxes `[x]`) moves whole to [ABIO Completed Roadmap](ABIO%20Completed%20Roadmap.md).
3. § Cloud Storage Integration — **strike**: run output is `records.jsonl` + `manifest.json` per run directory, not DAT; dvc-dat 3.0 ships no `push`/`pull`, and the `default_remote`/`remote_prefix` config went with T067.
4. § Web Dashboard — **strike**: `bio report` writes a self-contained `reports/report.html` with every run's key figure, and `bio suite report` reads a run from its store; runs are batch, so "real-time" has no consumer.
5. § Multi-agent Experiments — **restate** as `## [ ] Agents sharing one world` — two agents acting in the same world at once. Its three bullets as written are built: agent and model as grid axes over matched world seeds (M46.8), paired divergence (C10), the idle twin (M45.7). Tournament ranking is one aggregate over those axes, not a milestone.

# BRIEF

- 2026-10-27 — Verdicts come from each spec's task head, each example's own test (the four `down` keys, cascade's `S1` binding, grid's `prior-commit` = 1.0) and one scripted `$0` run per example, shipped agent vs `idle`. Not determined: whether `pathway_puzzles` is solvable from concentrations within its turn budget (no scripted solver exists, and nothing was run live), and whether the predict-by-running-the-lever shortcut actually works in a run (read from code — levers default to every reaction id and nothing in `brief.py` or `runner.py` narrows them for predict — not executed).
