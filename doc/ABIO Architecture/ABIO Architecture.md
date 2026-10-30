---
description: "How alienbio is built — a chemistry substrate, an instrument (Expr + suite/) that drafts worlds and runs agents against them under guards, and the operator surface + files that AUP's paper consumes."
---

| -[ABIO Architecture](ABIO%20Architecture.md)- | : How alienbio is built — a chemistry substrate, an instrument (Expr + suite/) that drafts worlds and runs agents against them under guards, and the operator surface + files that AUP's paper consumes.<br>→ [ABIO](../ABIO.md) → [ABIO Architecture](ha://p/ABIO%20Architecture) |
| --------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Related                                       | [ABIO PRD](../ABIO%20Design/ABIO%20PRD.md),  [ABIO Suite Runtime](ABIO%20Suite%20Runtime.md),  [ABIO Protocols](../ABIO%20Ref/ABIO%20Protocols.md),  [ABIO Expr Spec](../ABIO%20Guides/ABIO%20Expr%20Spec.md),  T051,                                                              |
| Subsystems                                    | [Bio-Engine](ABIO-Bio-Engine.md),  [Expr](ABIO-Expr.md),  [Generators](ABIO-Generators.md),  [Experiment](ABIO-Experiment.md),  [Runtime](ABIO-Runtime.md),  [Analysis](ABIO-Analysis.md),  [Infra](ABIO-Infra.md),  [Operator-Surface](ABIO-Operator-Surface.md),                 |
| Suite                                         | [Suite Construction](ABIO%20Suite%20Construction.md),  [Suite Construction Data Model](ABIO%20Suite%20Construction%20Data%20Model.md),  [Suite Runtime](ABIO%20Suite%20Runtime.md),                                                                                                |
| Layers                                        | [alienbio](ABIO%20alienbio.md),  [biology](ABIO%20biology.md),  [infra](ABIO%20infra.md),                                                                                                                                                                                          |
| Docs                                          | [Architecture Docs](ABIO%20Architecture%20Docs.md),  [PRD Docs](ABIO%20PRD%20Docs.md),                                                                                                                                                                                             |
| ...                                           |                                                                                                                                                                                                                                                                                    |

# ABIO Architecture
How alienbio is built: a chemistry substrate under an instrument that drafts worlds, runs agents against them under guards, and writes records the paper reads.

![[ABIO Architecture.svg|2400]] 

Every arrow is a call or a write in the direction drawn; nothing in the substrate knows the instrument exists, and nothing in the instrument reaches the network except the runtime's one metered seam to the Anthropic API. One edge is not drawn: the suite registers its drafter and experiment heads into Expr's registry at import, a plugin edge rather than a call.

## Subsystems

| SUBSYSTEMS | Description |
| --- | --- |
| [[ABIO-Bio-Engine]] | `src/alienbio/bio/` — chemistry, one compiled rate grammar, the reference + JAX simulators that must agree to 1e-9, flows, populations, the canaries. A wrong number here corrupts every trial silently. |
| [[ABIO-Generators]] | `suite/{pressure,phase1,conflict,delta}_gen.py`, `skeleton.py`, `blocks.py`, `hazard.py` — the drafters and the generator-held truth every score grades against. |
| [[ABIO-Runtime]] | `suite/runner.py`, `agent.py`, `llm_agent.py`, `brief.py`, `trial.py`, `mass_trial.py`, `naming.py` — the live loop: the brief, probes, compaction, opaque names, taint audit, concurrency, per-trial error isolation. |
| [[ABIO-Experiment]] | `suite/spec.py`, `drafters.py`, `agents.py`, `store.py`, `guards.py`, `report_text.py`, `experiment.py` (the facade), `expr_experiment.py`, `registration.py` — spec → guards → grid → records → manifest → report; every refusal before spend. |
| [[ABIO-Analysis]] | `suite/dose.py`, `delta.py`, `caution.py`, `degradation.py`, `faking.py`, `tradeoff.py`, `realism.py`, `census.py`, `plots.py` and the `score_*` primitives — what the paper reads. |
| [[ABIO-Expr]] | `src/alienbio/expr/`, `spec_lang/` — the loader/evaluator, heads and templates, and the untrusted-spec sandbox (AST allowlist, `!py`/include gates). The security surface. |
| [[ABIO-Operator-Surface]] | `cli.py`, `commands/`, `report.py`, `capabilities.py`, `config.py`, `justfile`, `ci.yml` — the `bio` CLI, the capability matrix, the one-page report, the gates. |
| [[ABIO-Infra]] | `infra/`, `protocols/` — `Entity`, the `mk` pegboard, the Protocols the substrate implements (checked by `pyright src/`). Cross-cutting, light. |

Row order is the scan order of T051 § Scope (riskiest first); each doc carries its own hand-authored figure and closes with the seams box 4 tested — what each found and what landed is noted there, and the refactors are [[ABIO Refactor Proposals]] (all eight landed 2026-09-10 as T053/T056/T057/T058).

## Overview

| ABIO at a glance |  |
| --- | --- |
| Code | `~/ob/grove/alienbio` — `src/alienbio/` 33.7k LOC, `tests/` 26.3k LOC<br>suite 1659 passed / 3 skipped · `pyright src/` 0 errors 0 warnings · coverage 91 % |
| Entry points | `bio suite run\|resume\|aggregate\|report` · `load_spec` · `run_experiment` · `DRAFTERS[name](seed, dials, **generator)` |
| Consumer | AUP — every phase-1/2/3 arm is a `catalog/experiments/*.yaml` spec or a script over `DRAFTERS` |
| Gates | `just test` · `just check` · `bio test-matrix --check`<br>fifteen golden zeros (`records.jsonl` hashes) · CI (`.github/workflows/ci.yml`) |
| Truth | generator-held oracles on `task.setup["oracle"]`; the agent sees surface names only; a registered filing (`catalog/registrations.yaml`) is what admits a live model to a guarded world |
| Published | `https://oblinger.github.io/abio-docs/` — mkdocs builds the repo's `doc/` directly ([ABIO Docs](../ABIO%20Docs.md)) |


