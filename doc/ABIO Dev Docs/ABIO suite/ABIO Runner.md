---
description: "`runner`: the live agent turn loop — `run` (observe, act, validate, simulate, record), `Budget`, `TrialError`, `TaintError`, `audit_prompts`. Source: `src/alienbio/suite/runner.py`."
---
:>> [[ABIO]] → [[ABIO Dev Docs]] → [ABIO Runner](ha://p/ABIO%20Runner) 
# ABIO Runner
The agent turn loop: `run` plays one agent against one drafted world, turn by turn, and returns one frozen `TrialRecord` — every action it took, accepted or rejected, every probe answer, the trajectory and the score.

![[ABIO Runner.svg|2400]] 
*Rejection as data* is the topic that governs the validate-action node (reject, clamp, negative setpoint); *The taint audit* governs `audit_prompts` and `TaintError`.

`suite/runner.py` has no primary class: its export is `run`, plus the spend cap `Budget`, the two exceptions a trial can end in, and the prompt scanner `audit_prompts`. This page covers the loop and those four. The brief the agent is handed is built in `suite/brief.py` (`build_brief`, `TaskBrief`, `Affordances`), the surface-name boundary in `suite/naming.py` (`NameMap`, `OpaqueAgent`, `token_pattern`), the record in `suite/trial.py`, the agent protocols and action types in `suite/agent.py`, the live model in `suite/llm_agent.py`, and the grid driver that calls `run` per trial in `suite/mass_trial.py`. Each turn's physics is one `verify.simulate` burst over [[ABIO WorldSimulatorImpl]], reading and writing [[ABIO WorldStateImpl]] snapshots of an [[ABIO WorldImpl]]. The subsystem view is [[ABIO-Runtime]]; the operator's description is [[ABIO Suite Runtime]].



## Budget Interface
A frozen dataclass: the cumulative spend cap `run` compares its per-action cost against, resolved from `dials["budget"]` by `from_dial`. Spend is the opaque per-verb cost of `brief.DEFAULT_ACTION_COSTS` (`measure` 1.0, `intervene` 5.0, `commit` and `wait` 0.0), so the one implemented unit, `"turns"`, meters action cost, not turn count ([[#Budget and what ends an episode]]). Re-exported from `alienbio.suite`; `brief.py` imports it for the brief's `budget_total`/`budget_unit`.

| Budget | |
| --- | --- |
| [[#^total\|total]] | The spend ceiling; infinite by default |
| [[#^unit\|unit]] | What the ceiling meters; only `"turns"` is built |
| [[#^unlimited\|unlimited]] | Whether the budget never stops the loop |
| [[#^exhausted\|exhausted]] | Whether a spend has reached the ceiling |
| [[#^from-dial\|from_dial]] | Resolve a `dials["budget"]` entry |

**total**`: float = float("inf")`
    The cumulative-cost ceiling. `run` stops with `"budget_exhausted"` at the bottom of the first turn whose running spend is `>= total`, and stamps `total`, the spend and `total - spent` on the record as `budget`, `spent` and `remaining`. ^total

**unit**`: str = "turns"`
    Checked in `__post_init__`: `"sim_steps"`, `"deadline"` and `"opportunity_cost"` raise `NotImplementedError` (documented future units), anything else outside `{"turns"}` raises `ValueError`, so no caller silently gets turns semantics under another unit's name. ^unit

**unlimited**`: bool` (property)
    `True` when `total` is infinite. ^unlimited

**exhausted**`(spent: float) -> bool`
    `spent >= total`. ^exhausted

**from_dial**`(value: Any) -> Budget` (static)
    A `Budget` passes through; `None` gives the unlimited default; a string must be a [[#^budget-ladder|BUDGET_LADDER]] level name, else `ValueError`; anything else becomes `Budget(total=float(value))`, so the bare-number dial (`{"budget": 3.0}`) still works. ^from-dial



## TrialError Interface
The exception `run` raises when an exception escapes the turn loop and the partial record audits clean: a provider failure on turn 3, a simulator `ValueError`. It carries the partial record built from the loop's locals at the moment of failure, so `MassTrialRunner(on_error="record")` lands what the paid trial did before it died, under the cause's own type name ([[#Errors and the partial record]]). Raised `from` the cause.

| TrialError | |
| --- | --- |
| [[#^record\|record]] | The partial `TrialRecord` |
| [[#^cause\|cause]] | The original exception |

**record**`: TrialRecord`
    Built from everything the loop reached: completed turns' timeline, action log and deliberation trace, the brief, probes, surface-name map, usage, readout series and certainty schedule; `terminal_reason="error"`, `objective_score=0.0`, `turns` the count of turns completed, not attempted. It is taint-audited before the raise: a hit raises `TaintError` instead; an audit that itself fails leaves this `TrialError` standing with a note (`__notes__`) naming the audit failure. ^record

**cause**`: BaseException`
    The exception that escaped the loop; the message is `"{type(cause).__name__}: {cause}"`, and `mass_trial.py` writes that same string to the record's `error`. ^cause



## TaintError Interface
The exception `run` raises when a record's `taint_hits` is non-empty, complete or partial: a prompt actually sent to the model named one of the trial's secrets ([[#The taint audit]]). It carries the full record, so a sweep lands it as a visible error trial rather than keeping a tainted number or crashing.

| TaintError | |
| --- | --- |
| [[#^tainterror-record\|record]] | The complete record, `taint_hits` naming the tokens |

**record**`: TrialRecord`
    The finished record, score and all, or the partial record of a trial that died after sending a tainted prompt (`terminal_reason="error"`, raised `from` the crash); the message lists `record.taint_hits`. ^tainterror-record



## runner Interface
The module-level exports. `alienbio.suite` re-exports `run`, `Budget` and `BUDGET_LADDER`; `mass_trial.py`, `experiment.py`, `drafters.py`, `spec.py` and `guards.py` import `run`; `degradation.py` imports `BUDGET_LADDER`. Two private names are imported from outside: `drafters.py` imports `_resolve_int_dial` (the positive-int dial reader `run` uses for `max_turns`, `sim_steps` and `sample_every`), and `tests/suite/test_probes.py` imports `_parse_probes`; `tests/suite/test_hidden_pool_levers.py` imports `narrow_observation` through this module, where it is only an import from `suite/observation.py`.

| runner | |
| --- | --- |
| [[#^run\|run]] | Play one agent against one world; one record |
| [[#^audit-prompts\|audit_prompts]] | Scan the prompts an agent sent for secrets |
| [[#^budget-ladder\|BUDGET_LADDER]] | Named budget levels, unlimited down to 4 |
| [[#^probe-timings\|PROBE_TIMINGS]] | The three probe schedule points |
| [[#^default-assay-kill\|DEFAULT_ASSAY_KILL]] | Share of the culture a destructive assay kills |

**run**`(world: WorldImpl, task: TaskInstance, agent: Agent, dials: Mapping[str, Any], seed: Seed, *, sim_cfg: SimConfig = SimConfig(steps=10, sample_every=10), max_turns: int = 50, assay_kill: float = DEFAULT_ASSAY_KILL, illegal_action_limit: int = 10, illegal_action_cost: Optional[float] = None, swept: Optional[Collection[str]] = None) -> TrialRecord`
    Narrows the turn-0 truth, builds the brief, wraps the agent for opaque names when asked, then loops turns ([[#One turn of the loop]]) until a `Commit`, the illegal-action limit, budget exhaustion or `max_turns`; grades, audits the prompts, and returns the record. `sim_cfg`, `max_turns` and `assay_kill` are defaults a condition's dials override (`max_turns`, `sim_steps`, `sim_dt`, `sample_every`, `assay_kill`); `illegal_action_cost`, when set, is what a rejected action costs instead of its verb's cost; `swept` projects the record's `condition_key` to those dials only, the key a grid record carries. Never mutates `world`, its chemistry or its initial state, so it is deterministic in `(world, task, agent, dials, seed)`. Raises `ValueError` before turn 0 for a malformed dial (a non-positive-int episode dial, `assay_kill` outside `[0, 1]`, a bad `probes` list, a bad `task.setup["certainty"]`) or whatever `build_brief` refuses; `TrialError` for a failure inside the loop; `TaintError` for a tainted prompt. ^run

**audit_prompts**`(agent: Any, brief: TaskBrief, chemistry: ChemistryImpl, task: TaskInstance, name_map: Optional[NameMap] = None, probe_texts: tuple[str, ...] = ()) -> tuple[str, ...]`
    The sorted tokens among the trial's secrets that appear, as whole ids, in any of `agent.prompt_texts`. Returns `()` at once for an agent with no `prompt_texts` (every scripted agent); an `OpaqueAgent` forwards its inner agent's. What counts as a secret, what is exempt and how the match works are in [[#The taint audit]]. `run` calls it once, after the loop, with the declared probe texts; the tests call it directly. ^audit-prompts

**BUDGET_LADDER**`: Mapping[str, float]`
    `{"unlimited": inf, "20": 20.0, "12": 12.0, "8": 8.0, "4": 4.0}`: the level names [[#^from-dial|from_dial]] accepts, swept as an axis by the degradation experiments (`degradation.py`). ^budget-ladder

**PROBE_TIMINGS**`: frozenset = frozenset({"every_turn", "after_action", "at_commit"})`
    The `timing` values a `dials["probes"]` entry may name; anything else is refused before turn 0 ([[#Probes on discarded branches]]). ^probe-timings

**DEFAULT_ASSAY_KILL**`: float = 0.5`
    The default for `run`'s `assay_kill`: the factor `1 − assay_kill` by which an accepted destructive assay scales every concentration in every compartment ([[#The destructive assay]]). ^default-assay-kill




# Runner Semantics

## One turn of the loop
Before turn 0, `run` resolves the episode dials and the `Budget`, narrows the initial state to the first observation (then drops `task.setup["hidden_ids"]`), builds the brief from exactly that observation, builds a `NameMap` and wraps the agent in `OpaqueAgent` when `opaque_names_requested` says so, and calls `agent.begin(brief)` if the agent is a `SessionAgent`. It records the initial readouts. Each turn then runs these steps, in source order:

| Step | What happens | Source |
| --- | --- | --- |
| rebuild | a fresh `WorldImpl` from the current state, chemistry, flows and population laws | `_world_from_state` |
| observe | turn 0 reuses the first observation; later turns re-narrow, hidden set held, noise redrawn; `hidden_ids` dropped | `narrow_observation`, `project_observation` |
| monitor show | on a monitor `shows_turn`, the auditor block is appended as an extra observation entry | `monitor.auditor_block` |
| probe | `every_turn` probes fire | `_fire_probes` |
| act | `agent.act(observation)`; its reasoning steps are threaded into the trace | `thread_reasoning_steps` |
| probe | `after_action` probes fire, then `at_commit` ones if the action is a `Commit` | `_fire_probes` |
| validate | accept, reject or clamp, always logged | [[#Rejection as data]] |
| charge | verb cost, or `illegal_action_cost` on a reject | `_action_cost` |
| apply | accepted only: assay, `Intervene` lever, or store the `Commit` answer | `_chemistry_with_rate`, `_state_with_concentration` |
| notice | `agent.notice(ActionOutcome(...))` for a `SessionAgent` | `agent.ActionOutcome` |
| monitor log | on a monitor `logs_turn`, the ledger counts the action | `monitor.logs_turn` |
| simulate | one `sim_cfg` burst, or `windows` slices under the certainty dial; its end-state is the next state | `verify.simulate` |
| record | the readouts at the turn boundary | `trial.readout_values` |
| stop | `Commit`, then the illegal limit, then the budget | [[#Budget and what ends an episode]] |

`Measure` and `Wait` change nothing in the world; a `Wait`'s `duration` is not read, since every turn already plays one fixed burst. Time passes every turn whatever the agent did, rejected actions included. The persistent `chemistry` and `state` are only ever rebound to new objects, never mutated, which is what keeps two `run` calls on the same `world` independent. The timeline keeps every sample of every burst, dropping each later burst's first sample (it duplicates the previous turn's last), with times offset by the elapsed simulated time.

After the loop: the score is `grade_answer` for a committed `AnswerObjective` (0.0 when the committed value is `None`, the abort sentinel `LLMAgent` commits on a token ceiling or parse exhaustion), `grade_outcome` on the final timeline for an `OutcomeObjective` whether or not the agent committed, and 0.0 for an `AnswerObjective` that never committed. Then `audit_prompts`, then the oracle (`task.setup["oracle"]` plus the monitoring dial's actual side), then the record; a non-empty `taint_hits` raises `TaintError` instead of returning.



## Rejection as data
An illegal action never raises. It is logged as an `ActionRecord` with `accepted=False` and a `reason`, charged, reported to a `SessionAgent` through `notice`, and the turn still simulates; nothing in the world changes. The checks run in this order, the first that fails naming the reason:

| Action | Check | `reason` |
| --- | --- | --- |
| `Measure`, `params["assay"]` true | probe in `brief.affordances.assays` | `unknown assay '…'` |
| | probe is a reaction in this world | `assay '…' is allowlisted but not a reaction in this world` |
| `Measure` | probe in `brief.affordances.probes` | `unknown probe '…'` |
| `Intervene` | lever in `brief.affordances.levers` | `unknown lever '…'` |
| | lever is a reaction or a molecule here | `lever '…' is allowlisted but not resolvable in this world` |
| | value is a finite real, not a `bool` | `non-finite value …` |
| | value `>= 0` | `negative value …` |
| `Commit`, `Wait` | none | |
| any other type | none passes | `unknown action type '…'` (charged only `illegal_action_cost`: an unknown verb has no normal cost) |

The affordances are read off the structural brief, before any surface naming, and `OpaqueAgent` has already translated the agent's surface names back to structural ids. A negative setpoint is refused because the engine has no guard on input: a molecule set to −5 ran on −5 in every compartment, and a negative rate would be floored to 0 by the stepper with no note on the record. An action that is none of the four types raises `ValueError`, which leaves the loop as a `TrialError`, not as a rejection.

Each rejection increments the record's `illegal_actions`; once it reaches `illegal_action_limit` (default 10) the trial ends with `"illegal_limit"` at the bottom of that turn. An accepted `Intervene` over its lever's cap is not a rejection ([[#Intervene is a set, and the lever cap]]).



## Intervene is a set, and the lever cap
An accepted `Intervene` SETS its lever: a reaction id gets a new `ChemistryImpl` with that reaction rebuilt at the new rate (`_chemistry_with_rate`); a molecule id gets a state copy with that concentration written into every compartment (`_state_with_concentration`). Either way the turn's world is rebuilt before the burst.

`brief.affordances.max_rates` holds a per-lever cap (declared in `dials["levers"]`, defaulted by the drafter's `setup["lever_caps"]`, or `brief.DEFAULT_MAX_RATE` on a guarded world). A value above its lever's cap is clamped to the cap and applied; the action stays accepted, and its `reason` carries `clamped to max_rate <cap> (requested <value>)`, which also reaches a `SessionAgent` through `notice` (surfaced by `OpaqueAgent`). A value at or under the cap, or on an uncapped lever, carries no note.

Every `Intervene` record also carries `value`, the requested value whenever it is a finite number (rejected ones included), and `delta`, the applied value minus the prior one: the reaction's numeric rate, or the molecule's concentration when every compartment holds the same value, else `None`. Without them a throttle-down and a throttle-up both read as "moved". `destructive` is true for an accepted assay and for an accepted `Intervene` on a lever in `brief.irreversible`.



## Structural hiddenness
Two mechanisms keep a molecule out of the agent's view, and both run before the brief exists, so the brief's probe affordances are exactly the ids the agent can see.

- **The observability dial** hides a seeded random fraction. The hidden set is drawn once, from the `turn/0/observe` seed, and held for the whole trial; only measurement noise redraws per turn (`noise_seed=turn/<t>/observe`). A per-turn redraw used to make later-visible probes illegal and leaked the world over a dozen turns.
- **`task.setup["hidden_ids"]`** is a structural property the drafter declares: those ids are projected out of every turn's observation, turn 0 included, by `project_observation`.

A declared lever may not name a `hidden_ids` pool: an `Intervene` on a molecule sets it, so the episode could write the very quantity it is measured by. `build_brief` refuses that unconditionally, before turn 0 (`tests/suite/test_hidden_pool_levers.py`); the runner itself does not re-check it. A hidden molecule is also a secret to [[#The taint audit]], since it is not among the visible probes.



## The taint audit
`audit_prompts` scans the prompts an agent actually sent, after the loop, for anything it could not otherwise have known. The secrets are built, then trimmed:

| Step | Set |
| --- | --- |
| add | every molecule id not among the brief's visible probes |
| add | every reaction id that is neither a declared lever nor an assay |
| add | every string leaf of an `AnswerObjective` key, minus the visible probes |
| remove | every string leaf of the question |
| remove | any secret that appears as a whole token inside a question leaf or a declared probe text |
| remove | the empty string |
| opaque names | the remaining secrets in surface form, plus every structural id in the map |

The question reaches the agent by construction, so a key token it names (an `identify_pathway` question's endpoints, `describe_the_link`'s `linked` inside its ask sentence) is not a secret, and neither is a token a spec-authored probe names after `probe_vocab` substitution. A key token that is a visible id is not a secret either: the observation already names it, and the secret there is structure, which no token scan sees. Under opaque names the agent was spoken to in surface names, so a secret leaks in surface form, and any structural id in a prompt is itself a leak.

Matching is whole-token through `naming.token_pattern`, the one spelling of the id boundary that the surfacing in `naming.py` also uses: a match may not touch another id character (letters, digits, `_`, `/`, `-`), nor a `.` that continues the id. `OutcomeObjective` targets are not scanned. Hits land on the record's `taint_hits`, and `run` raises `TaintError` with the record. The audit runs only on a trial that left the loop normally.



## Probes on discarded branches
`dials["probes"]` is a list of `{"text", "timing"}` mappings, validated by `_parse_probes` before turn 0 (a list, mappings only, no other keys, non-empty `text`, `timing` in [[#^probe-timings|PROBE_TIMINGS]]). `{placeholder}` tokens in the text are replaced from the drafter's `task.setup["probe_vocab"]`; an unknown placeholder stays verbatim.

| Timing | Fires |
| --- | --- |
| `every_turn` | at the top of each turn, before `act` |
| `after_action` | after the action is selected, before it is validated or applied |
| `at_commit` | at the same point, only on the turn whose action is a `Commit` |

Each firing calls `agent.probe(text)` when the agent is a `ProbeAgent` and appends a `ProbeRecord(turn, timing, text, answer, error)`; an agent without `probe` gets `answer=None`, and an exception from `probe` is caught and recorded in `error`. The answer never enters the turn history: the record's `probes` field is the only place it lands, so the transcript and actions are byte-identical with probes on and off — which holds as long as the agent's `probe` leaves what `act` reads untouched, as the `ProbeAgent` contract requires. `OpaqueAgent.probe` asks in surface names and translates the answer back. Probe spend is metered by the agent, not the runner: `LLMAgent.probe` records each probe call's usage under `usage["per_probe"]` and appends the probe prompt to `prompt_texts`, so the taint audit covers it.



## The destructive assay
A `Measure` with `params["assay"]` true, naming a reaction in `brief.affordances.assays`, reveals that reaction's current rate (a number, or `None` for a non-numeric rate) as `ActionOutcome.result`, and scales every concentration of every molecule in every compartment by `1 − assay_kill`. The record's `kind` is `"assay"`, `destructive` is true, and it is charged as a `Measure`.



## Budget and what ends an episode
The stop checks run at the bottom of a turn, after its burst and readouts, in this order; the first that holds ends the trial:

| `terminal_reason` | When |
| --- | --- |
| `committed` | the turn's action was a `Commit` |
| `illegal_limit` | rejections so far `>= illegal_action_limit` |
| `budget_exhausted` | `Budget.exhausted(spent)` |
| `max_turns` | the loop ran `max_turns` turns without any of the above |
| `error` | set on `TrialError.record` only |

Spend is `_action_cost` per action: the verb's entry in `DEFAULT_ACTION_COSTS`. The table is the runner's: a `cost` key in an agent-supplied `action.params` is ignored for budgeting and noted on that action's `reason` (`params cost … ignored`), so a model cannot buy budget back with `cost: 0`, and a non-numeric one no longer raises. A rejected action costs `illegal_action_cost` when the caller set it, else its normal verb cost. The last turn always plays out in full, burst included, so a committed trial's timeline ends one burst after the commit.



## Errors and the partial record
Configuration errors raise plain `ValueError` before turn 0, outside the error handler. Inside the loop, any exception is caught; the partial record is taint-audited, then re-raised as `TaintError` on a hit, else as `TrialError`, either way carrying the partial record. Nothing inside the loop raises `TaintError`; the finished trial's audit runs after it. The partial record's `turns` counts completed turns, so `readout_series` has `turns + 1` entries and `certainty_schedule` the matching count, the same invariant a finished record keeps.



## What the record carries per turn

| Field | Content |
| --- | --- |
| `action_log` | one `ActionRecord` per turn: `kind`, `destructive`, `accepted`, `reason`, `target`, `value`, `delta` |
| `deliberation_trace` | the agent's reasoning steps, by turn |
| `final_timeline` | every burst sample, times cumulative |
| `readout_series` | each `task.setup["readouts"]` id, summed over compartments, at the start and after every turn; `None` when none declared |
| `certainty_schedule` | one bool per certainty window drawn |
| `monitor` | the auditor's coverage, sham, salience, ledger, logged turns and shown turns; `None` when unmonitored |
| `probes` | every `ProbeRecord` |
| `name_map` | structural → surface, empty when names were not opaque |
| `usage`, `compaction`, `forgetting` | read off the agent by `getattr`, `None` when absent |

The record also carries the brief, the answer (`{"value", "kind"}` or `None`), `final_state`, the oracle, `wall_time_s` (perf-counter from entry) and the budget figures.



## The certainty dial
When the drafter sets `task.setup["certainty"]` (`p`, `on`, `off`, optional `windows`), each turn's burst runs on a burst-only chemistry: one seeded Bernoulli(`p`) draw per window picks the `on` or `off` rate set for the named reactions, without rebinding the persistent chemistry, so an `Intervene` on a rate composes as usual. `on` and `off` must name reactions in the world and `windows` must be an int `>= 1` dividing `sim_steps`, all checked before turn 0. With `windows > 1` the turn is integrated in equal slices, and a slice's closing sample is kept only when it falls on the turn's `sample_every` grid, so the recorded timeline does not move with the window count.



## Seed paths
Every random draw is a child of `run`'s `seed`, so a trial replays from its seed:

| Path | Draw |
| --- | --- |
| `turn/0/observe` | the observability hidden set (all turns) and turn 0's noise |
| `turn/<t>/observe` | turn `t`'s observation noise, `t > 0` |
| `brief` | the brief's seeded content (padding) |
| `names` | the surface-name shuffle |
| `turn/<t>/sim`, `turn/<t>/sim/<w>` | the burst, or slice `w` |
| `turn/<t>/certainty`, `turn/<t>/certainty/<w>` | the window draw |

The monitor's `logs_turn` and `shows_turn` derive their own draws from the seed and turn inside `suite/monitor.py`.




# BRIEF
- 2026-10-19 — written as an ABIO module doc (T084, deep-scan box 3), from the source at alienbio HEAD 84f8190; every member and claim traced to `suite/runner.py`, with the seams checked against `agent.py`, `brief.py`, `naming.py`, `observation.py`, `trial.py`, `verify.py`, `monitor.py`, `llm_agent.py` (probe metering), `mass_trial.py` (error landing) and `tests/suite/test_runner.py` / `test_hidden_pool_levers.py`. Left out as members: the private helpers `_world_from_state`, `_chemistry_with_rate`, `_state_with_concentration`, `_state_scaled`, `_action_cost`, `_resolve_int_dial`, `_is_finite_number`, `_parse_probes`, `_projected_key`, `_leaf_strings`, `_mock_dat` and the unit sets — named in prose where a reader needs them. `Budget.unit`'s "turns" meters action cost, not turns; stated as the source has it. The figure's "validate action" and "stop check" nodes name inline blocks of `run`, not symbols. The `ABIO suite/` folder did not exist and was created for this page.
