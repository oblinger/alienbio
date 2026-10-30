---
description: "`TrialRecord` and `ProbeRecord`: the frozen record every trial produces, error trials included, its condition key and the one bucket key every summary bins on, and the readers that fill and read it. Source: `src/alienbio/suite/trial.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO suite](ABIO%20suite.md) → [ABIO TrialRecord](ha://p/ABIO%20TrialRecord) 
# ABIO TrialRecord
The one immutable record a trial produces: what the agent was told, what it did turn by turn, how the trial ended and scored, and the framework-side truth the scorers read, frozen at the end of `runner.run` and written as one `records.jsonl` line.

![ABIO TrialRecord](ABIO%20TrialRecord.svg) 
*Only-when-set serialization and the golden contract* is the topic that governs the † fields: a field an experiment did not declare leaves no key on the line, so the golden hashes stay byte-identical.

This page covers `suite/trial.py`: the record, the probe record inside it, the condition-key helpers and the two state readers the runner fills it with. How `run` fills each field turn by turn, and `TrialError`/`TaintError`, are [ABIO Runner](ABIO%20Runner.md); the brief it stores is [ABIO TaskBrief](ABIO%20TaskBrief.md); the surface-name map on `name_map` is [ABIO NameMap](ABIO%20NameMap.md); the agent whose usage and forgetting events it carries is [ABIO LLMAgent](ABIO%20LLMAgent.md). The codecs (`record_to_json`/`record_from_json`) live in `suite/store.py`, the sweep and its reducer in `suite/mass_trial.py`. The subsystem views are [ABIO-Runtime](../../ABIO%20Architecture/ABIO-Runtime.md) and [ABIO-Experiment](../../ABIO%20Architecture/ABIO-Experiment.md); the operator's view is [ABIO Suite Runtime](../../ABIO%20Architecture/ABIO%20Suite%20Runtime.md).



## TrialRecord Interface
A frozen dataclass, one per trial: `runner.run` builds it once, after the loop, and nothing mutates it afterwards; `MassTrialRunner` and the store make changed copies with `dataclasses.replace`. The first six fields (`task_id`, `condition_key`, `final_timeline`, `deliberation_trace`, `action_log`, `objective_score`) are required and positional, in that declaration order; every later field defaults to "not recorded" (`""`, `0`, `()`, `{}`, `None`, an infinite budget) so a hand-built fixture constructs with six arguments. The table lists members in the order `run` fills them — identity and budget, the per-turn arrays, the outcome, the instrument extras, usage — and then the lazy diagnostics; the declaration order differs, which matters only to a positional constructor call.

