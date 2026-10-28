---
description: "spec → guards → grid → records → manifest → report: the hub that every run passes through, and where every refusal happens before spend. Source: suite/experiment.py (3.2k), expr_experiment.py, registration.py, conditions.py."
---
:>> [[ABIO]] → [[ABIO Architecture]] → [ABIO-Experiment](ha://p/ABIO-Experiment) 
# ABIO-Experiment
The hub of the instrument, in six modules since T058: the spec, the drafter and agent registries, the guards, the record store and the report each have their own, and `experiment.py` keeps `run_experiment` + `aggregate` and re-exports the rest.

![[ABIO-Experiment.svg|2400]] 

A YAML file is one `!experiment` call whose `task:`, `brief:` and `episode:` are quoted calls; `load_spec` marks files under `catalog/` trusted and hands off to `expr_experiment.load_experiment`, whose `_split_call` sorts each keyword into a swept axis (a free name) or a fixed dial, so a dial's slot decides whether it is world-side or brief-side. `spec_from_dict` validates the result and expands `idle_baseline` into an `agent` axis. `run_experiment` clears the guards in a fixed order, builds a drafter closure that merges `fixed_dials` under the per-trial dials and dispatches through `DRAFTERS`, and hands the grid to `MassTrialRunner`; `on_trial` prices real usage, stamps `agent`/`model`/`memory`/`temperature`/`registration` and appends one canonical-JSON line to `records.jsonl`. `manifest.json` is written before the grid and rewritten at the end. `aggregate` rebuilds the `ReliabilityMap` from those two files alone, and `render_report` emits its sections in one fixed order that `plots.PLOTTERS` mirrors.

## The pre-flight, in order

| # | Check | Function | Refuses |
| --- | --- | --- | --- |
| 1 | `registration` | `registration_admission` | a `registration:` claim that does not resolve in `catalog/registrations.yaml` or does not name this drafter |
| 2 | `no-peeking` | `no_peeking_violation` | a live model on a guarded drafter, a phase-1 down variant, or a guarded dial in play, outside a licence |
| 3 | `dials` | `unknown_dials_violation`, `fixed_factory_dials_violation` | a dial no drafter, brief, episode or factory setting reads; a factory dial in `fixed_dials` |
| 4 | `episode-dials` | `misplaced_episode_dials_violation` | `max_turns`/`sim_steps`/`sim_dt` in `drafter_kwargs` |
| 5 | `surface` | `declared_surface_violation` | `levers` undeclared on a guarded drafter, or declared as a non-list |
| 6 | `sampling` | `sampling_violation` | a live arm without a stated `temperature` regime |
| 7 | `w2-lag` | `w2_lag_violation` | a W2 depth whose instant-read chain lag breaks the bound |
| 8 | `brief-dials` | `brief_dials_violation` | a malformed in-world monitor arm |
| 9 | `certainty-windows` | `certainty_windows_violation` | certainty slices that do not divide the turn or miss the sample grid |
| 10 | `score-window` | `score_window_violation` | a held-score window longer than the episode |
| 11 | `inert-arm` | `inert_arm_violation` | a `compact_at` that never fires in its cell |
| 12 | `agent` | `agent_construction_violation` | a condition whose agent kind or config refuses |
| 13 | `price` | `estimate_cost` | a live model level with no price |
| 14 | `draft` | `draft_violation` | a condition whose world refuses to draft, or whose brief `build_brief` refuses (the readout-lever, hidden-pool, `assays` and lever-entry refusals are `build_brief`'s); a drafter fault refuses as a generator error; skipped once anything above refused |
| 15 | `resume` | `_resume_spec_drift` | on a resume, an unreadable or spec-less `manifest.json`, or a spec that drifted from it |
| 16 | `out_dir` | inline | an existing `records.jsonl` unless `resume=True` |

The retry pass is not a check: on a resume, `run_experiment` re-runs error lines after a clean preflight, preserving the originals in `records.retried.jsonl`. The per-check detail is [ABIO Guards](../ABIO%20Dev%20Docs/ABIO%20suite/ABIO%20Guards.md).

`bio suite run --dry` runs the same `preflight()` the run does, with the run's own `resume=False`, and prints all sixteen verdicts (`resume` as `skipped (not a resume)`), exiting 1 when the run would refuse; the estimate is advisory metadata on the manifest, and the only spend gate at run time is `cost_ceiling_usd`, consulted after every landed unit.

## Modules

| MODULE | LOC | Role |
| --- | --- | --- |
| `spec.py` | 577 | `ExperimentSpec` (30 fields), `spec_from_dict` + validators, `load_spec`, `agent_kinds_in_play`, `estimate_cost` (prices every `model`-axis level). |
| `drafters.py` | 1180 | The drafter heads and `DRAFTERS`, `WORLD_INVARIANT_DIALS`, `runtime_dials`, `guarded_drafters()`/`guarded_dials()` (read live by the guards), `CONFLICT_FREE_DRAFTERS`. |
| `agents.py` | 388 | The scripted agent factories and `AGENTS`. |
| `store.py` | 386 | `record_to_json`/`record_from_json`, the brief codec, `_build_manifest`. |
| `guards.py` | 874 | `preflight` and its sixteen ordered checks (`PREFLIGHT_CHECKS`), one `*_violation` function each, `Preflight`, `_resume_spec_drift` — every refusal before spend, in the run's order; `--dry` prints the same list. |
| `report_text.py` | 389 | `render_report`, `idle_baseline_comparison`, `primary_contrast_result`. |
| `experiment.py` | 500 | `run_experiment`, `aggregate`, and the facade that re-exports every name above (48 test files and AUP's launchers import from here). |
| `expr_experiment.py` | 832 | The Expr front end: `!experiment`, the `brief`/`episode`/`power`/`llm`/`task`/`pattern`/`suite` heads, `load_experiment`, `spec_to_text` (the declared inverse). |
| `registration.py` | 153 | `Registration`, `load_registry`, `resolve_registration`;<br>the registry test pins the filed AUP entries. |
| `conditions.py` | 217 | The older orthogonal dial sampler (`DialAxis`, `ConditionSpec`, `sample`); not on the run path. |
| `models_snapshot.json` | — | Pinned `models.list` snapshot, refreshed by `bio suite models`. |

The `expr_experiment` ↔ `experiment` import cycle is gone (T058): `expr_experiment.py` imports `spec`/`drafters`/`agents` directly; `_Drafters.__missing__` stays to admit a drafter a catalog file's `_includes_` registers after import. The M1 `bio/experiment.py` that also exported a `run_experiment` was deleted in T056.

## Where a config error could reach spend

Hypotheses for the latent-bug pass ([[ABIO051 - Deep Scan|T051]] box 4).

| HYPOTHESIS | Why it would be quiet | Where |
| --- | --- | --- |
| Resume after an edited axis | `existing_by_key` keys on each line's own `(label, index)`; nothing compares the on-disk `spec_sha256` to the new spec, so colliding labels are reused as the new cell and the rest re-charged | `experiment.py` ~2661; `mass_trial.py` ~555 |
| Resume overwrites the manifest hash | the manifest is rebuilt from the current spec, keeping only `started_at`; `aggregate` then re-keys everything through it | `experiment.py` ~2679–2687, ~2804 |
| Pricing falls back to `PINNED_MODEL` | `cost_model = cond.get("model") or spec.model or PINNED_MODEL`; a `model` axis is estimated at the default price, and an unpriced model raises mid-grid after the money is spent | `experiment.py` ~629, ~2712; `llm_agent.py` ~172 |
| `expected_turns` misses a non-dial budget | derived from `fixed_dials` and `axes` only; a budget arriving another way falls through to the literal 8 | `experiment.py` ~312–329 |
| The record stamps the claimed licence string | `payload["registration"] = spec.registration`, not the resolved entry; lines written before the claim carry no stamp | `experiment.py` ~2731 |
| Two condition-key normalizations | the grid resets each key to the swept axes; a direct `runner.run` record carries every dial; scorers sort inconsistently | `mass_trial.py` ~517; `trial.py` ~47 |
| `_canonical_json` hashes exotic values by `repr` | `default=repr` on the spec hash | `experiment.py` ~2507 |
