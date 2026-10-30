---
description: "`agent`: the `Agent` Protocol and its two optional extensions (`SessionAgent`, `ProbeAgent`), the closed four-verb `Action` set, `ReasoningStep`, `ActionOutcome`, and the deterministic `ScriptedAgent` with its `WaitUntil` guard. Source: `src/alienbio/suite/agent.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO suite](ABIO%20suite.md) → [ABIO Agent](ha://p/ABIO%20Agent) 
# ABIO Agent
The seam every decision-maker binds to: an agent takes an observation and returns one of four neutral actions plus its reasoning, and may opt in to being briefed, told each action's fate, and probed.

![ABIO Agent](ABIO%20Agent.svg) 
*The turn contract* is the topic that governs the runner's numbered call list; *The action vocabulary* governs the `Action` union and what `ActionRecord` logs; *Agent families* governs the green implementer column.

`suite/agent.py` holds the contract only: three structural Protocols, the four action dataclasses the runner and every scorer pattern-match by type, the reasoning fragment, the outcome the runner reports back, and the one built-in agent, `ScriptedAgent`. It holds no world, no simulator and no brief logic. The turn loop that calls these methods, validates and applies the action and writes the `ActionRecord` is [ABIO Runner](ABIO%20Runner.md); the brief handed to `begin` is [ABIO TaskBrief](ABIO%20TaskBrief.md); the live-model implementer is [ABIO LLMAgent](ABIO%20LLMAgent.md); the surface-name wrapper `OpaqueAgent` is [ABIO NameMap](ABIO%20NameMap.md); the record the action log lands on is [ABIO TrialRecord](ABIO%20TrialRecord.md). The registered agents (`AGENTS`) live in `suite/agents.py`. The subsystem view is [ABIO-Runtime](../../ABIO%20Architecture/ABIO-Runtime.md); the operator's view is [ABIO Suite Runtime](../../ABIO%20Architecture/ABIO%20Suite%20Runtime.md) § Agents.