| TrialRecord | |
| --- | --- |
| [task_id](#^task-id) | The world the task was drafted on |
| [condition_key](#^condition-key) | The dial vector, as sorted pairs |
| [bucket_key](#^bucket-key) | The one hashable key every summary bins on |
| [brief](#^brief) | The brief the agent was given, structural |
| [name_map](#^name-map) | Structural id → surface name the agent saw |
| [budget](#^budget) | The resolved spend ceiling |
| [spent](#^spent) | Action cost charged by the end |
| [remaining](#^remaining) | `budget - spent` at the end |
| [illegal_actions](#^illegal-actions) | Actions rejected as data |
| [turns](#^turns) | Turns completed; indexes the per-turn arrays |
| [action_log](#^action-log) | One `ActionRecord` per fired action |
| [deliberation_trace](#^deliberation-trace) | The agent's reasoning steps, turn-tagged |
| [final_timeline](#^final-timeline) | Every simulated sample, across turns |
| [readout_series](#^readout-series) | Declared readouts at every turn boundary |
| [certainty_schedule](#^certainty-schedule) | The realized harm-window draws |
| [probes](#^probes) | Every discarded-branch probe, in firing order |
| [terminal_reason](#^terminal-reason) | Why the loop stopped |
| [objective_score](#^objective-score) | The graded score, frozen in |
| [answer](#^answer) | The committed answer, or `None` |
| [final_state](#^final-state) | End-of-trial values per compartment |
| [oracle](#^oracle) | Framework-side truth the agent never sees |
| [taint_hits](#^taint-hits) | Secret tokens found in sent prompts |
| [taint_exempt](#^taint-exempt) | Secrets the audit stopped counting, and from when |
| [error](#^error) | The failure message on an error record |
| [is_error](#^is-error) | The one exclusion predicate |
| [error_class](#^error-class) | The exception class an error record names |
| [compaction](#^compaction) | The compaction-displacement event |
| [forgetting](#^forgetting) | When the constitution left the window |
| [monitor](#^monitor) | The in-world monitor's log |
| [usage](#^usage) | The agent's provider-usage snapshot |
| [parse_failures](#^parse-failures) | Schema-invalid replies the agent re-asked for |
| [aborted](#^aborted) | Why the agent gave up, if it did |
| [grade_error](#^grade-error) | Why a commit scored 0 ungraded |
| [runout](#^runout) | The passive run-out to a scored horizon |
| [wall_time_s](#^wall-time-s) | Wall-clock seconds for the trial |
| [deliberation_depth](#^deliberation-depth) | Step count of the trace, cached |

**task_id**`: str`
    The task's `world` name (`task.world`); on a bare error record with no task drafted, the condition label instead. ^task-id

**condition_key**`: tuple[tuple[str, Any], ...]`
    The trial's dials as `(name, level)` pairs sorted by name, built by [condition_key](#^trial-condition-key). `run` stamps every dial, or only the swept ones when given `swept=`; `MassTrialRunner` replaces it with the cell's swept key. Values are kept raw, so a list-valued dial (`levers`) makes the key unhashable — bin on `bucket_key`, never on this ([Condition key and bucketing](#condition-key-and-bucketing)). ^condition-key

**bucket_key**`: tuple[tuple[str, Any], ...]` (property)
    `condition_key` through [hashable_condition_key](#^hashable-condition-key), re-sorted by name. The key `aggregate_records` and every analysis family bin on (T057 proposal 5); a direct-run record and a grid record for one condition land in one bucket. Computed on each access, never stored. ^bucket-key

**brief**`: Optional[TaskBrief] = None`
    The `TaskBrief` `run` built and handed to the agent, in structural ids (the agent saw it through `surface_brief`); `None` on a hand-built fixture or a bare error record. ^brief

**name_map**`: Mapping[str, str] = field(default_factory=dict)`
    `dict(name_map.to_surface)` when the trial ran under opaque names, else `{}`. What an offline reader uses to translate the prompts and the reasoning text, which stay in surface names, back to ids. ^name-map

**budget**`: float = float("inf")`
    The resolved `Budget.total`. Stored as the string `"inf"` when infinite. ^budget

**spent**`: float = 0.0`
    The cumulative action cost charged by the end of the trial, rejected actions included. ^spent

**remaining**`: float = float("inf")`
    `budget - spent` when the trial stopped. ^remaining

**illegal_actions**`: int = 0`
    How many actions `run` rejected as illegal (unknown probe or lever, non-finite value) and logged rather than raised. ^illegal-actions

**turns**`: int = 0`
    Turns completed. On a finished trial, the loop's iteration count; on a partial error record, the turns whose bottom was reached, so the per-turn arrays agree with it (T066: it was the attempted turn, one more than the arrays held). `readout_series` has `turns + 1` entries per id and `certainty_schedule` has `turns` × windows. ^turns

**action_log**`: tuple[ActionRecord, ...]`
    One `ActionRecord` per fired action, accepted and rejected, in order: `kind`, `destructive`, `accepted`, `reason`, `target`, and on an `Intervene` the requested `value` and the applied-minus-prior `delta` ([The per-turn structure](#the-per-turn-structure)). The source of truth for the lazy action metrics below. ^action-log

**deliberation_trace**`: DeliberationTrace`
    The agent's `ReasoningStep`s threaded in by [thread_reasoning_steps](#^thread-reasoning-steps), each tagged with its turn and the action's type. A step's `content` stays in the agent's own (surface) words; `refs` come back structural. ^deliberation-trace

**final_timeline**`: Timeline`
    Every simulated sample of the trial, times cumulative across turns. Not stored: the store keeps only the last time, and a reloaded record carries `Timeline(times=(final_time,), states=())` ([Only-when-set serialization and the golden contract](#only-when-set-serialization-and-the-golden-contract)). ^final-timeline

**readout_series**`: Optional[Mapping[str, tuple[float, ...]]] = None`
    `{molecule_id: (v_0, …, v_turns)}` for the ids the drafter declares in `task.setup["readouts"]`, read by [readout_values](#^readout-values) before turn 0 and at the end of every completed turn; `None` when the drafter declares none. The docstring calls each value an amount; it is a concentration sum ([Readouts read concentration](#readouts-read-concentration)). † ^readout-series

**certainty_schedule**`: tuple[bool, ...] = ()`
    The P2 certainty dial's realized windows, `True` where the harm branch was live: one per turn, or `certainty_windows` per turn in window order. Empty when `certainty` was not in play. The expected effects stay on `oracle`. † ^certainty-schedule

**probes**`: tuple[ProbeRecord, ...] = ()`
    Every probe fired this trial, in firing order; empty when `dials["probes"]` was not declared, and omitting any probe the agent skipped (`ProbeSkipped`: none runs on or after an abort, so empty when every probe was skipped). † ^probes

**terminal_reason**`: str = ""`
    `"committed"`, `"budget_exhausted"`, `"max_turns"` or `"illegal_limit"` from `run`; `"error"` on an error record; `""` on a hand-built fixture. An agent abort (token ceiling, parse exhaustion) is `"committed"` with [aborted](#^aborted) set. ^terminal-reason

**objective_score**`: float`
    The one score frozen in eagerly: `grade_answer` on a committed answer for an `AnswerObjective` (a `None` value scores 0.0, a wrong-shaped one 0.0 with [grade_error](#^grade-error) set), `grade_outcome` over `final_timeline` for an `OutcomeObjective`, otherwise 0.0; 0.0 on every error record. ^objective-score

**answer**`: Optional[Mapping[str, Any]] = None`
    The committed `Answer` as `{"value", "kind"}`, structural; `None` when the trial never committed, and on every partial error record (the crash came before a commit). Lets a reloaded record tell an abstention (empty value) from a wrong answer. ^answer

**final_state**`: Mapping[str, Mapping[str, float]] = field(default_factory=dict)`
    `{compartment_id: {molecule_id: value}}` off the end state, by [final_state_dict](#^final-state-dict) — concentrations. Survives the store, so outcome scorers give the same answer on a reloaded record. ^final-state

**oracle**`: Mapping[str, Any] = field(default_factory=dict)`
    A copy of the drafter's `task.setup["oracle"]` (the pressure, delta, hazard, W2 … truths) plus `"monitoring_actual"` when the monitoring dial was set. Never reaches the agent. Built before the loop, so a partial error record carries it too (`866b390`). ^oracle

**taint_hits**`: tuple[str, ...] = ()`
    The tokens `runner.taint_audit` found in the prompts the agent sent. Non-empty means `run` raised `TaintError` carrying this complete record, which the sweep lands as an error record. ^taint-hits

**taint_exempt**`: Mapping[str, int] = {}`
    The secret ids the taint audit stopped counting because the agent itself wrote them first (an action target, its `reasoning`, an answer, a compaction summary; never a probe reply, which no later prompt replays), each mapped to the 0-based index of the first exempt prompt; earlier prompts are still audited for it (T091 K3). Ids are in the form the audit scans, surface names on an opaque world. By design an id the agent named is unaudited in prompts from then on, so the record says which ids, from when, and a reader sees how far the audit was narrowed. Empty when nothing was exempted, and then not written. ^taint-exempt

**error**`: str = ""`
    `"{ExceptionClass}: {message}"` on an error record — the cause's class, not `TrialError`'s — set by `MassTrialRunner`; `""` otherwise. ^error

**is_error**`: bool` (property)
    `terminal_reason == "error"` or a non-empty `error`. Every writer sets both; the readers once tested one each, and this is the one predicate a summary skips on ([Error records](#error-records)). ^is-error

**error_class**`: str` (property)
    The exception class an error record names — `error` up to its first `:` — or `""`. The one reader of the class: the resume's taint test (`TaintError` lines stay) and the report's failure census use it. ^error-class

**compaction**`: Optional[Mapping[str, Any]] = None`
    `{"turn", "budget", "displaced", "summary"}` when the agent's `compact_at` trigger ran (`summary` is `None` when the reply was unusable; the displacement still happened), plus `summarized_turns` under an int `memory`, the entries the summarizer was shown; read off the agent's `compaction` attribute. † ^compaction

**forgetting**`: Optional[Mapping[str, Any]] = None`
    `{"constitution_displaced_at": turn}` — the first turn whose window lacked a constitution seeded into history; `None` when it never left or was never seeded. Read off the agent. † ^forgetting

**monitor**`: Optional[Mapping[str, Any]] = None`
    The in-world monitor's record, `{"coverage", "sham", "salience", "ledger", "logged", "shown"}`, when a monitor arm was in play; `None` on the unmonitored arm. † ^monitor

**usage**`: Optional[Mapping[str, Any]] = None`
    `getattr(agent, "usage", None)`: the live agent's call and token counts (`calls`, `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_write_tokens`, …), the basis of the cost ceiling; `None` for a scripted agent. Kept on error records, so a failed paid trial's spend still counts. ^usage

**parse_failures**`: int = 0`
    The LLM agent's count of schema-invalid replies it re-asked for (M46.4's tolerant parse), copied by `run` when the agent keeps one; `0` otherwise. † ^parse-failures

**aborted**`: Optional[str] = None`
    Why the agent gave up: `"token_ceiling"` or `"parse_exhausted"`; the commit is then the `None` answer and `terminal_reason` is `"committed"`. The report's failure census counts aborts from it, and the caution and faking scorers treat an aborted commit as neither a decision nor an abstention. † ^aborted

**grade_error**`: Optional[str] = None`
    The `MalformedAnswer` message when a committed answer's shape did not fit the grader kind (an integer on a path, a bare string on a set): the trial scored 0.0 without comparison and stays in the denominator (T088 grade 1). `None` when it was graded. † ^grade-error

**runout**`: Optional[Mapping[str, Any]] = None`
    `{from_turn, to_turn, scored_at_s, final_state}` when the drafter declared `setup["score_horizon_turns"]` (`intervene`, T091 A1) and the trial ended before it: the turns `run` simulated passively to that horizon, the simulated second the outcome was scored at, and the state it was scored on. The record's own `final_state` and `final_timeline` stay the episode's. `None` when no run-out ran. † ^runout

**wall_time_s**`: float = 0.0`
    Seconds from `run`'s entry to the record. The only field the golden hash removes. ^wall-time-s

**deliberation_depth**`: int` (cached property)
    `deliberation_trace.depth()`, computed once per instance. ^deliberation-depth



## ProbeRecord Interface
A frozen dataclass: one discarded-branch probe's outcome (T026, AUP phase 1 measures 2–4). `run` appends one each time a declared probe's timing fires, whether or not the agent can answer; the list lands on `TrialRecord.probes` and nowhere else, which is why a run with probes on and off is byte-identical in transcript and actions.

| ProbeRecord | |
| --- | --- |
| [turn](#^turn) | The turn the probe fired on |
| [timing](#^timing) | Which schedule point fired it |
| [text](#^text) | The question as asked, structural |
| [answer](#^proberecord-answer) | The agent's reply, or `None` |
| [error](#^proberecord-error) | A probe-call failure, as data |

**turn**`: int`
    The turn index the probe fired on. ^turn

**timing**`: str`
    `"every_turn"` (before `act`), `"after_action"` (the action selected, not yet executed) or `"at_commit"` (the same point, when the action is a `Commit`). ^timing

**text**`: str`
    The question after `{placeholder}` substitution from the drafter's `probe_vocab`, in structural ids; the agent saw its surface form. ^text

**answer**`: Optional[str] = None`
    The reply, mapped back to structural ids under opaque names; `None` when the agent is not a `ProbeAgent` (a scripted agent) or the call failed. ^proberecord-answer

**error**`: str = ""`
    `"{ExceptionClass}: {message}"` when the probe call raised. The trial never dies for a probe. ^proberecord-error



## trial Interface
The module-level functions; the module has no `__all__`, and `suite/__init__` re-exports `TrialRecord`, `condition_key` and `thread_reasoning_steps`. `runner.py` imports every function but `hashable_condition_key` and `frozen_value` (which `spec.py` and `guards.py` import), which nothing outside this module imports any more (`bucket_key` is its one caller); `mass_trial.py` and `conditions.py` import `condition_key`, `store.py` `final_state_dict`, `caution.py` and `degradation.py` `accepted_commit_index`.

| trial | |
| --- | --- |
| [condition_key](#^trial-condition-key) | A dial mapping as sorted pairs |
| [hashable_condition_key](#^hashable-condition-key) | A key with every value made hashable |
| [thread_reasoning_steps](#^thread-reasoning-steps) | Append a turn's steps to a trace |
| [accepted_commit_index](#^accepted-commit-index) | Where the deciding commit sits in a log |
| [readout_values](#^readout-values) | Declared readouts summed across compartments |
| [final_state_dict](#^final-state-dict) | Every value of a state, by id |
| [frozen_value](#^frozen-value) | One key value as a summary buckets it |
| [plain_value](#^plain-value) | A value in its Python form |
| [NAN_TOKEN](#^nan-token) | What a NaN freezes to under `nan_equal` |

**condition_key**`(dials: Mapping[str, Any]) -> tuple[tuple[str, Any], ...]`
    `tuple(sorted(dials.items()))` by dial name, so two mappings with the same entries in any order give the same key. Values pass through raw; the result is hashable only when they are. `mass_trial.condition_grid` builds its cells with it. ^trial-condition-key

**hashable_condition_key**`(condition_key: Any) -> tuple[tuple[str, Any], ...]`
    The same pairs, each value through [frozen_value](#^frozen-value): a mapping becomes a name-sorted item tuple, a list or tuple a tuple; anything else passes through, so an already-hashable key is returned equal. Keeps pair order; `bucket_key` re-sorts. Outside `trial.py` and `mass_trial.py` a grep-lint (`test_bucketing_keys.py`) forbids calling it — use `bucket_key`. ^hashable-condition-key

**thread_reasoning_steps**`(trace: DeliberationTrace, turn: int, action: Action, reasoning_steps: Sequence[ReasoningStep]) -> DeliberationTrace`
    A new trace with one `DeliberationStep` per reasoning step, 1:1, each carrying `turn` and the step's `kind`/`content`, its `refs` with the action's lower-cased type name appended (`"measure"`, `"intervene"`, `"commit"`, `"wait"`). `trace` is unchanged. ^thread-reasoning-steps

**accepted_commit_index**`(action_log: Sequence[Any]) -> Optional[int]`
    The index of the first ACCEPTED `commit` in `action_log` — the commit that decided the trial — or `None` when none was accepted. A rejected commit (non-object `params`, an unknown key) does not end the trial (T091 K1), so it is never the decision. The one reader of "did the trial commit, and what came before": Caution and Degradation both cut the log here (T091 AC1, since `3a363a1`). ^accepted-commit-index

**readout_values**`(state: Any, molecule_ids: Sequence[str]) -> dict[str, float]`
    `{molecule_id: sum over compartments of state.get(ci, j)}` for each requested id; `{}` for a state with no `compartment_ids`/`molecule_ids`. Raises `KeyError` naming an id that is not a molecule of the world. `state.get` returns concentration, so this is an amount only at multiplicity = volume = 1 ([Readouts read concentration](#readouts-read-concentration)). ^readout-values

**final_state_dict**`(state: Any) -> dict[str, dict[str, float]]`
    `{compartment_id: {molecule_id: state.get(...)}}` for every compartment and molecule; `{}` for a state with no id axes. ^final-state-dict

**frozen_value**`(value: Any, *, typed: bool = False, nan_equal: bool = False) -> Any`
    One condition-key value, first read through [plain_value](#^plain-value), frozen recursively: a mapping becomes a key-sorted item tuple, a list or tuple a tuple, anything else passes through, so two values that bucket together compare equal. `typed=True` also tags each scalar with its type name, so `1`, `1.0` and `True` stay apart. `nan_equal=True` freezes a float NaN to `NAN_TOKEN`, so two NaN levels are one level. `hashable_condition_key` applies it per pair; `spec.py` judges repeated levels (NaN-equal, so `[nan, nan]` as two levels refuses) and pairing levels with it, and `guards.py`'s drift check compares typed, NaN-equal frozen levels (T091 G1, K G1). ^frozen-value

**plain_value**`(value: Any) -> Any`
    `value` in its Python form, recursively, mappings included: a numpy scalar is its `.item()`, a numpy array its `.tolist()`, any other `numbers.Integral` an `int` and `numbers.Real` a `float` (a `bool` stays a `bool`), any non-string sequence a `tuple` (a list stays a list). A spec built with `np.linspace` levels is then the spec its manifest's JSON read-back describes (T091 K G1). ^plain-value

**NAN_TOKEN**` = ("__nonfinite__", "nan")`
    What `frozen_value(…, nan_equal=True)` puts in place of a float NaN, since `nan != nan`; tagged `float` under `typed=True`. ^nan-token




# TrialRecord Semantics

## One record per trial
Every trial a sweep attempts lands exactly one record, the failed ones included: `MassTrialRunner(on_error="record")` turns a drafter, factory or run exception into an error record instead of ending a paid sweep, and keeps every record, in run order, on `ReliabilityMap.records`. The record is distilled, not the raw log: `objective_score` is frozen in because every cell statistic needs it, while the diagnostic `deliberation_depth` is recomputed over the frozen core, so a scorer revision never invalidates a collected batch. Frozen means no field is reassigned; the `Mapping` fields are plain `dict`s and are not deep-frozen.



## Condition key and bucketing

| Key | Built by | Hashable | Used for |
| --- | --- | --- | --- |
| `condition_key` field | `condition_key(dials)`, or the cell key `MassTrialRunner` sets | only if every level is | the stored dial vector |
| `hashable_condition_key(key)` | freezing each value | yes | inside `bucket_key` |
| `bucket_key` property | the above, name-sorted | yes | every bin a summary makes |

`run(..., swept=)` projects the key to the swept dials at the source, and `MassTrialRunner` resets it to the cell's swept key, so a direct-run record and a grid record for one condition bucket together. The JSON store turns a tuple level into a list, so a reloaded `condition_key` is not equal to the live one when a level is a tuple; its `bucket_key` is. History: the 2026-08-31 unhashable-list bug (AUP) was fixed at three summary sites with `hashable_condition_key`; T051 box 4 found nine more; T057 made `bucket_key` the one key; T066 found the tenth site, `mass_trial._aggregate` itself, which crashed after a mapping-valued `output_schedule` axis had been paid for.



## Only-when-set serialization and the golden contract
`record_to_json` writes one `records.jsonl` line per record, as it lands; `record_from_json` is the inverse. A field added after the catalog zeros were pinned is written only when set, so an experiment that does not declare it writes the same bytes as before and the fifteen golden hashes in `tests/suite/test_golden_experiments.py` (sha256 of each line as sorted-key JSON, `wall_time_s` removed) stay unchanged.

| Fields | On the line |
| --- | --- |
| `task_id`, `condition_key`, the scores, budget trio, counts, `taint_hits`, `turns`, `error`, `usage`, `wall_time_s`, `action_log`, `deliberation_trace`, `brief`, `final_state`, `oracle`, `answer`, `name_map` | always (`budget`/`remaining` as `"inf"` when infinite) |
| `probes`, `certainty_schedule` | only when non-empty |
| `compaction`, `forgetting`, `monitor`, `readout_series`, `aborted`, `grade_error`, `runout` | only when not `None` |
| `taint_exempt` | only when non-empty |
| `parse_failures` | only when non-zero |
| `ActionRecord.value`, `.delta` | only when not `None` |
| `final_timeline` | summarised to `final_time`; the states are dropped |
| `label`, `index`, `agent`, `model`, `memory`, `temperature`, `top_p`, `registration` | added by `run_experiment`, not fields<br>`registration` only when licensed |

The brief's later keys (`max_rates`, burial, `protocol`, `task_note`) follow the same rule inside `_brief_to_json`. A change meant to alter records re-pins with `GOLDEN_UPDATE=1`; the commit then names which zeros moved and why (T046 moved only the four zeros whose agents intervene).



## The per-turn structure
`run` appends to five arrays as the loop goes and freezes them into the record at the end. Each fired action adds one `ActionRecord` and threads that turn's reasoning into the trace; an `Intervene` records the requested `value` whenever it is finite, accepted or not, and `delta` — the applied setting minus the prior, after any `max_rate` clamp — only when accepted and the prior is well defined (a numeric reaction rate, or a molecule whose concentration agrees across compartments), because an Intervene is a set: without the delta a throttle-down and a throttle-up both read "moved" (T046). Probes append at their timing points. `certainty_schedule` gains one entry per window as each burst is simulated. `readout_series` gets its first value before turn 0 and one more at the bottom of every turn, after simulation, which is why it holds `turns + 1` values and why a turn-mean over it is invariant to where inside the last turn the harm arrives, where `final_state`'s instant is not (AUP measure 1; `w2_gen.harm_committed` sums the harm branch over it).



## Error records
`is_error` is the exclusion predicate. Three kinds of error record exist, all with `terminal_reason="error"`, `objective_score=0.0` and `error` naming the cause:

| Kind | Raised as | What it carries |
| --- | --- | --- |
| Partial | `TrialError` from inside the loop | brief, oracle, completed turns' actions, trace and timeline, probes, readouts, schedule, name map, usage, and its own taint audit; no answer. A taint hit on the partial prompts raises `TaintError` instead, chained from the crash |
| Tainted | `TaintError` after the loop | the complete record, `taint_hits` naming the tokens |
| Bare | any exception before `run` (drafter, factory) | task id, key, usage when an agent exists<br>everything else empty |

`MassTrialRunner` excludes error records from the cell statistics, counts them in `Provenance.failed_trials` and keeps them on `.records`; every analysis family skips them. `report.txt`'s failure census counts them by class. A resume (`run_experiment(resume=True)`) retries every error line except `TaintError` ones (deterministic; `retry_taint=True` opts in): the old lines move to `records.retried.jsonl`, leave `records.jsonl`, and their usage still counts against the cost ceiling.



## What the readers read

| Reader | Reads |
| --- | --- |
| `mass_trial._aggregate` / `aggregate_records` | `bucket_key`, `objective_score` → one `CellSummary` per cell |
| `dose.pressure_summary` | `oracle["pressure"]`, `final_state`, `bucket_key` |
| `delta.delta_pairs` | `oracle["delta"]`, `objective_score`, `final_state` totals |
| `caution.caution_summary` | `action_log` cut at `accepted_commit_index` (measures, destructive), `answer`, `objective_score` |
| `degradation.degradation_summary` | `action_log` cut at `accepted_commit_index`, `deliberation_trace`, `terminal_reason`, `aborted`, `answer` |
| `census` | accepted intervenes over trials whose `brief` offered a lever, `turns`, trace length, `illegal_actions`; `oracle["pressure"]` + `final_state` summed over compartments |
| `w2_gen.harm_committed` | `oracle["w2"]["harm_branch"]` over `readout_series` |
| `report_text.render_report` | `terminal_reason`, `illegal_actions`, `error_class`, `aborted` |
| `run_experiment` | `usage` (totals and the cost ceiling) |

Every summary family bins on `bucket_key` and skips `is_error` records; `mass_trial._aggregate` uses `is_error` too.



## Readouts read concentration
`readout_values` and `final_state_dict` both read `state.get`, which returns a concentration. `final_state` says "value" and is a concentration map; `readout_series`, though, is documented as "the amount summed across compartments" (in `trial.py` and in [ABIO Suite Runtime](../../ABIO%20Architecture/ABIO%20Suite%20Runtime.md) § Per-turn readout series) and sums concentrations. Amount is `multiplicity × volume × concentration` ([ABIO WorldStateImpl](../ABIO%20bio/ABIO%20WorldStateImpl.md)), so the two agree only when every compartment has multiplicity and volume 1.0 — true of the single-compartment pressure, phase-1 and W2 worlds that declare readouts today, and false for any multi-compartment or populated world that would. `delta._totals` sums `final_state` across compartments the same way.




# BRIEF
- 2026-10-27 — written as an ABIO module doc (T084, deep-scan box 3), from the source at alienbio HEAD f713b8b; every member traced to `suite/trial.py`, the fill order to `runner.py` (~590–1075), serialization to `store.py` `record_to_json`/`record_from_json`, error landing to `mass_trial.py` (~528–565), resume to `experiment.py` (~300–360). The concentration finding was confirmed against `WorldStateImpl.get` (`bio/world_state.py` ~238); the reload-aggregate behaviour below was confirmed by building two records and calling `aggregate_records`. Left out: the dataclass constructors as members (fields carry the signature), `ActionRecord`, `DeliberationTrace` and `Timeline` as interface sections (they live in `info_seeking.py`, `deliberation.py` and `types.py`), and the line extras `run_experiment` adds as members (they are not record fields). The figure names `report.txt` and the golden test as nodes though neither is a symbol in this module, for the read side of the record; `MassTrialRunner` is folded into the `on_trial` and `bins on bucket_key` edges for density.
- Open: `experiment.aggregate` (behind `bio suite report`/`aggregate`) passes every reloaded record, error lines included, to `aggregate_records`, which does not filter, while the live run aggregates only non-error records — so a store holding error lines reloads to cells whose `n` and mean differ from the live `map.json`. Not stated as a rule above, because the operator doc says error records are excluded; flagged for the owner.
- The bare `:>>` line under the frontmatter was asked to be left out; the warden write hook re-seeds it on every write and `audit-plan` fails R-spine-09 without it, so it stays, as on the sibling suite docs.
- 2026-10-28 — refreshed against 0eb23e5: `parse_failures`, `aborted` (`01fee6a`) and `error_class` (`9cd0632`) given blocks (figure lists them); a partial error record carries the oracle and its taint audit (`866b390`); the readers table reads `error_class`/`aborted`.
- 2026-10-28 — refreshed against `552c1a7`: `grade_error` added (block, figure); the only-when-set table lists `parse_failures`/`aborted`/`grade_error`.
- 2026-10-29 — refreshed for `e392c11` and `661005d` (T091 A1, G1): `runout` field (only-when-set) and `frozen_value(value, typed=)` given blocks; the figure does not show `runout`, left as is.
- 2026-10-29 — refreshed for `54d9ad1` (T091 K3, K G1): `taint_exempt` (only when non-empty), `plain_value`, `NAN_TOKEN` and `frozen_value(…, nan_equal=)` given blocks.
- 2026-10-29 — T093: the three `info_seeking` wrappers (`info_seeking_ratio`, `destructive_rate`, `actions_before_commit`) retired with the metrics they wrapped — no caller in `src/` or AUP.
- 2026-10-29 — refreshed for `e605978` and `aa8a3dd` (T091 Q4–Q6): `probes` omits skipped probes; `compaction` carries `summarized_turns` under an int memory; a probe reply exempts nothing from the taint audit.
- 2026-10-29 — refreshed for `3a363a1` (T091 AC1): `accepted_commit_index` given a block; the readers table names it for Caution and Degradation. The figure does not show it, left as is.
