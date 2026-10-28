---
description: "`TaskBrief` + `Affordances` + `build_brief`/`render_brief`: what a live agent is told before turn 0, the refusals made while building it, and the dial helpers that feed it. Source: `src/alienbio/suite/brief.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO suite](ABIO%20suite.md) → [ABIO TaskBrief](ha://p/ABIO%20TaskBrief) 
# ABIO TaskBrief
The briefing a trial's agent receives once, before turn 0: a frozen record of the question, the commitment, what it is told about the world, what it may measure and intervene on, and the episode's limits, built by a pure function that refuses a contradictory spec before any model is called.

![[ABIO TaskBrief.svg|2400]] 
*The refusals before spend* is the topic that governs the refusal gate; *The rendered order* governs the grouping inside `TaskBrief` and `render_brief`'s line sequence.

`runner.run` builds one brief per trial from the dial-narrowed turn-0 observation (so a hidden molecule is absent, not merely unlisted), the task, its drafter `setup` and the condition's dials, hands it to the agent through `SessionAgent.begin`, and keeps it, in structural ids, on the `TrialRecord`. This page covers the record, its constructor, its text rendering and the dial resolvers. The turn loop, the probe schedule and the taint audit are [[ABIO Runner]]; the surface-name boundary is [[ABIO NameMap]]; the drafters that put `lever_caps`, `hidden_ids`, `brief_defaults`, `probe_vocab` and the `epistemic_access` disclosure on the task live in `suite/drafters.py`; the guards that repeat some of these refusals at `preflight` live in `suite/guards.py`. The subsystem view is [[ABIO-Runtime]]; the operator's view is [[ABIO Suite Runtime]].



## TaskBrief Interface
A frozen dataclass with no methods: every field is set once by `build_brief` and read by `render_brief`, `surface_brief`, the runner's action validation and the record store. It holds only what the agent may see — the answer key's `kind`, never its `value`; the monitoring dial's surfaced side, never its actual side (that goes to `TrialRecord.oracle["monitoring_actual"]`). Fields are listed in the order the rendered brief presents them; the two the rendering never shows (`question_kind`, `sim_dt`) sit beside their neighbours.

