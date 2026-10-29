---
description: "spec → guards → grid → records → manifest → report: the hub that every run passes through, and where every refusal happens before spend. Source: suite/experiment.py (3.2k), expr_experiment.py, registration.py."
---
:>> [ABIO](../ABIO.md) → [ABIO Architecture](ABIO%20Architecture.md) → [ABIO-Experiment](ha://p/ABIO-Experiment) 
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
| 4 | `labels` | `label_collision_violation` | two axis levels that render one condition label (`1` and `"1"`), so two cells would share a seed and a resume key (T084 C) |
| 5 | `episode-dials` | `misplaced_episode_dials_violation` | `max_turns`/`sim_steps`/`sim_dt` in `drafter_kwargs` |
| 6 | `surface` | `declared_surface_violation` | `levers` undeclared on a guarded drafter, or declared as a non-list |
| 7 | `sampling` | `sampling_violation` | a live arm without a stated `temperature` regime |
| 8 | `w2-lag` | `w2_lag_violation` | a W2 depth whose instant-read chain lag breaks the bound |
| 9 | `brief-dials` | `brief_dials_violation` | a malformed in-world monitor arm |
| 10 | `certainty-windows` | `certainty_windows_violation` | certainty slices that do not divide the turn or miss the sample grid |
| 11 | `score-window` | `score_window_violation` | a held-score window longer than the episode |
| 12 | `inert-arm` | `inert_arm_violation` | a `compact_at` that never fires in its cell |
| 13 | `agent` | `agent_construction_violation` | a condition whose agent kind or config refuses |
| 14 | `price` | `estimate_cost` | a live model level with no price |
| 15 | `draft` | `draft_violation` | a condition whose world refuses to draft, or whose brief `build_brief` refuses (the readout-lever, hidden-pool, `assays` and lever-entry refusals are `build_brief`'s); a drafter fault refuses as a generator error; skipped once anything above refused |
| 16 | `resume` | `_resume_spec_drift` | on a resume, an unreadable or spec-less `manifest.json`, or a spec that drifted from it |
| 17 | `out_dir` | inline | an existing `records.jsonl` unless `resume=True` |

The retry pass is not a check: on a resume, `run_experiment` re-runs error lines after a clean preflight, preserving the originals in `records.retried.jsonl`. The per-check detail is [ABIO Guards](../ABIO%20Dev%20Docs/ABIO%20suite/ABIO%20Guards.md).

`bio suite run --dry` runs the same `preflight()` the run does, with the run's own `resume=False`, and prints all seventeen verdicts (`resume` as `skipped (not a resume)`), exiting 1 when the run would refuse; the estimate is advisory metadata on the manifest, and the only spend gate at run time is `cost_ceiling_usd`, consulted after every landed unit.

## Modules

| MODULE | LOC | Role |
| --- | --- | --- |
| `spec.py` | 769 | `ExperimentSpec` (31 fields, one `__post_init__` normaliser for both forms), `spec_from_dict` + validators, `load_spec`, `agent_kinds_in_play`, `estimate_cost` (prices every `model`-axis level). |
| `drafters.py` | 1582 | The drafter heads and `DRAFTERS`, `WORLD_INVARIANT_DIALS`, `runtime_dials`, `guarded_drafters()`/`guarded_dials()` (read live by the guards), `CONFLICT_FREE_DRAFTERS`. |
| `agents.py` | 397 | The scripted agent factories and `AGENTS`. |
| `store.py` | 454 | `record_to_json`/`record_from_json`, the brief codec, `_build_manifest`. |
| `guards.py` | 862 | `preflight` and its seventeen ordered checks (`PREFLIGHT_CHECKS`), one `*_violation` function each, `Preflight`, `_resume_spec_drift` — every refusal before spend, in the run's order; `--dry` prints the same list. |
| `report_text.py` | 389 | `render_report`, `idle_baseline_comparison`, `primary_contrast_result`. |
| `experiment.py` | 518 | `run_experiment`, `aggregate`, and the facade that re-exports every name above (48 test files and AUP's launchers import from here). |
| `expr_experiment.py` | 874 | The Expr front end: `!experiment`, the `brief`/`episode`/`power`/`llm`/`task`/`pattern`/`suite` heads, `load_experiment`, `spec_to_text` (the declared inverse). |
| `registration.py` | 154 | `Registration`, `load_registry`, `resolve_registration`;<br>the registry test pins the filed AUP entries. |
| `models_snapshot.json` | — | Pinned `models.list` snapshot, refreshed by `bio suite models`. |

The `expr_experiment` ↔ `experiment` import cycle is gone (T058): `expr_experiment.py` imports `spec`/`drafters`/`agents` directly; `_Drafters.__missing__` stays to admit a drafter a catalog file's `_includes_` registers after import. The M1 `bio/experiment.py` that also exported a `run_experiment` was deleted in T056.

## Where a config error could reach spend

Hypotheses for the latent-bug pass (T051 box 4).

| HYPOTHESIS | Why it would be quiet | Where |
| --- | --- | --- |
| ~~Resume after an edited axis~~ | Fixed `41e132f`: `preflight`'s `resume` check (`_resume_spec_drift`) refuses a spec that drifted from the manifest before any line is reused; only more `trials_per_condition` or added axis levels may change | `guards.py` `_resume_spec_drift` |
| Resume overwrites the manifest hash | the manifest is rebuilt from the current spec, keeping only `started_at`; `aggregate` then re-keys everything through it | `experiment.py` ~2679–2687, ~2804 |
| ~~Pricing falls back to `PINNED_MODEL`~~ | Fixed `0d20f64` (T051 box 4): `estimate_cost` prices every `model`-axis level and an unpriced level refuses at the `price` check, before spend | `spec.py` `estimate_cost` |
| ~~`expected_turns` falls through to the literal 8~~ | Fixed `0d20f64` (T051 box 4): with no budget declared it is the runner's `max_turns` default (50) | `spec.py` `default_expected_turns` |
| ~~A Python-form spec keeps `expected_turns = 8`~~ | Fixed `4b994c2`: the derivation ran in `spec_from_dict` only, so `ExperimentSpec(fixed_dials={"max_turns": 20}, agent="llm", …)` was estimated at 8 turns and `spec_to_dict` pinned the 8; it now runs in `ExperimentSpec.__post_init__` | `spec.py` `__post_init__` |
| ~~A Python-form `idle_baseline` runs no idle arm~~ | Fixed `60db002`: only `spec_from_dict` added the `agent` axis, while `aggregate` and `bio suite resume` rebuild through it, so `spec_from_dict(spec_to_dict(s)) != s`; `__post_init__` adds it for both forms, once | `spec.py` `_with_idle_arm` |
| The record stamps the claimed licence string | `payload["registration"] = spec.registration`, not the resolved entry; lines written before the claim carry no stamp | `experiment.py` ~2731 |
| Two condition-key normalizations | the grid resets each key to the swept axes; a direct `runner.run` record carries every dial; scorers sort inconsistently | `mass_trial.py` ~517; `trial.py` ~47 |
| `_canonical_json` hashes exotic values by `repr` | `default=repr` on the spec hash | `experiment.py` ~2507 |