alienbio is one Python package in three layers. The **substrate** (`bio/`, `infra/`) is a deterministic alien-chemistry engine: molecules, reactions, compartments, flows and populations, integrated by a reference simulator and a JAX simulator that must agree to 1e-9. The **instrument** (`expr/` + `suite/`) turns a YAML spec into an experiment: the Expr language loads the spec and resolves it against registered heads; the experiment layer expands axes into a condition grid and guards every run before spend (the no-peeking rule, the registration licence, unknown dials, the cost ceiling); the generators draft a world + task + oracle per trial; the runtime runs a scripted or live-model agent through the turn loop under opaque names and a taint audit; the analysis half scores the records and writes the report. The **boundary** is the `bio` CLI on one side and, on the other, the files a run leaves in `runs/<name>/` — `records.jsonl` is the artifact the paper reads, and the golden zeros pin it byte-for-byte across the ten shipped experiment types.

## Process model

Single process, no daemon. `bio suite run` loads one spec, plans the grid, then `MassTrialRunner` runs trials in a bounded thread pool (`concurrency:`), each trial drafting its own world from a seed derived from `(label, index)` so a resume re-draws the same worlds. Every landed trial appends one line to `records.jsonl`; `manifest.json` is written up front and carries the spec hash, git state, model snapshot and the resolved registration. A live-model trial makes its calls through one `LLMFn` provider seam with a shared usage meter; the cost ceiling stops the run between trials, never mid-call. Analysis and report run after the fact over the records on disk, so `aggregate` and `report` never need the worlds again.

## Boundaries that hold the design together

- **Generator-held truth.** The oracle a scorer grades against is minted by the drafter and rides `task.setup["oracle"]`; nothing downstream re-derives it. Every AUP defect of 2026-09 was two representations of one fact drifting at exactly this seam, which is why the generators are scanned first.
- **The agent never sees a structural id.** `naming.py` renames at the runner boundary (`m01`, `r01`), the taint audit reads a structural id in any prompt as a leak, and hidden ids are structurally invisible under observability narrowing.
- **No peeking, encoded once.** `no_peeking_violation` is the single rule: a live model on a guarded drafter, or on any world with a guarded dial in play, is refused before spend unless a filed registration in `catalog/registrations.yaml` names exactly those dials on exactly that drafter. The registry test pins the filed AUP entries, so a deleted licence is a red test.
- **Frozen bytes are the contract.** Fifteen golden zeros (`tests/suite/test_golden_experiments.py`) hash `records.jsonl`; every additive dial defaults to the byte-identical path and serializes only when set. A change that re-pins a golden is a recorded decision, not a refactor.
- **One rate grammar, two simulators.** The full rate expression grammar compiles to `bio/rate_expr.py` trees both simulators run; parity to 1e-9 is a CI test, and the M24/M47 parity bugs were found by it.
- **Repo → site.** Every page lives in the repo under `doc/` (since 2026-10-19 the anchor is the repo) and mkdocs publishes it straight from there (`docs_dir: doc`; `exclude_docs` keeps `ABIO Track/`, notebooks and `_hooks/` off the site). The build hook `doc/_hooks/strip_spine.py` drops each page's leading `:>>` breadcrumb line and unwraps every `ha://` link to its label, so the files keep what the vault daemon writes and the site shows neither ([ABIO Docs](../ABIO%20Docs.md)).

## Design decisions

| # | Decision | Rationale |
| --- | --- | --- |
| D1 | Worlds are composed from typed skeleton blocks, not hand-written | A small control surface must reach a buried crux only through indirection; [[ABIO Skeleton Arch]] is the subsystem-level design. |
| D2 | Experiments are declared in Expr, with the drafters as heads | One call-shaped generative form over YAML replaced four overlapping dataclass DSLs (F007 G4, ratified 2026-08-29); the ten catalog experiments proved byte-identical across the port. |
| D3 | Rejection, clamping and errors are data, not exceptions | A hallucinated lever id, an over-cap pull or a provider failure lands on the record (`illegal_action_limit`, clamp notes, error trials) so a paid grid is never killed by one trial. |
| D4 | Guards run before spend | Registration, no-peeking, unknown dials, declared surface, sampling, the per-model price, resume drift and `out_dir` resolve in one `preflight()` that `run_experiment` raises from and `bio suite run --dry` prints; a config error is a refusal, never N error records. |
| D5 | The instrument ships no experiment-specific scoring | Scorers read the objective's own targets; AUP's violation/erosion scoring lives in AUP's `run.py` (their ask, 2026-08-27), keeping the instrument neutral. |

Anchor-wide rulings — the safety-adjacency rule, the no-peeking rule's origin, what is out of scope — live in [[ABIO PRD]] and [[ABIO Experiment Catalog]] and are referenced, not restated.

## See also

- [[ABIO PRD]] — what ABIO is for; the ten requirements with build status.
- [[ABIO Suite Runtime]] — the published description of the turn loop, agents and experiment artifacts.
- [[ABIO Protocols]] — the class index the substrate implements.
- [[ABIO Expr Spec]] — the language by example.
- [[ABIO Roadmap]] — the forward milestones (M-Bench, M-FixPoint, M-Harden); the 41 done ones in [[ABIO Completed Roadmap]].