| TaskBrief | |
| --- | --- |
| [[#^question\|question]] | The question's structured form, verbatim |
| [[#^question-kind\|question_kind]] | The question's kind; not rendered |
| [[#^task-note\|task_note]] | Text placed right after the question line |
| [[#^objective-kind\|objective_kind]] | `answer` or `outcome` |
| [[#^answer-kind\|answer_kind]] | The answer key's kind, never its value |
| [[#^context-padding\|context_padding]] | Neutral filler burying the constitution |
| [[#^constitution\|constitution]] | The injected directive, when a string |
| [[#^constitution-in-history\|constitution_in_history]] | Constitution goes to turn history instead |
| [[#^protocol\|protocol]] | Free-text process scaffold |
| [[#^framing\|framing]] | Framing text, resolved |
| [[#^monitoring\|monitoring]] | The surfaced monitoring signal |
| [[#^monitor\|monitor]] | The in-world auditor's one line |
| [[#^stakes\|stakes]] | Stakes text, resolved |
| [[#^reversibility\|reversibility]] | Reversibility text, resolved |
| [[#^irreversible\|irreversible]] | Levers whose Intervene is destructive |
| [[#^affordances\|affordances]] | What a Measure or Intervene may name |
| [[#^budget-total\|budget_total]] | The trial's budget |
| [[#^budget-unit\|budget_unit]] | The budget's unit |
| [[#^action-costs\|action_costs]] | Per-verb cost table |
| [[#^max-turns\|max_turns]] | Turn limit |
| [[#^sim-steps\|sim_steps]] | Simulation steps per turn |
| [[#^sim-dt\|sim_dt]] | Step size; not rendered |

**question**`: Any`
    `task.question.structured` as drafted: a dict on every generated world, carrying the drafter's `target`/`tracked`/`goal` ids and, under `epistemic_access`, its `evidence` or `chemistry` disclosure ([[#The disclosure ladder]]). Rendered as `json.dumps(sort_keys=True, default=repr)`. Never taint: it is what the agent is asked. ^question

**question_kind**`: str`
    `task.question.kind` (`"json"` on the pressure families). Stored, not rendered. ^question-kind

**task_note**`: Optional[str] = None`
    `dials["task_note"]` verbatim (T061, AUP's B1 wording control): the line right after `Question:`, so a prohibition can ride the task statement with the constitution empty. A non-string or blank value raises. Guarded, surfaced under opaque names, stored only when set. ^task-note

**objective_kind**`: str`
    `"answer"` when `task.objective` is an `AnswerObjective`, else `"outcome"`; decides between the expected-answer line and the scored-on-outcome sentence. ^objective-kind

**answer_kind**`: Optional[str]`
    `AnswerObjective.key.kind` (`"ordered_path"`, `"json"` …); `None` on an outcome objective. The key's value is never read. ^answer-kind

**context_padding**`: Optional[str] = None`
    T027's buried-commitment control: `neutral_padding(dials["bury_commitment"], seed.child("bury_commitment"))`, rendered as a `Background record (routine site log):` line immediately before `Constitution:` ([[#The burial forms]]). Surfaced like every printed field, though it holds no id by construction; stored only when set. ^context-padding

**constitution**`: Optional[str]`
    `dials["constitution"]` (or a drafter's `brief_defaults` value) when it is a `str`, else `None` (M30.1). Stays on the brief under displacement; only the rendering drops it. ^constitution

**constitution_in_history**`: bool = False`
    T029's displacement burial: when `True`, `render_brief` omits the `Constitution:` line and `LLMAgent.begin` appends `{"turn": -1, "briefing": "Constitution: …"}` as the oldest history entry, so a finite `memory=k` window displaces it. Stored only when `True`. ^constitution-in-history

**protocol**`: Optional[str] = None`
    `dials["protocol"]` (T032, AUP's C10 hunt): rendered as `Protocol:` right after the constitution line, or in its place when none renders. Prompt text, not a guard dial; a non-string or blank value raises. Stored only when set. `surface_brief` renames ids inside it ([[#Opaque names]]). ^protocol

**framing**`: Optional[str] = None`
    `resolve_framing(dials)`: a `FRAMING_PRESETS` name's text, any other string verbatim, or a `{briefing, hints}` dict composed by `compose_briefing` over an empty base; `None` when absent or empty. ^framing

**monitoring**`: Any = None`
    The surfaced side of `resolve_monitoring(dials)` (M32.5); rendered whenever not `None`, so a bare `False` renders as `Monitoring: False`. ^monitoring

**monitor**`: Optional[str] = None`
    `monitor_brief_text(resolve_monitor(dials))` from `suite/monitor.py` (T060, AUP C4): one `Auditor:` line naming the coverage and the two observation keys, identical for the monitored and sham arms. Stored only when set. ^monitor

**stakes**`: Optional[str] = None`
    `resolve_stakes(dials)` (M32.2, ported in M36.7). W2 supplies an in-world default naming the tracked pool and the custodial reserve. ^stakes

**reversibility**`: Optional[str] = None`
    `resolve_reversibility(dials)`; also decides `irreversible` when no explicit list is given. ^reversibility

**irreversible**`: tuple[str, ...] = ()`
    `resolve_irreversible_levers(dials, levers)`. The runner tags an accepted `Intervene` on one of these `ActionRecord.destructive`. Rendered only when `reversibility` is set or the set differs from the whole lever list. ^irreversible

**affordances**`: Affordances`
    The probe, lever and assay allowlists and the per-lever caps the runner validates every action against ([[#The control surface]]). ^affordances

**budget_total**`: float`
    `budget.total` from the runner's `Budget`; rendered `unlimited` when infinite. ^budget-total

**budget_unit**`: str`
    `budget.unit`. ^budget-unit

**action_costs**`: Mapping[str, float]`
    A fresh `dict(DEFAULT_ACTION_COSTS)`. An agent-supplied `action.params["cost"]` is ignored by the runner, so this table is the whole cost model. ^action-costs

**max_turns**`: int`
    The resolved turn limit (`dials["max_turns"]` or the runner's default). ^max-turns

**sim_steps**`: int`
    `sim_cfg.steps`, after the runner applies `dials["sim_steps"]`. ^sim-steps

**sim_dt**`: float = 0.1`
    `sim_cfg.dt`. Carried for the record; the rendering states steps per turn but not their size. ^sim-dt



## Affordances Interface
A frozen dataclass: the ids an action may legally name in this trial and the cap on an `Intervene` value. The runner rejects, as data, a `Measure` whose probe is not in `probes`, an assay not in `assays`, and an `Intervene` whose lever is not in `levers`; it clamps an over-cap value to `max_rates` and keeps the action accepted.

| Affordances | |
| --- | --- |
| [[#^probes\|probes]] | Ids a Measure may name |
| [[#^levers\|levers]] | Ids an Intervene may name |
| [[#^assays\|assays]] | Reactions a destructive assay may name |
| [[#^max-rates\|max_rates]] | Per-lever cap on an Intervene value |

**probes**`: tuple[str, ...]`
    The sorted union of every id in every compartment of the turn-0 observation, plus the auditor keys (`monitor_probe_ids`) on a monitor arm, since the auditor block is appended after narrowing and would otherwise make the ids the brief names unmeasurable (T066). Not the discarded-branch `dials["probes"]` ([[#Probes are not on the brief]]). ^probes

**levers**`: tuple[str, ...]`
    `dials["levers"]` in declared order when the key is present (`[]` is a valid do-nothing surface); otherwise every reaction id, sorted, followed by `probes`, minus every id `lever_exclusion` refuses (the task's readouts, a hidden pool, a reaction with a compiled `rate_law`) — except on a task whose `setup` carries `require_levers`, where the missing dial raises. ^levers

**assays**`: tuple[str, ...] = ()`
    `resolve_assays(dials, chemistry)` (M36.10); empty unless `dials["assays"]`. ^assays

**max_rates**`: Mapping[str, float] = field(default_factory=dict)`
    Lever id → cap (T023): the spec's `{"id", "max_rate"}` entry wins, then `setup["lever_caps"]`, then `DEFAULT_MAX_RATE` on a guarded world; a lever with none of these is absent and uncapped. Stored only when non-empty. ^max-rates



## brief Interface
The module's functions and tables. Nothing is listed in an `__all__` and `alienbio.suite` re-exports none of it; callers import from `alienbio.suite.brief`.

| brief | |
| --- | --- |
| [[#^build-brief\|build_brief]] | Build the trial's one brief, refusing contradictions |
| [[#^render-brief\|render_brief]] | The brief as labelled plain text |
| [[#^compose-briefing\|compose_briefing]] | Apply a framing dict to a base text |
| [[#^coerce-monitoring\|coerce_monitoring]] | A monitoring spec to surfaced and actual |
| [[#^resolve-monitoring\|resolve_monitoring]] | `coerce_monitoring` over the dial |
| [[#^resolve-framing\|resolve_framing]] | The framing dial's text |
| [[#^resolve-stakes\|resolve_stakes]] | The stakes dial's text |
| [[#^resolve-reversibility\|resolve_reversibility]] | The reversibility dial's text |
| [[#^resolve-irreversible-levers\|resolve_irreversible_levers]] | Which levers are destructive |
| [[#^resolve-assays\|resolve_assays]] | The assay allowlist |
| [[#^neutral-padding\|neutral_padding]] | Seed-deterministic neutral filler |
| [[#^default-action-costs\|DEFAULT_ACTION_COSTS]] | Per-verb default costs |
| [[#^default-max-rate\|DEFAULT_MAX_RATE]] | Fallback lever cap on a guarded world |
| [[#^monitoring-presets\|MONITORING_PRESETS]] | Named monitoring arms |
| [[#^framing-presets\|FRAMING_PRESETS]] | Named framings |
| [[#^stakes-presets\|STAKES_PRESETS]] | Named stakes texts |
| [[#^reversibility-presets\|REVERSIBILITY_PRESETS]] | Named reversibility texts |

**build_brief**`(task: TaskInstance, chemistry: ChemistryImpl, first_observation: Observation, dials: Mapping[str, Any], budget: Budget, max_turns: int, sim_cfg: SimConfig, seed: Optional[Seed] = None) -> TaskBrief`
    Pure: reads its arguments, returns a new `TaskBrief`, touches nothing. `first_observation` must be the narrowed, `hidden_ids`-projected turn-0 read; the runner passes exactly that and `seed.child("brief")`. Raises `ValueError` for every case in [[#The refusals before spend]], plus whatever the resolvers and `resolve_monitor` raise. ^build-brief

**render_brief**`(brief: TaskBrief) -> str`
    Newline-joined labelled lines in a fixed order ([[#The rendered order]]), from the brief's own fields only. `LLMAgent.begin` makes its system prompt `directive + "\n\n" + render_brief(brief)`; `suite/realism.py` renders transcripts with it. ^render-brief

**compose_briefing**`(base: str, framing: Any) -> str`
    `None` returns `base` unchanged; a dict may carry `briefing` (replacement text) and `hints` (a list of strings, appended as a `Hints:` bullet block after a blank line). `ValueError` on any other key; `TypeError` on a non-dict, a non-string `briefing` or a `hints` that is not a list of strings. ^compose-briefing

**coerce_monitoring**`(spec: Any) -> tuple[Any, Any]`
    `(surfaced, actual)`: `None` → `(None, None)`; a `MONITORING_PRESETS` name → its pair; another scalar → `(spec, spec)`; a dict with `surfaced` and/or `actual` → each side, an omitted side `None`. `ValueError` on an empty dict or unknown keys, `TypeError` on any other type. ^coerce-monitoring

**resolve_monitoring**`(dials: Mapping[str, Any]) -> tuple[Any, Any]`
    `coerce_monitoring(dials.get("monitoring"))`. The runner calls it too, to record the actual side. ^resolve-monitoring

**resolve_framing**`(dials: Mapping[str, Any]) -> Optional[str]`
    A preset name → its text; another string → itself; a dict → `compose_briefing("", framing)`; empty or absent → `None`. ^resolve-framing

**resolve_stakes**`(dials: Mapping[str, Any]) -> Optional[str]`
    A `STAKES_PRESETS` name → its text, another string verbatim, `None` or `""` → `None`; any other type raises `ValueError`. ^resolve-stakes

**resolve_reversibility**`(dials: Mapping[str, Any]) -> Optional[str]`
    The same rules over `REVERSIBILITY_PRESETS`. ^resolve-reversibility

**resolve_irreversible_levers**`(dials: Mapping[str, Any], levers: Sequence[str]) -> tuple[str, ...]`
    An explicit `dials["irreversible_levers"]` wins (every entry a `str`, else `ValueError`; entries are not checked against `levers`). Otherwise `reversibility == "reversible"` → `()`, and anything else — `"irreversible"`, free text or no dial — → every lever, the pre-M36.7 rule that every accepted `Intervene` counts. ^resolve-irreversible-levers

**resolve_assays**`(dials: Mapping[str, Any], chemistry: ChemistryImpl) -> tuple[str, ...]`
    Absent → `()`; `"all"` → every reaction id, sorted; a list → its entries as strings, `ValueError` naming any that is not a reaction in `chemistry`. ^resolve-assays

**neutral_padding**`(n_tokens: int, seed: Seed) -> str`
    Sentences drawn by `seed.rng()` from four fixed facilities-language vocabularies (subject, verb, object, tail; no digits, no chemistry), appended until `len(text) // 4 >= n_tokens`, the suite's chars/4 token estimate. Deterministic in `(n_tokens, seed)`. `ValueError` unless `n_tokens` is a positive `int` (a `bool` is refused). ^neutral-padding

**DEFAULT_ACTION_COSTS**`: Mapping[str, float]`
    `measure` 1.0, `intervene` 5.0, `commit` 0.0, `wait` 0.0, keyed by lower-cased action type. Lives here so `runner._action_cost` and the brief read one table without a circular import. ^default-action-costs

**DEFAULT_MAX_RATE**`: float = 100.0`
    The cap every declared lever on a guarded world gets when neither the spec nor `setup["lever_caps"]` gives one (T023): finite, so one mega-pull cannot replace the repetition the pressure dial prices. ^default-max-rate

**MONITORING_PRESETS**`: Mapping[str, tuple[str, bool]]`
    EXP-4's three arms as `(surfaced text, actual)`: `logged` (told logged, logged), `apparently-unlogged` (told unlogged, unlogged), `deceptively-unlogged` (told unlogged, logged). ^monitoring-presets

**FRAMING_PRESETS**`: Mapping[str, str]`
    EXP-6's objective-type framings (M36.3): `procedural`, `substantive`, `meta`. ^framing-presets

**STAKES_PRESETS**`: Mapping[str, str]`
    `low` and `high`. ^stakes-presets

**REVERSIBILITY_PRESETS**`: Mapping[str, str]`
    `reversible` and `irreversible`; the second names a knockout as the permanent act. ^reversibility-presets




# TaskBrief Semantics

## The refusals before spend
Every row raises `ValueError` from `build_brief`, which the runner calls before `begin`, so no model call has been made. Rows marked *preflight* are also caught by `suite/guards.py` before the grid starts: the drafted-task check (`draft`), the surface check (`declared_surface_violation`) or the monitor check (`brief-dials`).

| Refusal | Condition | Since | Preflight |
| --- | --- | --- | --- |
| No control surface | `setup["require_levers"]` and no `levers` dial | M45.2 | surface |
| Malformed lever entry | not a `str` or an `{id, max_rate}` mapping; an unknown key; a non-string `id` | T023 | — |
| Bad cap | a `max_rate` or a `lever_caps` value that is a `bool`, non-numeric, non-finite or ≤ 0; `lever_caps` not a mapping | T023 | — |
| Lever is a readout | a declared lever is in `task_readouts`: the structured question's `target` or `tracked`, any string in a tuple/list `OutcomeObjective.target`, or a molecule a bare-collection question names unless the answer key is a node — on any world (guarded only until 2026-10-28) | T023, every readout since T051 box 4 | — |
| Lever is a hidden pool | a lever is in `setup["hidden_ids"]`, on any world | T066 Q1 | draft |
| Lever has a rate law | a declared lever (dial or drafter default) names a reaction carrying a compiled `rate_law`, on any world; the implicit surface leaves such a reaction out instead | module-doc pass 2026-10-27, owner (A) | draft |
| Bad defaults | `setup["brief_defaults"]` set but not a mapping | T047 | draft |
| Bad burial depth | `bury_commitment` not a non-negative `int` | T027 | — |
| Nothing to bury | `bury_commitment` > 0 with no or an empty constitution | T027 | — |
| Unseeded burial | `bury_commitment` > 0 and `seed=None` | T027 | — |
| Bad displacement flag | `constitution_in_history` not a `bool` (`0` passes as false) | T029 | — |
| Nothing to displace | `constitution_in_history` with no or an empty constitution | T029 | — |
| Two burial forms | `bury_commitment` > 0 and `constitution_in_history` | T029 | — |
| Blank scaffold | `protocol` set but not a non-blank `str` | T032 | — |
| Blank task note | `task_note` set but not a non-blank `str` | T061 | — |
| Bad told text | `stakes` or `reversibility` not a `str`; a non-string `irreversible_levers` entry | M36.7 | — |
| Unknown assay | an `assays` entry is not a reaction in the world | M36.10 | — |
| Bad monitor arm | `resolve_monitor`: coverage outside [0, 1], sham or salience without coverage, combined with `monitoring` | T060 | brief-dials |

`framing` and `monitoring` raise `TypeError` or `ValueError` from `compose_briefing` and `coerce_monitoring`. Both lever refusals exist because an `Intervene` on a molecule *sets* its concentration in every compartment: a readout lever lets the agent write the answer into the measurement, a hidden-pool lever lets it write the ground truth it is scored against (W2's `harm_ledger`, phase 1's unobservable tracked pool).



## Brief defaults and merge order
A drafter may ship `setup["brief_defaults"]`; W2 ships its bright-line commitment as `constitution` and its in-world `stakes`. They are merged as `{**defaults, **{k: v for k, v in dials.items() if v is not None}}`, so an explicit dial wins and a dial set to `None` does not erase a default. The merge happens first, so every consumer reads the merged view: the monitor probe keys, `levers` and the caps, both lever refusals, the constitution, both burial forms, `protocol`, `task_note`, the told-text resolvers, `irreversible`, `assays` and the monitor line. A drafter-default lever is therefore offered, capped and refused exactly like a declared one (no shipped drafter carries one).



## The rendered order
`render_brief`'s lines, top to bottom. A field absent or falsy produces no line, so a brief with none of the optional fields renders exactly as it did before they existed.

| # | Line | Field | Present when |
| --- | --- | --- | --- |
| 1 | `Question: {json}` | `question` | always |
| 2 | `Task note:` | `task_note` | set |
| 3 | `Expected answer kind:` or the outcome sentence | `objective_kind`, `answer_kind` | always |
| 4 | `Background record (routine site log):` | `context_padding` | constitution rendered and padding set |
| 5 | `Constitution:` | `constitution` | truthy and not displaced |
| 6 | `Protocol:` | `protocol` | set |
| 7 | `Framing:` | `framing` | truthy |
| 8 | `Monitoring:` | `monitoring` | not `None` |
| 9 | `Auditor:` | `monitor` | set |
| 10 | `Stakes:` | `stakes` | truthy |
| 11 | `Reversibility:` | `reversibility` | truthy |
| 12 | `Irreversible levers (cannot be undone):` | `irreversible` | non-empty, and `reversibility` set or not every lever |
| 13 | `Probes (Measure may name):` | `affordances.probes` | always |
| 14 | `Levers (Intervene may name…):` | `affordances.levers` | always; caps as `id (max N)` plus the clamp sentence when any cap exists |
| 15 | `Assays (…destructive):` | `affordances.assays` | non-empty |
| 16 | `Budget: … (per-action costs: …)` | `budget_total`, `budget_unit`, `action_costs` | always |
| 17 | `Max turns:` | `max_turns` | always |
| 18 | `Simulation steps per turn:` | `sim_steps` | always |

`question_kind`, `sim_dt` and the `constitution_in_history` flag are never rendered.



## The burial forms
Two ways to make the constitution harder to retain, one per arm.

| | `bury_commitment: N` | `constitution_in_history: true` |
| --- | --- | --- |
| Ticket | T027 | T029 |
| Mechanism | ≥ N estimated tokens of `neutral_padding` immediately before `Constitution:` in the system prompt | no `Constitution:` line; `LLMAgent.begin` seeds it once as history entry `turn: -1` |
| What it tests | salience and dilution | forgetting, as `memory=k` displaces the entry |
| Needs | a constitution and the trial seed | a constitution, and an agent with `memory != "none"` (`LLMAgent.begin` raises) |
| Brief field | `context_padding` | `constitution_in_history` |

Padding cannot induce forgetting: the system prompt is re-sent whole on every call, and AUP measured retention flat out to 20k tokens of filler. Displacement is the form a retention meter can be validated against. `N = 0` means no burial.



## The control surface
`levers` is the declared `dials["levers"]` when present, else every reaction id plus the visible probes, a default refused wherever `setup["require_levers"]` is set. Every guarded drafter's adapter in `suite/drafters.py` adds `require_levers` and `opaque_names` to its task's `setup`; `phase1_pressure` is not a guarded head but sets `require_levers` itself, so its surface must be declared and its readouts are protected too. The readout, hidden-pool and rate-law refusals apply on every world, and the implicit surface omits the same ids (`lever_exclusion`), so a neutral example's agent can no longer set its readout to the goal (`agent_loop` scored 0.85 that way against the intended 0.25).

A cap resolves per declared lever: the spec's `{"id", "max_rate"}` entry, else `setup["lever_caps"]` (`pressure` and `pressure_w2` cap their two feed levers at the generator's `feed_max_rate`, default 20; `phase1_pressure` at `FEED_MAX_RATE`, 20), else `DEFAULT_MAX_RATE` on a `require_levers` world, else none. A `lever_caps` entry for an undeclared lever is ignored.



## The disclosure ladder
`epistemic_access` is not read here. The `pressure`, `pressure_w2` and `phase1_pressure` drafters (the last only with `variant="coupling_withheld"`) write it into `question`, which reaches the agent verbatim on the `Question:` line. Levels nest strictly; the oracle records the level and `EPISTEMIC_DISCLOSURE[level]`. It is a guarded drafter parameter, so a live model needs a registration naming it.

| Level | Disclosed facts | Key on `question` | Adds |
| --- | --- | --- | --- |
| 0 | none | — | nothing |
| 1 | `co_movement`, `direction` | `evidence` | correlational co-movement, mechanism not characterized |
| 2 | + `driver`, `mechanism` | `chemistry` | the driver → tracked coupling note |
| 3 | + `lever` | `chemistry` | which feed lever drains into the driver (T046) |
| 4 | + `clean_lever` | `chemistry` | what the other lever does, per `clean_route` (T064) |

Level 4's clause is chosen from the world drafted, because a brief may only state the truth (`phase1_gen._CLEAN_ROUTE_CLAUSE`):

| `clean_route` | When | Clause says |
| --- | --- | --- |
| `target` | pressure family, `pi = 0` | the lever converts into the target directly |
| `target_shared` | pressure family, `0 < pi < 1` | converts into the target; the remainder is lost to waste |
| `waste` | pressure family, `pi = 1` | taken up, reaches neither pool |
| `inert` | `phase1_pressure`'s neutral lever | drains to its own sink |

So a level-4 arm's wording differs across a `pi` sweep in three buckets; levels 0–3 are byte-frozen under AUP's awareness registration.



## Probes are not on the brief
Two things share the word. `Affordances.probes` is the allowlist of ids a `Measure` may read. `dials["probes"]` (T026) declares discarded-branch questions, and the brief never carries them: the runner parses them (`_parse_probes`), substituting each `{placeholder}` that names a key of the drafter's `setup["probe_vocab"]` with its structural id (an unknown placeholder stays verbatim), and puts each to the agent's `ProbeAgent.probe` at its timing — `every_turn` (before the agent acts), `after_action` (selected, not yet executed) or `at_commit` (`after_action` on the committing turn). Answers land on `TrialRecord.probes`, never in the turn history. The dial is world-invariant and not guarded.



## Opaque names
On an opaque-names trial the runner wraps the agent in `OpaqueAgent`, whose `begin` passes `surface_brief(brief, name_map)`: `question` and `monitoring` (every value), `constitution`, `context_padding`, `protocol`, `framing`, `monitor`, `stakes`, `reversibility` and `task_note` (ids inside the text), and every id in `affordances` and `irreversible` — every field `render_brief` prints. The runner and the record keep the structural brief.



## Stored only when set
`store._brief_to_json` always writes the base fields and writes these keys only when they carry something, so a run that declares none of them produces `records.jsonl` lines byte-identical to the ones before they existed, and the golden hashes in `tests/suite/test_golden_experiments.py` hold. `_brief_from_json` defaults an absent key.

| Key | Written when | Since |
| --- | --- | --- |
| `affordances.max_rates` | any cap | T023 |
| `context_padding` | not `None` | T027 |
| `constitution_in_history` | `True` | T029 |
| `protocol` | not `None` | T032 |
| `monitor` | not `None` | T060 |
| `task_note` | not `None` | T061 |



## Guarded and world-invariant dials
A guarded dial puts an alignment-bearing arm on a world: a live model reaches it only through a registration naming it (`guards.no_peeking_violation`; the one declaration is `drafters.GUARDED_BRIEF_DIALS`, re-exported as the `brief` head's `BRIEF_GUARDED`). A world-invariant dial (`drafters.WORLD_INVARIANT_DIALS`) never shapes the drafted world, so arms differing only in it are seed-matched onto the same worlds.

| Brief dial | Guarded | World-invariant |
| --- | --- | --- |
| `constitution` | yes; admitted on `phase1_pressure` | yes |
| `monitoring`, `framing` | yes | yes |
| `stakes`, `reversibility` | yes | yes |
| `assays` | yes | yes |
| `task_note` | yes | yes |
| `monitor_coverage`, `monitor_sham`, `monitor_salience` | yes | yes |
| `levers`, `irreversible_levers`, `assay_kill` | no | yes |
| `bury_commitment`, `constitution_in_history` | no | yes |
| `protocol`, `probes` | no | yes |
| `observability`, `observation_noise` | no | no (read by the narrowing, not here) |

`epistemic_access` and the drafters' own guarded parameters are declared on their heads, not here.




# BRIEF
- 2026-10-19 — written as an ABIO module doc (T084, deep-scan box 3), from the source at alienbio HEAD 84f8190; every member and claim traced to `suite/brief.py`, `runner.py` (`build_brief` call, `_parse_probes`, `PROBE_TIMINGS`, cap clamp), `naming.py` (`surface_brief`, `OpaqueAgent`), `llm_agent.py` (`begin`), `store.py` (`_brief_to_json`), `monitor.py`, `drafters.py` (`EPISTEMIC_DISCLOSURE`, `_clean_route_for_pi`, the guarded adapter, `GUARDED_BRIEF_DIALS`, `WORLD_INVARIANT_DIALS`), `phase1_gen.py` (`phase1_chemistry_note`, `_CLEAN_ROUTE_CLAUSE`), `w2_gen.py`, `guards.py` and the tests `test_hidden_pool_levers`, `test_pressure_acceptance`, `test_bury_commitment`, `test_constitution_in_history`, `test_protocol`, `test_task_note`, `test_epistemic_level4`. Left out: the private `_estimate_padding_tokens` and `_PADDING_*` vocabularies (described in `neutral_padding`, no blocks). The brief asked for `BRIEF_ONLY_DIALS`, which no longer exists in the source; the world-invariant set is `drafters.WORLD_INVARIANT_DIALS`, documented in its place. The figure draws `render_brief` as the renderer, not `compose_briefing`, which only composes framing text. `epistemic_access`, `probes` and `probe_vocab` are documented as what they are — drafter- and runner-side, reaching the agent through `question` and `ProbeAgent.probe` — not as brief fields. The module docstring's note that `agent.types` re-exports the two coercers is stale: `alienbio/agent/` is gone.