## Agent Interface
The structural Protocol every decision-maker implements: one method, observation in, action and reasoning out. `@runtime_checkable`, so anything with an `act` attribute satisfies it; nothing else is required, which keeps scripted policies and live models interchangeable at the call site. An agent holds no handle on the world, the chemistry, the oracle or the answer key ([What an agent sees](#What%20an%20agent%20sees)). One instance serves one trial: agents keep turn state, and every factory in `AGENTS` builds a fresh one per `(condition, trial)`.

| Agent | |
| --- | --- |
| [act](#^act) | Choose this turn's action from the observation |

**act**`(observation: Observation) -> tuple[Action, tuple[ReasoningStep, ...]]`
    Called once per turn by `runner.run` ([The turn contract](#The%20turn%20contract)). `observation` is a tuple of one `{id: value}` dict per compartment, already narrowed by the observability and noise dials, with `task.setup["hidden_ids"]` dropped and, on some turns, the in-world monitor's block appended. Returns the action to take and zero or more `ReasoningStep`s; the runner threads the steps into the trial's `DeliberationTrace` and validates the action. Returning something that is not one of the four action types is rejected as data, not raised. An exception raised here ends the trial as a `TrialError` carrying the partial record. ^act



## SessionAgent Interface
The optional turn-memory extension (M46.1/M46.2): an agent that also has `begin` and `notice` is told its task once and the fate of every action it takes. `@runtime_checkable`; `runner.run` gates both calls on `isinstance(agent, SessionAgent)`, so an agent without them, `ScriptedAgent` included, is never briefed. Both methods return nothing, and the runner reads nothing back from them.

| SessionAgent | |
| --- | --- |
| [begin](#^begin) | Receive the trial's brief, once, before turn 0 |
| [notice](#^notice) | Receive one action's outcome, every turn |

**begin**`(brief: TaskBrief) -> None`
    Called exactly once, after the brief is built from the turn-0 observation and before the first `act`. The brief carries the question, the constitution and framing when dialed, the legal probes, levers, assays and lever caps, the budget, the per-verb costs and the turn and step limits; under opaque names it arrives with every id in surface form. ^begin

**notice**`(outcome: ActionOutcome) -> None`
    Called once per turn, after the action is validated, charged and applied (or rejected), and before the turn's simulation burst. It is how an agent learns that an action was refused, clamped, or what a destructive assay revealed ([Rejection reaches the agent](#Rejection%20reaches%20the%20agent)). ^notice



## ProbeAgent Interface
The optional discarded-branch extension (T026): a question put to the agent whose answer is recorded and never enters the main line. `@runtime_checkable`. An implementation must leave untouched everything `act` reads — history, turn counter, the token accounting the main line keys off — because the runner guarantees a trial's transcript and actions are byte-identical with probes on and off. Probes are declared per run in `dials["probes"]`.

| ProbeAgent | |
| --- | --- |
| [probe](#^probe) | Answer one question on a discarded branch |

**probe**`(text: str, observation: Optional[Observation] = None) -> Optional[str]`
    Returns the answer text, or `None` when the agent cannot answer. `observation` is the turn's observation — the one `act` is about to see (`every_turn`) or just saw (`after_action`, `at_commit`) — so the probe is asked in the act's own context. The runner calls it at the probe's schedule point (`every_turn` before `act`, `after_action` once the action is chosen, `at_commit` when that action is a `Commit`) and stores a `ProbeRecord`; for an agent that does not implement the Protocol it stores `answer=None` without calling anything. An exception raised here is caught and recorded on the `ProbeRecord.error`, never propagated. ^probe

## ProbeSkipped Interface
An `Exception` subclass (T091 Q4, `e605978`), exported from `alienbio.suite`: `probe` raises it when the probe must not run at all — the trial has aborted, or this turn's act will abort on its token ceiling. No call is made and the runner records no `ProbeRecord` for it ([ABIO Runner](ABIO%20Runner.md)). Distinct from a probe failure, which is recorded as data on `ProbeRecord.error`.

| ProbeSkipped | |
| --- | --- |
| [ProbeSkipped](#^probe-skipped) | The probe is not run and not recorded |

**ProbeSkipped**`(Exception)`
    Raised by `LLMAgent.probe` on or after an abort ([ABIO LLMAgent](ABIO%20LLMAgent.md)). A ceiling hit visible only after a call cannot be foreseen, so that turn's pre-act probe still runs. ^probe-skipped



## Measure Interface
Read an observable. A frozen dataclass; non-mutating, except when `params["assay"]` is true, which makes it the destructive assay ([The action vocabulary](#The%20action%20vocabulary)).

| Measure | |
| --- | --- |
| [probe](#^measure-probe) | The observable read |
| [params](#^params) | Opaque extra configuration |

**probe**`: str`
    The id read. Legal when it is in `brief.affordances.probes`; for an assay, when it is in `brief.affordances.assays` and is a reaction in this world. ^measure-probe

**params**`: Tags = field(default_factory=dict)`
    An opaque bag the world-agnostic core never interprets by name, with two exceptions the runner reads: `assay` (truthy makes the measure a destructive assay) and `cost` (ignored for budgeting and noted on the action's `reason`, since the cost table is the runner's). `LLMAgent` passes the model's `params` through verbatim. ^params



## Intervene Interface
Set one control-surface lever. A frozen dataclass. The runner applies it as a SET, not an add: a reaction lever gets that rate, a molecule lever gets that concentration in every compartment.

| Intervene | |
| --- | --- |
| [lever](#^lever) | The reaction or molecule id set |
| [value](#^value) | The setpoint |
| [params](#^intervene-params) | Opaque extra configuration |

**lever**`: str`
    Legal when it is in `brief.affordances.levers` and resolves to a reaction or a molecule. A lever the brief left off for a reason — the task's readout molecule, a structurally hidden pool, a reaction with a compiled rate law — is rejected naming that reason. ^lever

**value**`: Any`
    The setpoint. Rejected unless it is a finite real (a `bool` is not) and `>= 0`; above the lever's cap in `brief.affordances.max_rates` it is clamped to the cap and still accepted, with the clamp note on `reason`. ^value

**params**`: Tags = field(default_factory=dict)`
    As [Measure.params](#^params); only `cost` is read, to be ignored and noted. ^intervene-params



## Commit Interface
Submit the terminal answer. A frozen dataclass; a trial ends when, and only when, an agent emits one, at the bottom of that turn after its burst.

| Commit | |
| --- | --- |
| [answer](#^answer) | The answer graded against the objective |
| [params](#^commit-params) | Opaque extra configuration |

**answer**`: Answer`
    An `Answer(value, kind)`, kind one of `node_set`, `ordered_path`, `node_id`, `scalar`, `json`. Graded by `grade_answer` for an `AnswerObjective`; an `OutcomeObjective` scores the world's timeline and ignores it. The scripted agents commit `Answer(value=[], kind="json")` as an empty sentinel that grades to 0.0 without raising. Under opaque names `OpaqueAgent` maps its value back to structural ids. ^answer

**params**`: Tags = field(default_factory=dict)`
    As [Measure.params](#^params). `LLMAgent` marks its own abort commits here (`{"aborted": "token_ceiling"}` or `"parse_exhausted"`). ^commit-params



## Wait Interface
Let a turn pass without measuring or acting. A frozen dataclass; the runner treats it exactly like a non-assay `Measure` in its world effect, and it costs nothing by default.

| Wait | |
| --- | --- |
| [duration](#^duration) | Requested simulated seconds; not read |
| [params](#^wait-params) | Opaque extra configuration |

**duration**`: float`
    Accepted and logged but not read: every turn plays one fixed `sim_cfg` burst whatever the agent asked for. ^duration

**params**`: Tags = field(default_factory=dict)`
    As [Measure.params](#^params). ^wait-params



## ReasoningStep Interface
One opaque fragment of the reasoning behind a turn's action. A frozen dataclass mirroring `DeliberationStep` minus its `turn`, which is assigned when `trial.thread_reasoning_steps` appends the batch to the trace (also adding the action's lower-cased type name to `refs`). An agent picks its own granularity: `ScriptedAgent` emits one per fired step, `LLMAgent` one per turn carrying the model's `reasoning` text, the bare factories in `suite/agents.py` often none.

| ReasoningStep | |
| --- | --- |
| [kind](#^kind) | Opaque fragment tag |
| [content](#^content) | The fragment's text |
| [refs](#^refs) | Ids the fragment refers to |

**kind**`: str`
    Opaque tag; the shipped agents use `"policy"`, `"llm"` and `"abort"`. ^kind

**content**`: str`
    Free text. Under opaque names it is kept as the agent wrote it, in surface names. ^content

**refs**`: tuple[str, ...] = ()`
    Ids the fragment names; `OpaqueAgent` maps each back to its structural id. ^refs



## ActionOutcome Interface
What happened to one fired action at the runner (M46.3), handed to a `SessionAgent`'s `notice`. A frozen dataclass; built by `runner.run` every turn, never by an agent.

| ActionOutcome | |
| --- | --- |
| [turn](#^turn) | The turn index |
| [action](#^action) | The action as the agent returned it |
| [accepted](#^accepted) | Whether the runner applied it |
| [reason](#^reason) | Why it was rejected, or a note |
| [result](#^result) | What an accepted action returned |

**turn**`: int`
    0-based turn index. ^turn

**action**`: Action`
    The action as returned by `act` (surfaced again by `OpaqueAgent` before the inner agent sees it). ^action

**accepted**`: bool`
    `False` for a rejected action; nothing in the world changed. ^accepted

**reason**`: str = ""`
    The rejection reason; on an accepted action, empty except for a clamp note (`clamped to max_rate …`) or the ignored-`params["cost"]` note. ^reason

**result**`: Any = None`
    The reaction rate a destructive assay revealed; `None` for every other action. ^result



## WaitUntil Interface
A conditional guard inside a `ScriptedAgent` step list: hold at this position, measuring, until a predicate on the observation holds. A frozen dataclass.

| WaitUntil | |
| --- | --- |
| [predicate](#^predicate) | Condition on the current observation |
| [probe](#^waituntil-probe) | What to measure while it is unmet |

**predicate**`: ObservationPredicate`
    Called with each turn's observation, never inspected. The first turn it is true, the policy advances and the next step fires in the same `act` call. ^predicate

**probe**`: str`
    While the predicate is false the agent emits `Measure(probe)` each turn, with one `ReasoningStep` naming the unmet guard. ^waituntil-probe



## ScriptedAgent Interface
The deterministic, network-free agent that keeps CI green with zero model calls and serves as the zero every live-model number is read against. A plain class satisfying `Agent` only: it has no `begin` or `notice`, so it is never briefed. Its decisions are a pure function of `(policy, seed, observation sequence)`.

| ScriptedAgent | |
| --- | --- |
| [ScriptedAgent](#^scriptedagent) | Build from a policy and a seed |
| [policy](#^policy) | The step list or callable |
| [seed](#^seed) | The agent's seed |
| [act](#^scriptedagent-act) | Fire the next policy step |

**ScriptedAgent**`(policy: Policy, seed: Seed) -> None`
    Stores both and starts at step 0. Validates nothing. ^scriptedagent

**policy**`: Policy`
    A tuple of `PolicyStep`s, or a callable `(observation, seed) -> (action, reasoning_steps)` (the escape hatch every factory in `suite/agents.py` uses). ^policy

**seed**`: Seed`
    Handed to a callable policy every turn; the step-list path never reads it. ^seed

**act**`(observation: Observation) -> tuple[Action, tuple[ReasoningStep, ...]]`
    A callable policy is called and its result returned as is. A step list is walked in order: a `WaitUntil` either measures its probe (unmet) or advances (met); any other step is returned as the action with one `ReasoningStep(kind="policy")` naming its type, and the position advances. Raises `RuntimeError` when called after the list is exhausted, naming the step count, the turn, and whether the list ended on a `Commit`. ^scriptedagent-act



## agent Interface
The module-level type aliases. The module has no `__all__`; `alienbio.suite` re-exports every public name in it: `Action`, `ActionOutcome`, `Agent`, `Commit`, `Intervene`, `Measure`, `ObservationPredicate`, `Policy`, `PolicyStep`, `ProbeAgent`, `ReasoningStep`, `ScriptedAgent`, `SessionAgent`, `Wait` and `WaitUntil`.

| agent | |
| --- | --- |
| [Action](#^agent-action) | The closed four-verb union |
| [ObservationPredicate](#^observationpredicate) | A test on one observation |
| [PolicyStep](#^policystep) | One step of a step-list policy |
| [Policy](#^agent-policy) | A step list or a callable |

**Action**`= Union[Measure, Intervene, Commit, Wait]`
    The closed neutral action set. Scorers and the runner dispatch on the type, never on a name. ^agent-action

**ObservationPredicate**`= Callable[[Observation], bool]`
    The type of `WaitUntil.predicate`. ^observationpredicate

**PolicyStep**`= Union[Measure, Intervene, Commit, Wait, WaitUntil]`
    One step-list entry. ^policystep

**Policy**`= Union[tuple[PolicyStep, ...], Callable[[Observation, Seed], tuple[Action, tuple[ReasoningStep, ...]]]]`
    The two policy forms `ScriptedAgent` accepts. ^agent-policy




# Agent Semantics

## The turn contract
`runner.run` is the only caller. In order:

| When | Call | Condition |
| --- | --- | --- |
| before turn 0, once | `begin(brief)` | agent is a `SessionAgent` |
| each turn, first | `probe(text, observation)` for `every_turn` probes | agent is a `ProbeAgent` |
| each turn | `act(observation)` | always |
| right after `act` | `probe(text, observation)` for `after_action`, then `at_commit` probes | agent is a `ProbeAgent`; `at_commit` only on a `Commit` |
| after validate, charge, apply | `notice(ActionOutcome(...))` | agent is a `SessionAgent` |

Then the turn simulates one burst, and the loop stops on a `Commit`, on `illegal_action_limit` rejections (default 10), on the budget, or at `max_turns`. Under opaque names the runner wraps the agent in `OpaqueAgent` before `begin`, and every call above goes through the wrapper; the wrapper always has `begin`, `notice` and `probe`, and passes each on only when the inner agent has it. The Protocols are structural: `isinstance` checks only that the attributes exist, so a class that defines `begin` and `notice` for any purpose is briefed.



## The action vocabulary

| Action | Carries | Runner's effect | Rejected when | Default cost |
| --- | --- | --- | --- | --- |
| `Measure` | `probe` | none; logged | probe not in `brief.affordances.probes` | 1 |
| `Measure`, `params["assay"]` | `probe` = a reaction id | reveals its rate on `ActionOutcome.result`; scales every concentration by `1 − assay_kill` | not in `affordances.assays`, or not a reaction here | 1 |
| `Intervene` | `lever`, `value` | SETS the reaction's rate, or the molecule's concentration in every compartment; clamped at the lever's cap | lever not on the surface (reason named), not resolvable, value non-finite or negative | 5 |
| `Commit` | `answer` | ends the trial after this turn's burst; the answer is graded | never | 0 |
| `Wait` | `duration` | none; `duration` unread | never | 0 |
| anything else | — | none | always (`unknown action type …`) | only `illegal_action_cost` |

Costs are the runner's table (`brief.DEFAULT_ACTION_COSTS`), shown to the agent on the brief; an agent cannot price its own action. A rejected action is charged its verb cost unless `illegal_action_cost` is set. Every action, accepted or not, writes one `ActionRecord` (`kind`, `accepted`, `reason`, `target`, `value`, `delta`, `destructive`); an accepted assay, and an accepted `Intervene` on a lever in `brief.irreversible`, are `destructive`. The full check order is [ABIO Runner](ABIO%20Runner.md) § Rejection as data.



## Rejection reaches the agent
An illegal action never raises: it is logged, charged, and the turn still simulates. A `SessionAgent` hears it through `notice` with `accepted=False` and the reason, so a model that hallucinated an id can correct itself next turn. A clamp is not a rejection: the outcome is accepted and carries the clamp note. An agent that is not a `SessionAgent` gets no feedback at all.



## What an agent sees
An agent receives exactly three things: the brief (through `begin`), each turn's narrowed observation (through `act`), and the outcome of its own actions (through `notice`). It never receives the world, the chemistry, the full state, the oracle, the answer key or `task.setup`. The observation's hidden set is drawn once per trial and held, so the brief's probe list stays the legal set all trial; noise is redrawn each turn; `hidden_ids` pools never appear, and a lever naming one is refused. Under opaque names (`opaque_names_requested`) every id the agent sees is an `m01`/`r01` surface name and every id it returns is mapped back before validation. After the loop `audit_prompts` scans whatever the agent exposes as `prompt_texts` for leaked secrets; an agent without that attribute audits clean.



## Seeding and matched arms
The factory signature is `(seed, dials) -> Agent`. `MassTrialRunner` derives each trial's seed as `base_seed.child(f"{label}/{i}")`, drafts the world on `.child("draft")`, builds the agent on `.child("agent")` and runs on `.child("run")`. The label leaves out the world-invariant dials (`agent`, `model`, `memory`, `max_turns`, `budget`, … — `WORLD_INVARIANT_DIALS`) and any `matched_dials`, so a scripted arm and a live-model arm of one condition run on byte-identical worlds. A step-list `ScriptedAgent` ignores its seed; the callable factories in `suite/agents.py` take it and ignore it; `LLMAgent` keys its call cache and retries on it.



## Agent families

| Family | Protocols | Shipped (`AGENTS` name) | Reads the brief |
| --- | --- | --- | --- |
| Scripted, act only | `Agent` | `idle`, `measure-commit`, `survey-commit` (all `ScriptedAgent` over a callable) | no |
| Scripted, session-shaped | `Agent`, `SessionAgent` | `heuristic-commit`, `knockout-commit`, `act-commit`, `assay-commit`, `pursue-target` | yes: question, irreversible levers, levers, assays, target and goal |
| Live model | `Agent`, `SessionAgent`, `ProbeAgent` | `llm` (`LLMAgent`) | yes, rendered into the system prompt |

`OpaqueAgent` is not registered: the runner inserts it around whichever agent a trial uses. The kind is `dials["agent"]` when that dial is swept, else the spec's `agent`; `_agent_factory_for` refuses an unknown kind. The factory-read dials (`agent`, `model`, `memory`, `compact_at`, `compact_budget`, `history_token_limit`, `max_tokens`, `output_schedule`) are `FACTORY_DIALS` in `suite/drafters.py`; only the `llm` factory reads any beyond `agent`.



## Writing a scripted agent
A step list is enough when the policy does not depend on the brief. From `tests/suite/test_agent.py`, polling a probe until it crosses a threshold, then acting and committing:

```python
policy = (
    WaitUntil(
        predicate=lambda obs: obs[0]["probe_x"] > 5.0,
        probe="probe_x",
    ),
    Intervene(lever="pump_rate", value=2.0),
    Commit(answer=Answer(value="done", kind="scalar")),
)
agent = ScriptedAgent(policy=policy, seed=Seed(42))
```

A policy that needs the declared surface is a plain class with `begin`, `notice` and `act`, as the five session-shaped classes in `suite/agents.py` and the shortcut policies in `tests/suite/test_gameability.py` are. End the list with a `Commit` or keep `max_turns` within its length: an exhausted list raises. A predicate indexes the observation by id, so under opaque names it must use surface names.




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084, deep-scan box 3), from the source at alienbio HEAD a799468; members traced to `suite/agent.py`, behavior to `suite/runner.py` (turn loop, rejection, costs since `d0a2797`, unknown-type rejection since `484db58`, rate-law and readout refusals through `brief.lever_exclusion` since `f1b2af0`/`a799468`), `suite/agents.py`, `suite/llm_agent.py` (`_parse_action`), `suite/naming.py`, `suite/mass_trial.py` (seed paths), `suite/info_seeking.py` (`ActionRecord`) and `tests/suite/test_agent.py`, `test_runner.py`, `test_gameability.py`. Left out: `ScriptedAgent._pos` (private), the private agent classes and factories of `suite/agents.py` as members (they are tabled under Agent families, and belong to a future `agents` doc), and `ActionRecord` as an Interface section (it is defined in `suite/info_seeking.py`). The default costs are read from `brief.DEFAULT_ACTION_COSTS`. The brief's task list named a `prior-commit` agent; it is not a framework entry in `AGENTS` but the grid example's own, added to `AGENTS` when `catalog/examples/grid/helpers.py` is loaded, so it is not listed.
- 2026-10-28 — refreshed against 0eb23e5: `ProbeAgent.probe` takes the turn's observation (`01fee6a`); the turn-contract rows and the figure's ProbeAgent box pass it.
- 2026-10-29 — refreshed for `e605978` (T091 Q4): `ProbeSkipped` given an interface block — raised by `probe` when it must not run; the runner records nothing for it.
