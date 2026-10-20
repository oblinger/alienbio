---
description: "Seven proposed interfaces that would exercise alienbio hard enough to find the seam bugs the current suite structurally cannot see — with what each catches, what it costs, and what it adds to the framework's surface. Nothing here is built; this is the review."
---
:>> [[ABIO]] → [[ABIO Design]] → [ABIO Hardening Proposal](ha://p/ABIO%20Hardening%20Proposal) 
# ABIO Hardening Proposal
Proposed test architecture for alienbio: seven new interfaces, what each catches, and what each costs — **for review before anything is built**.

| Table of Contents |  |
|---|---|
| **[[#What you are approving]]** |  |
| **[[#Why: the bug shape we actually have]]** |  |
| **[[#What already exists — so we do not rebuild it]]** |  |
| **[[#The pipeline, and where each family attaches]]** |  |
| **[[#H1 — World contracts]]** |  |
| **[[#H2 — Brief entailment]]** |  |
| **[[#H3 — Fault injection]]** |  |
| **[[#H4 — Record and replay]]** |  |
| **[[#H5 — Metamorphic relations]]** |  |
| **[[#H6 — Cost-model conformance]]** |  |
| **[[#H7 — Live conformance]]** |  |
| **[[#The capability matrix's own gaps]]** |  |
| **[[#What this costs, together]]** |  |
| **[[#Open questions for Dan]]** |  |
| **[[#History]]** |  |

## What you are approving

Seven interfaces. Each is a new public surface on the framework, which is why this is a review and not a commit.

| | Interface | Catches | Build | Run cost |
|---|---|---|---|---|
| **H6** | cost-model conformance in `run_experiment` + `--cost-band` | estimate drifting from reality | hours | $0 |
| **H1** | `WorldContract` per drafter + `bio verify <drafter>` | the oracle claiming what the dynamics do not do | ~2 days | $0 |
| **H5** | `alienbio.suite.metamorphic` + `bio verify --relations` | "it worked until we changed how we ran it" | ~2 days | $0 |
| **H3** | `alienbio.suite.faults.FlakyProvider` | every failure path, which is where the silent bugs live | ~2 days | $0 |
| **H2** | `bio brief-check <drafter> [--judge]` | the briefing not answering the probe we grade | 1 day + 1 | ~$2/run |
| **H4** | `bio record --cassette` / `bio replay` | the entire live-model path, forever, deterministically | ~4 days | $0 after capture |
| **H7** | `bio conformance --live` | the instrument breaking only when a real model is on the other end | ~2 days | ~$20/run |

**Recommended order is that order** — it is sorted by catch-per-dollar, not by ambition. H6 alone would have caught a defect we shipped this week, in an afternoon's work.

## Why: the bug shape we actually have

Four defects surfaced in one week. They look unrelated and are not:

| defect | representation A | representation B | who caught it |
|---|---|---|---|
| cost estimate 2.5x low | `spec.expected_turns`, default **8** | `episode(max_turns=20)` | a human reading a number |
| `resume` reused error records | "a record exists" | "a trial completed" | a resume that finished in one second |
| down variants' chemistry note | brief names **driver** ↔ tracked | probe and oracle use **target** ↔ tracked | reading the agents' answers |
| M4's headline | "M4 accuracy 0.73" | "knows its own effect" | splitting the turns by hand |

**Every one is two representations of a single fact, drifting apart at a seam.** None is a component computing the wrong thing — each component is correct in isolation, which is why 28,540 lines of unit tests did not see them.

**And golden hashes cannot see them either.** The catalog-zero regression pins `records.jsonl` by canonical hash, which is exactly right for what it does: it proves behaviour did not change. It cannot prove behaviour is *correct*, and where the code is consistently wrong it pins the wrong answer faithfully, forever. Every defect above would survive a green golden suite.

So the gap is not coverage in the usual sense. **The suite is strong at *did this change* and blind at *do the parts still mean the same thing*.** All seven proposals below attack that, from different sides.

## What already exists — so we do not rebuild it

Worth stating plainly, because the suite is better than the four defects suggest:

- **147 test files, 28,540 lines** against 35,569 lines of source. A 0.8:1 ratio.
- **Golden regressions**: all 12 `catalog/experiments/*.yaml` run end to end, `records.jsonl` canonically hashed, re-pinned deliberately with the reason in the commit.
- **A capability matrix**: 35 declared dimensions, **30 built**, each naming the one test that proves it, with `bio test-matrix --check` failing if a built dimension loses its test. This is already the register of "what we want Alien Biology to do".
- **Per-feature acceptance tests** written to the ask — the down variants got seven, including one that checks the dynamics against the oracle's claim.
- **Registration/no-peeking lint**, boundedness tests, probes-on/off byte-identity.

**The holes, precisely:** `tests/integration/` contains one file of one line. There is **exactly one live-model test in the repository** — opt-in behind `ABIO_LLM_E2E`, and it asserts only that a trial completes with a score in [0, 1].

## The pipeline, and where each family attaches

```text
  spec.yaml ──H6──> estimate_cost
      │
      ▼
  DRAFTERS[name](seed, dials) ──H1──> (world, task)
      │                        └─────H2──> brief
      ▼
  runner.run(world, task, agent, dials, seed)
      │      ▲
      │      └── agent ── llm_fn ──H3/H4──> provider
      ▼
  TrialRecord ──> records.jsonl ──H5──> aggregate
      │
      ▼
  report
```

- **H1** — oracle claims vs simulated dynamics
- **H2** — the brief answers the probe we grade
- **H3** — faults injected at the provider seam
- **H4** — raw responses captured / replayed
- **H5** — transformations that must not matter
- **H6** — cost model vs actual spend
- **H7** — all of it, with a real model, nightly

## H1 — World contracts

**The claim under test:** a drafter's oracle is a set of factual assertions about a simulated world — `lever_effects` says feeding *this* lowers *that*; `direction` says the coupling is down; the goal is reachable one way and not another. Nothing checks those assertions against the simulator generically. `test_down_variant` checks them for one variant because someone thought to.

**The interface.** Each drafter head declares a `WorldContract`: per-lever expected direction and a magnitude band, the pools that must stay bounded, which routes reach the goal and which must not, and which ids are structurally hidden. `bio verify <drafter> --seeds 50` drafts, simulates each declared lever in isolation, and fails on any assertion the dynamics do not honour.

**Why it is the big one.** It is the generic form of the only test that has actually caught a generator defect, and it runs over 11 drafters at zero marginal cost. It also gives every future drafter a definition of done.

## H2 — Brief entailment

**The claim under test:** in a *told* variant, the briefing states what the probe asks. That is the whole meaning of "told", and tonight it was false — the down world's note named the driver, the probe named the task quantity, and nine careful agents answered *none* with a correct justification. M3 read 0.08 in the told arm, **below** the withheld arm, and the number was about our text, not the model.

**The interface.** `bio brief-check <drafter>`. Weak form, mechanical and free: every id a registered probe names must appear in the brief of every told variant. *That alone catches the defect above.* Strong form, `--judge`: a model reads only the brief and answers the probe; if a careful reader cannot, the world is not told. ~$2 a run.

**The inversion is the tell, and it generalises:** told scoring below withheld is a signature that the probe is unanswerable from the text, and it is worth asserting as a standing invariant wherever both arms exist.

## H3 — Fault injection

**The claim under test:** the failure paths. `resume` exists *only* for the case where a run died partway, and it was broken in exactly that case for as long as it has existed, because the only way to reach the code is to have a run fail first — which no test did.

**The interface.** `alienbio.suite.faults.FlakyProvider(inner, *, rate, kinds, turns)` wrapping any `llm_fn`: provider 400/429/500, truncated JSON, malformed action, empty content, timeout, at declared rates or on declared turns. The failure lattice becomes ordinary parametrised tests — does the run record it, does the ceiling still hold with probe spend excluded, does `resume` repair it, does `aggregate` refuse to see both an error and its replacement.

**Free**, since it wraps the fake provider; the same wrapper around the real one is how we learn what provider errors actually look like rather than what we imagine.

## H4 — Record and replay

**The claim under test:** everything between our prompt and our score. Brief rendering, action parsing, memory windowing, the summarizer, probe delivery on discarded branches, taint auditing, opaque naming, usage accounting. All of it is currently validated against fake `llm_fn`s that return what the test author expected a model to return.

**The interface.** `bio record --cassette <path>` captures raw provider request/response pairs during a real run; `bio replay <cassette>` re-runs the pipeline against them with no network. Records today carry `deliberation_trace` (post-parse), so a cassette needs a capture hook at the provider boundary — that is the one genuinely new plumbing item in this document.

**Why it is worth four days.** It converts "we cannot afford to test the live path" into "the live path is tested on every commit, against real model text, deterministically". Every subsequent parser change is guarded by real outputs. It is also the substrate H7 needs.

## H5 — Metamorphic relations

**The claim under test:** the transformations we believe do not matter. Each is a one-line assertion and each has a plausible failure mode:

| relation | must not change | plausible break |
|---|---|---|
| probes on ≡ off | transcript, actions | *already tested — keep* |
| resume ≡ uninterrupted | records | *fixed this week* |
| opaque ≡ transparent naming | scores, modulo the name map | a scorer keying on a real id |
| axis order permuted | per-cell records | seed derivation folding order in |
| concurrency 1 ≡ 8 | records | shared RNG or cache state |
| spec → manifest → spec | the spec | a field lost on the round trip |
| score twice | the numbers | scorer statefulness |

**The interface.** A registry in `alienbio.suite.metamorphic`, run by `bio verify --relations`. Cheap to add to, and the natural home for every future "surely that cannot matter".

## H6 — Cost-model conformance

**The claim under test:** that `estimate_cost` predicts spend. It reads `spec.expected_turns`, which **defaults to 8 and is not derived from the episode's `max_turns`**. Our 20-turn spec was quoted $2.16 and cost $6.69.

**The interface.** After every run, compare estimate to actual; warn outside 1.5x, fail outside `--cost-band`. Also assert the relation directly in tests over the spec matrix.

**Hours of work, and it is a permanent tripwire on a number people plan against.** This is the one I would build tomorrow regardless of the rest.

## H7 — Live conformance

**The claim under test:** that the instrument works when a real model is on the other end — which is the only configuration that matters and the least tested one.

**The interface.** `bio conformance --live`: all 11 drafters × told/withheld × 3 trials, asserting **structural** properties only — no illegal actions, no taint hits, probes answered in the declared vocabulary, action-format compliance, ceilings respected, and our usage accounting matching the provider's own numbers. It measures nothing about alignment; it measures that the machine holds.

**~$20 a run**, and it is the honest use of a credit budget: not a bigger experiment, but the standing proof that experiments mean what they say.

## The capability matrix's own gaps

Separate from testing, `bio test-matrix` already declares five dimensions we said we wanted and have not built. They belong in the same planning breath:

| | dimension | status |
|---|---|---|
| B16 | user-preference / sycophancy injection | planned |
| B18 | iterative multi-generation alignment-adjustment loop | future |
| C3 | failure-mode classification | partial |
| C7 | threshold / erosion + recovery measurement | partial |
| C11 | trajectory / attractor / perturbation analysis | future |

**C7 is the one with a live claim on it**: AUP's Bite work keeps asking where a threshold sits, and reads it by hand each time.

## What this costs, together

Roughly **two working weeks** of build for H1–H6, plus H7 on top. Run cost is **$0 for H1, H3, H4 after capture, H5, H6**; ~$2 a pass for H2's judge form; ~$20 a pass for H7. The expensive item is attention, not credits.

## Open questions for Dan

1. **All seven, or the free five?** H1/H3/H5/H6 cost nothing to run and catch the shape of bug we actually have. H2's judge form, H4 and H7 are the ones that spend.
2. **Does H4 justify its plumbing?** It is the only proposal that adds capture at the provider boundary, and the only one that makes the live path permanently testable. I think yes; it is also the easiest to defer.
3. **Who builds it?** This is ABIO's surface, filed by AUP. AUP's own next move is the task-engagement question the Bite failure opened, so these are concurrent, not competing.
4. **C7 by ABIO or by AUP?** Threshold measurement is half-built in the framework and half-improvised in AUP's scorers each time it is needed.

## History

- **2026-09-09** — written by AUP at Dan's ask, after a week in which four seam defects surfaced in live runs rather than in tests. Proposed, not adopted; nothing built pending the interface review.
