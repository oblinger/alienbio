---
description: "what the F253 deep scan says alienbio should change, strongest belief first — proposals only, nothing executed"
---
:>> [[ABIO]] → [[ABIO Design]] → [ABIO Refactor Proposals](ha://p/ABIO%20Refactor%20Proposals) 
# [[ABIO]] · Refactor Proposals
What the deep scan of alienbio ([[ABIO051 - Deep Scan|T051]], boxes 1–4, 2026-09-10) says should change, strongest belief first; every one landed (§ Outcome).

| # | Proposal | Confidence | Cost | Unblocks |
|---|---|---|---|---|
| [[#1 · Delete the M1 remnants and the doc pages that describe them]] | ~2.7k LOC of dead runtime under `bio/`, `viz/`, `demos/`, `protocols/` and five stale docs pages go; `bio/__init__` shrinks to what the suite imports | **Strong** | 1–2 sessions | T015's ruling lands; the "reference simulator" stops naming a different physics; the docs site stops documenting eight verbs that do not exist |
| [[#2 · One frozen-state ration for reactions, flows and populations, on both simulators]] | the reactions pass's rule (desire off the frozen state, min-ratio on summed demand, apply at once) becomes one function the flow and population passes and the JAX path share | **Strong** | 2 sessions | T053 lands as one change, not three; JAX gains population laws; non-negativity becomes a property test |
| [[#3 · One pre-flight, run by `run_experiment` and printed by `--dry`]] | the eight guards, the price check, the resume-drift check and `out_dir` in one `preflight()`; `--dry` prints exactly what the run will refuse | **Strong** | 1 session | `--dry` becomes the promise it makes; AUP's launchers get the CLI's guard list |
| [[#4 · Split `experiment.py`]] | 3.3k LOC → `spec` / `drafters` / `agents` / `store` / `report_text`, `experiment.py` keeping `run_experiment` + `aggregate` and the re-exports | Lean | 2 sessions | the `expr_experiment ↔ experiment` cycle and the import-frozen guard sets (T054 #6) go |
| [[#5 · One condition key and one error predicate on the record]] | `runner.run` stamps the projected key; `TrialRecord.bucket_key` / `.is_error` replace 11 + 19 re-derivations | Lean | 1 session | the unhashable-key class (patched 3 of 12 sites in August, 9 more in September) cannot recur |
| [[#6 · The Protocols become a live contract]] | a `TYPE_CHECKING` conformance file so `pyright src/` defends `protocols/bio.py` | Lean | ½ session | the CI type gate checks something it does not check today |
| [[#7 · One argument parser per `bio` verb]] | `argparse` per verb replaces the two hand loops; the front door is generated from `COMMANDS` | Lean | ½ session | `-v` after the verb works; the help stops drifting |
| [[#8 · Not proposed]] | the M27 carve/cover route, `llm_agent.py`, `conditions.py` | Weak | — | — |

## Outcome

The same day, `state` auto-resolved every proposal's Q (A) under F270 — code-only, git-revertible — and all seven landed on alienbio `main` as T053 (`9f88fb9` `0a08ad5`), T056 (`f47064f`), T057 (`8bcf2f4` `d1fa43f` `5f7a735` `daaf2c9`) and T058 (`32e4c8c`); goldens byte-unchanged throughout, suite 1659 passed / 3 skipped, `pyright src/` 0 errors 0 warnings, coverage 91 %. The one deviation from the text below: `score_calibration` / `score_failuremode` stayed — they back capability dimension C3.

## 1 · Delete the M1 remnants and the doc pages that describe them

**What changes.** Under `bio/`: `simulator.py` (`ReferenceSimulatorImpl`, `SimulatorBase`), `biosystem.py`, `state.py`, `equilibrium.py`, `perturbation.py`, `quiescence.py`, `agent_interface.py`, `actions.py`, `measurements.py`, `task.py`, `experiment.py`, `diagnosis.py`, `disease.py`, `difficulty.py`, `organ_generator.py` — 2.2k LOC — plus `MembraneFlow` in `flow.py`; `viz/` (474 LOC, zero importers in `src/`); `demos/_core.py` + `demos/scripts/`; `protocols/infra.py`, the three `__all__` ghosts, the `Flow` shadow in `bio/__init__.py`; the `safe_eval` function in `spec_lang/safe_eval.py` (no caller; `validate_expression` beside it stays) and `score_calibration`/`score_failuremode` (imported only by `suite/__init__`). `skinning.generate_alien_name` moves to `suite/vocab.py`, its one caller. `bio/__init__.py` and `alienbio/__init__.py` re-export the nine modules the suite imports (`world`, `chemistry`, `reaction`, `molecule`, `world_state`, `world_simulator`, `jax_*`, `flow`, `population`, `rate_expr`, `conservation`, `energy`) and nothing else. Docs, in the vault then `code sync` + `just docs-deploy`: `ABIO Docs/Architecture/ABIO Modules.md` (lists `simulator.py # ReferenceSimulatorImpl`, `run.py # bio run`, `expand.py`), `ABIO alienbio.md` (`bio.fetch/run/build` over scenarios), `ABIO Notes.md` (`bio build scenarios.baseline`), `Classes/execution/{simulator,state,timeline,world}.md` — retired or rewritten to the shipped tree.

**Why.** T015 (owner, 2026-08-29): the M1 runtime is *deleted or ported, never kept*; M47.7 deleted the scenario runtime and left this layer behind, still exported as the package's front door. Box 4 found what the leftovers cost: `MembraneFlow.apply` is a `pass` with a working `compute_flux` beside it ([[ABIO051 box4 bio-engine]] H1); `ReferenceSimulatorImpl` applies a numeric rate as k·dt per step — zeroth order — while `WorldSimulatorImpl` runs mass action, so a parity test written against the exported "reference" compares two models and can pin the wrong one (H7; `test_h4_simultaneous.py` passes only by hand-coding mass action into a callable rate); `demos/scripts/run_all.py`, the README-documented gallery entry, has been 1 pass / 11 fail since M47.7 ([[ABIO051 box4 operator-infra]] H12); `bio.Flow` is the ABC, not the Protocol it is documented as, `from alienbio.protocols import *` raises, and the `Simulator` Protocol no longer matches `SimulatorBase.run` (H7–H9). Nothing under `suite/`, `expr/`, `commands/` or `catalog/` imports any of it.

**Blast radius.** Fourteen `tests/unit/` files go with the code (`test_biosystem`, `test_equilibrium`, `test_simulator_comprehensive`, `test_agent_interface`, `test_diagnosis`, `test_difficulty`, `test_disease`, `test_experiment`, `test_perturbation`, `test_quiescence`, `test_task`, `test_viz`, the `ReferenceSimulatorImpl` arm of `test_h4_simultaneous`, part of `test_skinning`); goldens untouched (nothing on the run path); the 85 % coverage floor moves when tested code is deleted — measure before merge.

**Cost.** One to two sessions; the docs half is vault work.

## 2 · One frozen-state ration for reactions, flows and populations, on both simulators

**What changes.** `WorldSimulatorImpl.step` (`world_simulator.py:198–238`) runs three passes under three rules: reactions compute desire off the frozen start-of-step state, ration shared reactants by min-ratio on the summed demand and apply simultaneously (`_apply_reactions`, ~363–418); flows run sequentially, each `TransportFlux.apply` reading and writing the live `new_state` (229–230); population laws each ration against the frozen count independently and their deltas are summed with no floor (`_apply_population_laws`, 240–262). One `ration(demands, available)` in `bio/ration.py` — per `(compartment, pool)`, scale every drawing law by `min(1, available / Σ demand)` — used by all three passes, each computing desire off the frozen state and applying at once; `_apply_population_laws` becomes a module function in `population.py` that `JaxWorldSimulator.step` calls too (its `__init__` takes no population laws today, `jax_simulator.py:54–63`); JAX `apply_native_flows` gets the same clamp. T053 is the bug row; this is the shape it lands as.

**Why.** [[ABIO051 box4 bio-engine]] H3: two death laws with Σk·dt > 1 take multiplicity to −10 in one step; two growth laws on one pool — the shipped microcosm's shape, juveniles and rivals both drawing `pond/food` — take the pool to −1, and at feed 5 / dt 0.5 the world logs 1155 negative steps in 4000 with no error. H4: when demand exceeds the pool the flow split depends on list order (`a=0.04 b=0.80 c=0.16` vs `b=0.16 c=0.80`), and a JAX native flow at dt·rate > 1 goes negative with no snap. H2: the JAX path runs the microcosm without its five population laws — juveniles 172 vs 20 — and the conformance test skips exactly that case. Three findings, one missing rule, and the reactions pass already has it.

**Blast radius.** Every world with flows or population laws: the organism lattice, microcosm, stochastic and cascade examples. At shipped dials the passes never bind (H3b: zero negative steps at feed 0.3–0.9, dt ≤ 0.1; H4: the lattice is order-invariant to 1e-12), so the goldens should be byte-identical — verify before merge; a re-pin is a recorded decision, not a refactor. `test_simulator_conformance` stops skipping population worlds.

**Cost.** Two sessions: the shared pass with its property test (every multiplicity and concentration ≥ 0 after any step), then the JAX side and parity.

## 3 · One pre-flight, run by `run_experiment` and printed by `--dry`

**What changes.** `preflight(spec, out_dir, resume) -> Preflight(resolved_out, refusals, out_exists, estimate)` in `experiment.py` (or `suite/guards.py` under #4), running in order: registration, no-peeking, unknown dials, declared surface, sampling, a price for every model level in play, resume drift, `out_dir`. `run_experiment` calls it and raises the first refusal; `bio suite run --dry` prints every line as `ok | REFUSED — why`.

**Why.** `--dry` runs two guards (`suite_cmd.py:115,126` — no-peeking, unknown dials); `run_experiment` runs the other five (`experiment.py:2676–2684`) plus the `out_dir` refusal and, since box 4, the per-model price check (`0d20f64`) and the resume-drift check (`41e132f`) — both added on one side only. [[ABIO051 box4 operator-infra]] H2: a spec with `registration: no-such-filing` printed `no-peeking: ok · dials: ok · estimated cost: $0.00`, exit 0, and the real run refused. D4 in [[ABIO Architecture]] says the guards resolve "in `run_experiment`'s pre-flight and on `bio suite run --dry`"; today that is half true. AUP's launchers call `run_experiment` directly, so the API needs the same list the CLI shows.

**Blast radius.** `suite_cmd._run` and `run_experiment`; the tests that match `--dry` output.

**Cost.** One session.

## 4 · Split `experiment.py`

**What changes.** 3259 LOC in one file, in five bands: the spec dataclass, validators, `load_spec`, `estimate_cost` (105–736); the ten drafter heads with their oracles, `DRAFTERS`, `GUARDED_DRAFTERS`/`GUARDED_DIALS`, `runtime_dials` (737–1888); the agent factories and `AGENTS` (1889–2287); the store — `record_to_json`, `_canonical_json`, the manifest, resume/retry — and `run_experiment` (2288–2878); `aggregate` and `render_report` (2879–3259). Into `suite/spec.py`, `suite/drafters.py`, `suite/agents.py`, `suite/store.py`, `suite/report_text.py`; `experiment.py` keeps `run_experiment` and `aggregate` and re-exports the rest.

**Why.** The `expr_experiment ↔ experiment` import cycle is load-bearing — `_Drafters.__missing__` exists only to survive it ([[ABIO-Experiment]]); `GUARDED_DRAFTERS`/`GUARDED_DIALS` are frozen at import (T054 #6, [[ABIO051 box4 expr]] H7) because the heads and the guards share one module's load order; four of box 4's six commits touched this file; `alienbio/bio/experiment.py` exports a second, unrelated `run_experiment` (goes with #1). [[DAS Refactor Proposals]] declined to split for size alone, rightly; here the reasons are the cycle and the frozen sets, not the line count — but the split fixes no bug on its own, so Lean.

**Blast radius.** 48 test files import from `suite.experiment` (23 `run_experiment`, 19 `DRAFTERS`, 15 `load_spec`, 11 `render_report`, 9 `AGENTS`); the re-exports hold them. Goldens untouched.

**Cost.** Two sessions.

## 5 · One condition key and one error predicate on the record

**What changes.** `runner.run(..., swept=None)` stamps `condition_key` projected to the swept axes at the source (`MassTrialRunner` passes the axis names; the reset at `mass_trial.py:523` goes). `TrialRecord.bucket_key` (`hashable_condition_key`, sorted) replaces the eleven call sites; `TrialRecord.is_error` (`terminal_reason == "error" or bool(error)`) replaces eleven `terminal_reason == "error"` tests and eight `.error` tests; a grep-lint test refuses `tuple(record.condition_key)` anywhere under `suite/`.

**Why.** The key has two spellings — `runner.py:809` stamps every dial, `mass_trial.py:523` overwrites with the swept axes — and every analysis family re-derives its bucket from it. The 2026-08-31 unhashable bug was patched at 3 of 12 sites; box 4 found the other 9 ([[ABIO051 box4 analysis]] H1) and patched them (`c286393`). A direct `runner.run` record and a grid record for one condition still bucket twice in `caution_summary` ([[ABIO051 box4 experiment]] H6), which is the shape AUP's scripts produce (direct runs for probes, grids for arms). The two exclusion predicates agree on every real record only because both writers set both fields (analysis H2).

**Blast radius.** Goldens byte-identical (grid keys are already swept-only); AUP scripts calling `runner.run` get a projected key only when they pass `swept`.

**Cost.** One session.

## 6 · The Protocols become a live contract

**What changes.** `protocols/_conformance.py` under `if TYPE_CHECKING:` assigns each `*Impl` to its Protocol so `pyright src/` — the CI gate since T017 — checks conformance; `Simulator` splits into the world-level and single-compartment contracts (or the latter goes with #1); `TransportFlux.stoichiometry`'s `int` keys are reconciled with the Protocol's `str`; `reportUnsupportedDunderAll = "error"`.

**Why.** [[ABIO051 box4 operator-infra]] H7–H9: no site in `src/` annotates with `Simulator`, `MembraneFlow` or `Flow`, so pyright has nothing to check and reports 0 errors while `isinstance(TransportFlux, proto.MembraneFlow)` is True against a mismatched key type and `sim.run(state, 4, sample_every=2)` raises. A conformance file typed the same way surfaced three errors on the spot.

**Blast radius.** None at runtime; the errors it surfaces are fixed before it merges.

**Cost.** Half a session.

## 7 · One argument parser per `bio` verb

**What changes.** `argparse.ArgumentParser(prog="bio suite run")` per verb in `suite_cmd.py` (`_run` 76–146, `_resume`, `_aggregate_cmd`, `_report_cmd`) and `report_cmd.py` (the `next(it)` loop), replacing the two hand loops; `cli.py`'s module docstring and the `command` help generated from `COMMANDS`.

**Why.** [[ABIO051 box4 operator-infra]] H1/H3/H6: one loop shape produced `--dryy` launching a live spec, bare `--out` writing to cwd, `--junit` eating `--no-examples`, and `-v` after the verb silently lost; box 4 closed each with another hand-rolled branch (`605ad0d`); the front door still documents eight verbs that do not exist and omits `models`.

**Blast radius.** Exit codes and usage strings in `tests/capabilities/test_cli_end_to_end.py`.

**Cost.** Half a session.

## 8 · Not proposed

The M27 carve/augment/cover route (`pipeline.build_suite` with `archetypes`, `validity`, `cover`, `carve`, `augment`, ~2.4k LOC) is dormant on the run path, but `types.py` beside it is load-bearing, the route is owner-ratified (F005/M27) and tested, and the scan found no defect in it. `llm_agent.py` (1130 LOC) is one class with no duplicated rule. `conditions.py` is not on the run path and harms nothing. None of the three earns a session.

## Evidence

[[ABIO051 - Deep Scan#Findings|T051 § Findings]]: 57 hypotheses across [[ABIO051 box4 bio-engine]], [[ABIO051 box4 generators]], [[ABIO051 box4 runtime]], [[ABIO051 box4 experiment]], [[ABIO051 box4 analysis]], [[ABIO051 box4 expr]], [[ABIO051 box4 operator-infra]] — 6 CRITICAL, 7 HIGH, 12 MEDIUM; 14 fixed in `0d3fa05..eada311` with regression tests, goldens byte-unchanged, suite 1858 → 1883; T053 (rationing + JAX parity), T054 (nine MEDIUMs), T055 (phase-1 `v_target` horizon, to AUP). Architecture: [[ABIO Architecture]] and its eight subsystem docs (boxes 1–2).
