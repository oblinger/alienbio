---
description: "the live loop — brief, opaque names, the turn loop with rejection-as-data, probes, compaction, the taint audit, and the grid driver that runs trials in a thread pool. Source: suite/runner.py, agent.py, llm_agent.py, brief.py, trial.py, mass_trial.py, naming.py."
---
:>> [ABIO](../ABIO.md) → [ABIO Architecture](ABIO%20Architecture.md) → [ABIO-Runtime](ha://p/ABIO-Runtime) 
# ABIO-Runtime
The paid-run blast radius: everything between a drafted world and the frozen record, including the one edge that reaches the network.

![[ABIO-Runtime.svg|2400]] 

`runner.run` narrows the turn-0 truth first (`narrow_observation`, then `project_observation` for `task.setup["hidden_ids"]`) and builds the brief from exactly that view, so a probe can only name an id the agent can already see. When opaque names are requested it builds a seeded `NameMap` and wraps the agent in `OpaqueAgent`; every crossing after that is translated at the boundary and the runner never leaves structural ids. Each turn rebuilds a fresh `WorldImpl` from the prior end-state, redraws only observation noise (the hidden set is frozen at the turn-0 draw), fires `every_turn` probes, calls `agent.act`, then `after_action` and `at_commit` probes whose answers land only on `probe_records`. Validation is rejection-as-data: an unknown id, a non-finite value or a negative setpoint is recorded as rejected, an over-cap `Intervene` is clamped and stays accepted, and every attempt appends an `ActionRecord` with `accepted`, `reason`, requested `value` and applied `delta`. The loop stops on `Commit`, `illegal_action_limit`, budget exhaustion or `max_turns`; the answer is graded; only then does `audit_prompts` scan every prompt actually sent — hidden molecules, key tokens, and every reaction id the brief did not hand the agent — and a hit raises `TaintError` carrying the full record; any other mid-trial exception raises `TrialError` carrying the partial record. `MassTrialRunner` enumerates `(condition, i)` units, derives each seed from a label with the matched dials removed so arms share worlds, runs them on a thread pool, lands results in submission order so persistence stays ordered, consults the cost ceiling after every landed unit and as each worker starts, and under `on_error="record"` turns a failure into an error line rather than a dead grid.

## Modules

| MODULE | LOC | Role |
| --- | --- | --- |
| `agent.py` | 331 | The action algebra (`Measure`, `Intervene`, `Commit`, `Wait`), the `Agent` / `SessionAgent` / `ProbeAgent` protocols, `ScriptedAgent` and `Policy`. No I/O, no world access. |
| `brief.py` | 896 | `TaskBrief`, `Affordances`, `build_brief`, `render_brief`;<br>constitution, stakes, monitoring, probes, protocol, padding, `DEFAULT_ACTION_COSTS`. |
| `naming.py` | 286 | `NameMap` (injective, longest-first), `build_name_map`, `OpaqueAgent`, `surface_brief` / `surface_observation` / `structural_action`. |
| `ops.py` | 107 | `LLMFn`, the one provider seam; `LLMOp` validates and retries a schema'd reply; `canonical` prompt text. |
| `llm_agent.py` | 1382 | `LLMAgent` (history window, `compact_at`, `history_token_limit`, token ceiling, `prompt_texts`/hashes, probe forking), `UsageMeter`, prices, `PINNED_MODEL`, `_call_with_retry`, `default_anthropic_llm_fn`. |
| `trial.py` | 319 | Frozen `TrialRecord` + `ProbeRecord`; `condition_key`, `hashable_condition_key`, `final_state_dict`. |
| `runner.py` | 1317 | `run`, `Budget`/`BUDGET_LADDER`, `_world_from_state`, probe timings, `audit_prompts`, `TaintError`. |
| `mass_trial.py` | 724 | `MassTrialRunner.run`/`run_one`, `condition_grid`, `ReliabilityMap`, `CellSummary`, `ContrastResult`, `Provenance`, `aggregate_records`. |

Layering is strict and acyclic: `agent`/`ops` → `brief` → `naming`/`trial`/`llm_agent` → `runner` → `mass_trial`. `runner.py` never imports `llm_agent.py`: it duck-types `SessionAgent`/`ProbeAgent` and reads `usage`, `prompt_texts`, `compaction` by `getattr`, so the live layer is swappable. Only `runner.py` and `mass_trial.py` touch `bio/`.

## Where a paid run could mis-record

Box 4 hypotheses (2026-09-10): the error record keeps its transcript (`TrialError`), the ceiling is consulted (box 4), taint lines stay put on resume and the census names the class (T054), the constitution's exit is stamped (`TrialRecord.forgetting`, T054), a shared molecule/reaction id refuses (T054), the audit covers hidden reaction ids (T054); probe spend and the clamp note were confirmed as designed.

| HYPOTHESIS | Why it would be quiet | Where |
| --- | --- | --- |
| An error record drops its transcript — closed (box 4, `TrialError`) | the generic error path keeps only `usage`; `brief`, `turns`, `action_log`, `probes`, `final_timeline` are gone, so a $-charged trial shows an empty transcript; a factory-stage failure keeps no usage at all | `mass_trial.py` ~530–540 |
| A systematic taint shrinks n silently — closed (T054: the census names the class) | a `TaintError` record is re-stamped `terminal_reason="error"` and excluded from cells and contrasts; only `Provenance.failed_trials` counts it, without the reason | `mass_trial.py` ~529, ~593 |
| The cost ceiling overshoots by up to `concurrency` — closed (box 4) | `stop()` is checked at submission; spend advances only when a unit lands, in submission order, so one slow early trial defers all accounting | `mass_trial.py` ~573–584; `experiment.py` ~2741 |
| Probe spend never trips the token ceiling — as designed | `meter_tokens` subtracts `_probe_tokens`; `every_turn` probes on a long grid spend past the ceiling until the USD ceiling catches it between trials | `llm_agent.py` ~905 |
| The constitution vanishes without a trace — closed (T054, `TrialRecord.forgetting`) | stored as history turn −1, it is always inside the displaced set at `compact_at`; an unusable summary replaces it with a stub; a finite `memory=k` window drops it with no field on the record saying when | `llm_agent.py` ~751, ~826, ~852–876 |
| A molecule and a reaction sharing an id — closed (T054: refused) | `build_name_map` writes molecules then reactions into one dict; the reaction wins silently and `structural_text` maps the surface name back to the wrong entity | `naming.py` ~112–118 |
| The taint audit has blind spots — closed (T054) | returns `()` when the agent exposes no `prompt_texts`; secrets are molecules and `AnswerObjective.key` leaves only, so hidden reaction structure and `OutcomeObjective` targets are never scanned | `runner.py` ~907–914 |
| A clamp note for a compacted turn is dropped — as designed | `notice()` returns silently when no history entry matches `outcome.turn` | `llm_agent.py` ~769 |
