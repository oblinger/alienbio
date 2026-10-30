---
description: "`ExperimentSpec`: one run as data — its 31 fields in six groups, the YAML `!experiment` and Python forms, the `__post_init__` normaliser and field validators both forms share, where a dial may live, `estimate_cost` and `CostEstimate`, and the spec's view on the manifest. Source: `src/alienbio/suite/spec.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO suite](ABIO%20suite.md) → [ABIO ExperimentSpec](ha://p/ABIO%20ExperimentSpec) 
# ABIO ExperimentSpec
The declared shape of one experiment, a frozen dataclass naming the world to draft, the dials to sweep and hold, the agent and its budget, the run's controls and its price: everything `preflight`, the condition grid and the manifest read, so that a run is a file you can review, diff and re-run.

![ABIO ExperimentSpec](ABIO%20ExperimentSpec.svg) 
*Where a dial lives* is the topic that governs the dials group; *Expected turns and the estimate* governs the cost group and the `estimate_cost` reader; *The two forms and the round trip* governs the left column: only the YAML path passes through `spec_from_dict`, and both reach the same validators in the constructor.

`suite/spec.py` holds the spec, its dict codec and validators, `load_spec`, `agent_kinds_in_play`, and the dry-run `estimate_cost` with the `CostEstimate` it returns (split out of `experiment.py` in T058; `experiment.py` re-exports every name). This page covers those. The `!experiment` head, `load_experiment` and `spec_to_text` live in `suite/expr_experiment.py`; the dial sets (`WORLD_INVARIANT_DIALS`, `EPISODE_DIALS`, `FACTORY_DIALS`, `runtime_dials()`) in `suite/drafters.py`; the seventeen checks a spec meets before spend are [ABIO Guards](ABIO%20Guards.md); the factory that reads the agent-side fields is in `suite/agents.py`, the agent itself [ABIO LLMAgent](ABIO%20LLMAgent.md); `condition_grid` and the seed matching in `suite/mass_trial.py`; the manifest in `suite/store.py`; each trial's record is [ABIO TrialRecord](ABIO%20TrialRecord.md). The subsystem view is [ABIO-Experiment](../../ABIO%20Architecture/ABIO-Experiment.md); the operator's view of the experiment file is [ABIO Suite Runtime](../../ABIO%20Architecture/ABIO%20Suite%20Runtime.md) § Experiments as artifacts.



## ExperimentSpec Interface
A frozen dataclass whose methods are `__post_init__` and the `_validate` it calls, the normaliser both forms pass through: it adds the idle arm under `idle_baseline`, derives (or checks) `expected_turns`, and runs every field check ([Refused at load, refused at preflight](#refused-at-load-refused-at-preflight)), normalising as it goes (floats, a plain-dict schedule, a parsed `PowerDesign`), idempotently. [spec_from_dict](#^spec-from-dict) only reshapes a dict into constructor arguments ([The two forms and the round trip](#the-two-forms-and-the-round-trip)). Six fields are required (`name`, `axes`, `drafter`, `agent`, `trials_per_condition`, `base_seed`); the rest default as listed. Fields are grouped here as the figure groups them, not in source order.

| ExperimentSpec | |
| --- | --- |
| [name](#^name) | The run's name; default output folder |
| [drafter](#^drafter) | The `DRAFTERS` key that draws each world |
| [trials_per_condition](#^trials-per-condition) | Trials in each grid cell |
| [base_seed](#^base-seed) | Root of every trial seed |
| [out_dir](#^out-dir) | Default output folder |
| [axes](#^axes) | The swept dials, in sweep order |
| [fixed_dials](#^fixed-dials) | Dials applied to every cell, never keyed |
| [drafter_kwargs](#^drafter-kwargs) | Keywords splatted into the drafter head |
| [matched_dials](#^matched-dials) | Extra swept dials kept out of the seed |
| [idle_baseline](#^idle-baseline) | Add the matched idle arm |
| [agent](#^agent) | The `AGENTS` kind every cell runs |
| [model](#^model) | The pinned model id for a live arm |
| [memory](#^memory) | History window: full, none or k turns |
| [compact_at](#^compact-at) | Turn at which a summary displaces history |
| [compact_budget](#^compact-budget) | Summarizer output budget |
| [history_token_limit](#^history-token-limit) | Fill-driven truncation limit |
| [max_tokens](#^max-tokens) | Flat per-turn output budget |
| [output_schedule](#^output-schedule) | Deep and shallow per-turn budgets |
| [token_ceiling](#^token-ceiling) | Per-trial runaway token guard |
| [temperature](#^temperature) | Sampling temperature or `provider-fixed` |
| [top_p](#^top-p) | Nucleus sampling parameter |
| [concurrency](#^concurrency) | Trials in flight at once |
| [design](#^design) | The committed statistical design |
| [key_readout](#^key-readout) | The readout drawn as the key figure |
| [cost_ceiling_usd](#^cost-ceiling-usd) | Spend at which the grid stops |
| [price_usd_per_mtok](#^price-usd-per-mtok) | Price for models the table lacks |
| [expected_turns](#^expected-turns) | Turns the estimate prices per trial |
| [expected_prompt_tokens](#^expected-prompt-tokens) | Prompt tokens per turn, for the estimate |
| [expected_output_tokens](#^expected-output-tokens) | Output tokens per turn, floor |
| [expected_cache_hit_rate](#^expected-cache-hit-rate) | Cached share of input, for the estimate |
| [registration](#^registration) | The pre-registration id claimed |
| [validation](#^validation) | Rule set: `run` or `recorded` |
| [recorded_warnings](#^recorded-warnings) | Run-only rules a recorded spec breaks |
| [source](#^source) | The file a loaded spec came from |

**name**`: str`
    The experiment's name, printed by `--dry` and written as the manifest's `name`; with no `out_dir` anywhere the run writes to `runs/{name}`. ^name

**drafter**`: str`
    A `DRAFTERS` key. The YAML form takes it from the head of the quoted `task:` call, which must be a drafter head; the Python form checks nothing, and an unknown name refuses at the `draft` check. ^drafter

**trials_per_condition**`: int`
    Trials per grid cell, a positive int (refused at construction otherwise), and at least a declared [design](#^design)'s required n; a resume may raise it without counting as drift. ^trials-per-condition

**base_seed**`: int`
    Every trial's seed is `Seed(base_seed).child(f"{label}/{i}")`, the label built from the condition key less the matched dials ([The condition grid](#the-condition-grid)). An int; a bool or float is refused at construction. ^base-seed

**out_dir**`: Optional[str] = None`
    The output folder when the caller passes none; `run_experiment(out_dir=…)` and `--out` win. ^out-dir

**axes**`: tuple[tuple[str, tuple[Any, ...]], ...]`
    The swept dials as `(name, levels)` pairs in declared order; one condition cell per level combination, each level on the record's `condition_key`. `spec_from_dict` reads a mapping and keeps its insertion order ([Where a dial lives](#where-a-dial-lives)). `_validate_axes` refuses at construction an axis declared twice, an axis with no levels, and a repeated level, judged by `trial.frozen_value` (what a summary buckets as one cell), not `repr`: `1`/`1.0`/`True`, or two dict levels differing only in key order, are one level, and with `nan_equal=True` so `[nan, nan]` is a repeated level and refuses; numpy levels are read in their Python form first (`trial.plain_value`) (T091 B1/B5/B10, G1/G2, K G1). ^axes

**fixed_dials**`: Mapping[str, Any] = {}`
    Dials applied to every cell, merged under the cell's own as `{**fixed_dials, **condition}`; never on a condition key. A dial both fixed and swept refuses at construction, since the axis would silently override the fixed value (T091 D10). A factory dial here is refused at the `dials` check (since `c63ad42`). ^fixed-dials

**drafter_kwargs**`: Mapping[str, Any] = {}`
    Keywords splatted into the drafter head on every draft: generator settings (`feed_max_rate`, `score_read`, `hop_delay_s`, `certainty_windows` …) that no other reader sees. A head dial placed here is applied and counted in play by the guards (T066); an episode dial here is refused. ^drafter-kwargs

**matched_dials**`: tuple[str, ...] = ()`
    Swept dials, beyond `WORLD_INVARIANT_DIALS`, to keep out of the seed label, so their arms draw the same worlds (M36.3, EXP-6's `ill_posed` trap). The constructor refuses a name that is not a swept axis. ^matched-dials

**idle_baseline**`: bool = False`
    Ask for the do-nothing twin of every cell. `__post_init__` appends an `agent` axis `(agent, "idle")`, or, when an `agent` axis is already swept, appends `"idle"` to its levels (T091 B13), for both forms (M45.7). Nothing is added when `agent` is `idle` with no agent axis or the swept axis already holds `idle`, which makes it idempotent, so a reload does not add it twice (`60db002`; before it, only `spec_from_dict` added the axis). ^idle-baseline

**agent**`: str`
    The `AGENTS` kind (`llm`, `idle`, `survey-commit` …) every cell runs unless an `agent` axis sweeps it. The constructor checks `agent` axis levels against `AGENTS` but not this scalar; the YAML head resolves it by name, and the `agent` check catches the rest. ^agent

**model**`: Optional[str] = None`
    The live model id; `None` means `PINNED_MODEL` (`claude-sonnet-5`) on a live arm. The constructor refuses an unpinned id here and on every `model` axis level: a `-latest` alias, or an undated id missing from `models_snapshot.json`. ^model

**memory**`: Union[str, int] = "full"`
    The live agent's history window: `"full"`, `"none"` or an int k. A `memory` axis overrides it per cell, is priced per level and recorded per line. The field is checked at construction by `LLMAgent`'s own validator (`validate_agent_config`); a swept level at the `agent` check. ^memory

**compact_at**`: Optional[int] = None`
    T049: the 0-based turn at which a model-written summary replaces all earlier history; a trial dial of the same name overrides. A positive int or unset, checked at construction; the `inert-arm` check refuses a value no cell's episode reaches. ^compact-at

**compact_budget**`: Optional[int] = None`
    T049: `max_tokens` for the summarizer call; a same-named dial overrides. A positive int or unset, checked at construction. ^compact-budget

**history_token_limit**`: Optional[int] = None`
    T049: keep only the newest history entries whose estimated tokens fit; a same-named dial overrides. A positive int or unset, checked at construction. One forgetting trigger per arm. ^history-token-limit

**max_tokens**`: Optional[int] = None`
    T059: a flat per-turn output cap sent to the provider; a same-named dial overrides. Positive int; refused at load beside an `output_schedule`. ^max-tokens

**output_schedule**`: Optional[Mapping[str, int]] = None`
    T059: `{"every", "deep", "shallow"}`, every value a positive int; turns `0, every, 2·every …` get `deep` output tokens, the rest `shallow`. Validated at load by `validate_output_budget` and stored as a plain dict. ^output-schedule

**token_ceiling**`: Optional[int] = None`
    Handed to each `LLMAgent`, which aborts the trial once its metered tokens pass it: a runaway guard per trial, not the run's spend gate. A positive int or unset, checked at construction. ^token-ceiling

**temperature**`: Optional[Union[float, str]] = None`
    M45.18: a number in `[0, 1]`, or the literal `"provider-fixed"` for a model with no sampling knob (the Claude 5 API refuses the parameter). Range and literal are checked at load; absence on a live arm refuses at the `sampling` check. Rides the manifest and every live record line. ^temperature

**top_p**`: Optional[float] = None`
    M45.18: a number in `[0, 1]`, optional; refused at load beside `temperature: provider-fixed`. ^top-p

**concurrency**`: int = 1`
    M45.6: trials in flight at once, a positive int. The ceiling check runs as each unit lands and as each worker starts, so a stop can overshoot by the units already running. ^concurrency

**design**`: Optional[PowerDesign] = None`
    M46.9: the statistical design. The constructor parses a mapping (a `PowerDesign` passes as is), refuses a `primary_contrast` that is not a swept axis and two of its levels (a level matched by its `trial.frozen_value`, as the grid buckets it), and refuses `trials_per_condition` below the design's required n, naming the number. ^design

**key_readout**`: Optional[str] = None`
    The `suite.plots.PLOTTERS` name whose figure becomes `key.png`; `None` takes the first readout the records carry, in report order. Refused at load when not a `PLOTTERS` name. ^key-readout

**cost_ceiling_usd**`: Optional[float] = None`
    M45.5: positive, or absent. `run_experiment`'s `stop()` halts the grid once the priced usage of landed records reaches it; nothing compares it with the estimate ([Expected turns and the estimate](#expected-turns-and-the-estimate)). ^cost-ceiling-usd

**price_usd_per_mtok**`: Optional[Union[tuple[float, float], Mapping[str, tuple[float, float]]]] = None`
    USD per million tokens for models absent from the published price table, never a reprice (`f0604df`, T091 Q2): a pair `(input, output)` of non-negative numbers prices every unpriced model in play; a mapping `{model_id: (input, output)}` prices them by name. A mapping naming a published model refuses at construction; a pair beside a published live model refuses in `estimate_cost` (the `price` check), naming the models. `spec_to_dict` writes the mapping as `{model: [in, out]}`. ^price-usd-per-mtok

**expected_turns**`: Optional[int] = None`
    Turns per trial the estimate prices. Left `None`, `__post_init__` derives it from the declared episode budget, for both forms; a stated value is checked as a positive int. Always an int after construction (`4b994c2`; before it a directly built spec kept the literal 8) ([Expected turns and the estimate](#expected-turns-and-the-estimate)). ^expected-turns

**expected_prompt_tokens**`: int = 1500`
    Prompt tokens per turn before history, for the estimate; a positive int. ^expected-prompt-tokens

**expected_output_tokens**`: int = 300`
    Output tokens per turn, for the estimate; a positive int. A floor: a larger declared `max_tokens` or `output_schedule` level replaces it. ^expected-output-tokens

**expected_cache_hit_rate**`: float = 0.0`
    M45.19: the share of input the estimate prices at the cache-read rate (10% of input), measured by a pilot; a number in `[0, 1]`. ^expected-cache-hit-rate

**registration**`: Optional[str] = None`
    T030: an id in `catalog/registrations.yaml`. Only checked as a non-empty string at load; resolved by `registration_admission` at the `registration` check and again for the manifest, where the resolved entry is written. Licensed record lines carry the id. ^registration

**validation**`: Literal["run", "recorded"] = "run"` (`compare=False`, `repr=False`)
    Which rule set the constructor applies (T091 Y2). `"run"` refuses every rule and is the only mode `preflight`, and so `run_experiment`, accepts. `"recorded"` is how `spec_from_manifest(current=False)` rebuilds a finished run's spec for `aggregate` and `bio suite aggregate|report`: each rule in [RECORDED_NOTE_RULES](#^recorded-note-rules) lands on `recorded_warnings` instead of raising, so a run written under an older rule set still reads. Still refused in both modes: `axes` not a mapping, a level list not a list, a repeated axis name, an unknown `agent` level, a non-string model, bad field types. Any other value raises. ^validation

**recorded_warnings**`: tuple[str, ...] = ()` (`init=False`, `compare=False`, `repr=False`)
    The refusal message of each run-only rule a `validation="recorded"` spec broke, in check order; always `()` in `"run"` mode, which raises instead. `bio suite aggregate` prints them to stderr, `bio suite report` at the top of the report and `report.txt` ([ABIO SuiteCmd](../ABIO%20alienbio/ABIO%20SuiteCmd.md)). ^recorded-warnings

**source**`: Optional[Mapping[str, Any]] = None` (`init=False`, `compare=False`, `repr=False`)
    `{"spec_path", "helper_modules"}` when `load_spec` read the spec from a file: that file and every `.py` its trusted `_includes_` ran, each relative to the repo root when under it, else absolute (T091 E1). Not part of the spec's value: never compared, never in `spec_to_dict`. Not an init field (T091 Y3): `dataclasses.replace` builds a spec no file describes, so the copy carries `None` and its manifest names no `spec_path`; only `load_spec`, through [with_source](#^with-source), sets it. The manifest carries both keys so `bio suite resume` can reload the file and `aggregate|report` can run the helpers. `None` for a Python-built spec. ^source



## CostEstimate Interface
A frozen dataclass: the dry-run price of a spec's grid, built only by [estimate_cost](#^estimate-cost). The `price` check computes it, `Preflight.estimate` carries it, `--dry` prints it and the manifest pins it as `cost_estimate` (`dataclasses.asdict`) at the start of the run. Advisory: nothing gates on `usd`.

| CostEstimate | |
| --- | --- |
| [llm_trials](#^llm-trials) | Trials whose agent resolves to `llm` |
| [turns_per_trial](#^turns-per-trial) | The spec's `expected_turns` |
| [calls_per_trial](#^calls-per-trial) | Model calls one live trial is priced at |
| [input_tokens](#^input-tokens) | Total input tokens priced |
| [output_tokens](#^output-tokens) | Total output tokens priced |
| [usd](#^usd) | The projected cost |
| [model](#^costestimate-model) | The model priced, or `mixed(...)` |
| [formula](#^formula) | The arithmetic as one line |

**llm_trials**`: int`
    `(condition, trial)` units with a live agent: with an `agent` axis, its `llm` levels × the other axes' cells × `trials_per_condition`; else every cell when `agent == "llm"`; else 0. ^llm-trials

**turns_per_trial**`: int`
    `spec.expected_turns`, set even when `llm_trials` is 0. ^turns-per-trial

**calls_per_trial**`: int = 0`
    One call per turn, plus each per-turn probe's forked call every turn, each `at_commit` probe once, and one summarizer call when `compact_at` is declared (the count `bury_commitment` filler is multiplied by); 0 on an all-scripted spec. The only field with a default, added with the probe pricing (`245f79c`). ^calls-per-trial

**input_tokens**`: int`
    Per-trial input tokens (the main line averaged over `memory` axis levels, plus probe and summarizer calls) × `llm_trials`, rounded; 0 with no live trial. ^input-tokens

**output_tokens**`: int`
    Per-trial output tokens (per-turn output × turns, plus probe and summarizer replies) × `llm_trials`, rounded; 0 with no live trial. ^output-tokens

**usd**`: float`
    The sum over model levels of `cost_usd` on each level's equal share, cached input at the cache-read rate; `0.0` with no live trial. ^usd

**model**`: Optional[str]`
    `None` with no live trial; the single id priced (`spec.model`, else `PINNED_MODEL`); or `"mixed(a, b)"` under a `model` axis. ^costestimate-model

**formula**`: str`
    One line naming trials, turns, memory levels, the extra probe and summarizer calls and the `bury_commitment` filler (`N calls/trial incl. …`), per-trial tokens, cache hit and prices, ending `= $usd`; `"0 llm trials -> $0.00"` when there are none. `--dry` prints it after the total. ^formula



## spec Interface
The module-level functions. A spec's fields are validated in one place, `ExperimentSpec.__post_init__`, for both forms; `spec_from_dict` builds through it, and the YAML head, `bio suite resume` and `aggregate` all build through it. `experiment.py` re-exports these and the private helpers `require_pinned_model` (also called by the `llm` agent factory per trial) and `_validate_matched_dials`; `expr_experiment.py` imports `default_expected_turns` so `spec_to_text` can tell a stated `expected_turns` from a derived one. No `__all__`.

| spec | |
| --- | --- |
| [spec_to_dict](#^spec-to-dict) | Spec to a JSON-able dict |
| [spec_from_dict](#^spec-from-dict) | Dict to a validated spec |
| [with_source](#^with-source) | Stamp a spec with its file |
| [RECORDED_NOTE_RULES](#^recorded-note-rules) | Rules recorded mode notes |
| [load_spec](#^load-spec) | Load an experiment file |
| [agent_kinds_in_play](#^agent-kinds-in-play) | Every agent kind a run can build |
| [estimate_cost](#^estimate-cost) | Price the grid without running it |

**spec_to_dict**`(spec: ExperimentSpec) -> dict[str, Any]`
    Every field under its own name, `axes` as a `{name: [levels]}` mapping, tuples as lists, `design` through `PowerDesign.to_dict()`. What the manifest stores as `spec` and hashes as `spec_sha256`. Emits `expected_turns` as a number always, so reloading keeps the value rather than re-deriving it; with `__post_init__` deriving it for both forms, `spec_from_dict(spec_to_dict(s)) == s` for a spec built either way. ^spec-to-dict

**spec_from_dict**`(d: Mapping[str, Any], *, validation: Literal["run", "recorded"] = "run") -> ExperimentSpec`
    The dict codec's inbound half: reads the required keys (`KeyError` for a missing one), refuses an `axes` that is not a mapping or a level list that is not a list (a string included) in either mode, turns the `axes` mapping into ordered tuples, `None` for an empty `drafter_kwargs`/`fixed_dials`, coerces `idle_baseline` to bool, passes an unset `expected_turns` as `None`, and hands the rest to the constructor, whose validators raise `ValueError` naming the field. Optional keys default as the class does ([Refused at load, refused at preflight](#refused-at-load-refused-at-preflight)). `validation` is passed to the constructor: `"recorded"` for a finished run's manifest spec read back by a read-only verb. ^spec-from-dict

**with_source**`(spec: ExperimentSpec, source: Optional[Mapping[str, Any]]) -> ExperimentSpec`
    Sets `spec.source` in place on the frozen spec and returns it (T091 Y3); `load_spec` stamps its result this way. ^with-source

**RECORDED_NOTE_RULES**`: tuple[str, ...]`
    The run-only rules `validation="recorded"` notes rather than refuses, each one that exists to stop a RUN and has tightened since runs were recorded: `fixed-and-swept` (D10), `empty-axis` (B10), `repeated-level` (equal or bucket-equal, B5/G1/G2), `published-price-override` (Q2), `unpinned-model` (the models snapshot moves), `under-powered-design` (M46.9). Documentation only; the validators route these through one `refuse` callback. ^recorded-note-rules

**load_spec**`(path: Union[str, Path]) -> ExperimentSpec`
    Hands the file to `expr_experiment.load_experiment`, trusted when it sits under the repo's `catalog/` (it may then `_includes_` Python), untrusted otherwise. Raises `ExprError` for a non-experiment document, the pre-M47.4 flat form, a dial no head declares, an unread axis, or any `spec_from_dict` refusal. Stamps the result's `source` through `with_source`. ^load-spec

**agent_kinds_in_play**`(spec: ExperimentSpec) -> frozenset[str]`
    `spec.agent` plus every `agent` axis level. The no-peeking and sampling checks test it for `"llm"`; the manifest uses it to name the model in force. ^agent-kinds-in-play

**estimate_cost**`(spec: ExperimentSpec) -> CostEstimate`
    Prices the grid from its shape alone, probe and summarizer calls included: no world drafted, no trial run. With no live trial it returns $0 and never looks up a price; otherwise it prices every model level and raises `ValueError` from `price_for` when one has no published price and no override, or itself when a pair override sits beside a published model ([Expected turns and the estimate](#expected-turns-and-the-estimate)). ^estimate-cost




# ExperimentSpec Semantics

## The two forms and the round trip
A spec comes from one of two places; both pass the same field validators at construction, and only the YAML form also checks dial placement.

| | YAML `!experiment` | Python `ExperimentSpec(...)` |
| --- | --- | --- |
| entry | `load_spec(path)`, `bio suite run <spec>` | the constructor; launchers and tests |
| dial placement | which quoted call a keyword sits in: `task:` (drafter dials), `brief:`, `episode:` | the caller fills `axes`, `fixed_dials`, `drafter_kwargs` |
| axes | free names in a quoted call, each bound to the dial of the same name; factory dials sweep with no binding | whatever the caller lists |
| refused at build | an undeclared dial, a dial on two calls, an unread axis, a nested expression | an unknown keyword (`TypeError`) |
| field checks | every one, at construction (`ValueError`) | the same, with the same message |
| `expected_turns` | derived from the declared budget (`__post_init__`) | the same |
| `idle_baseline` | expanded into an `agent` axis (`__post_init__`) | the same |

The `!experiment` head (`expr_experiment.experiment`) sorts each keyword of a quoted call into a fixed dial or a swept axis with `_split_call`, refuses an axis that no call reads unless it is in `EXPERIMENT_AXES` (`FACTORY_DIALS` since `d53605e`; it was `{agent, model}`, so a YAML `memory` axis was refused), then passes only the keywords the file set to `spec_from_dict`. Whatever the form, `preflight` runs the same nineteen checks before spend, so the dial-placement checks the head makes are caught there for the Python form too. `expected_turns` and `idle_baseline` are derived by `__post_init__` for both forms since `4b994c2` and `60db002`, and every field check moved from `spec_from_dict` into the constructor after them, so a Python-built `concurrency=0` or `temperature=2.0` refuses at construction, not at preflight or mid-run.

`spec_to_dict` and `spec_from_dict` are inverses for a spec built either way. `spec_to_text(spec)` (in `expr_experiment.py`) renders a spec back as an experiment file, with the declared contract `load_experiment(text=spec_to_text(spec)) == spec`: each fixed dial and axis goes on the call whose head declares it, the agent side first (a drafter that also declares `max_turns` only reads it), a dial no head declares raises, an `idle_baseline` axis is left for the load to re-add, and a scalar is written only when it differs from its default. `expected_turns` is written only when it differs from what the derivation gives (T066: the sentinel was the literal 8, so a stated 8 beside a 20-turn episode came back 20); `registration` is written (T066: it was dropped, so a licensed spec round-tripped unlicensed).



## Where a dial lives
A trial's dial vector is `{**fixed_dials, **condition}`, and the drafter closure also splats `drafter_kwargs` into the head; the agent factory reads its own dials off that vector, falling back to the spec field. So a name can arrive four ways, and which one is legal depends on its class ([ABIO Guards](ABIO%20Guards.md) § Dials in play has the per-class table).

| Place | Applied by | Read by guards | Refused there | Since |
| --- | --- | --- | --- | --- |
| `axes` | the drafter, runner, brief and factory, one level per cell; on the condition key | every check | a name nothing reads (`dials`) | M46.5 |
| `fixed_dials` | the same readers, every cell; never keyed | every check | a name nothing reads; a factory dial | factory refusal `c63ad42` |
| `drafter_kwargs` | the drafter head only | head dials counted in play | an episode dial (`max_turns`, `sim_steps`, `sim_dt`) | T066 |
| spec field (`agent`, `model`, `memory`, the forgetting and output-budget fields) | the agent factory; a same-named dial overrides | `agent_kinds_in_play`, `estimate_cost`, `agent`, `inert-arm` | n/a | M46.8, T049, T059 |

The factory-dial refusal exists because the guards and the estimate read the spec field and the axes, while the factory reads the merged vector: `fixed_dials: {agent: llm}` passed every check, estimated $0.00 and ran a paid trial. A factory dial is therefore a spec field when fixed and an axis when swept, never a fixed dial. In the YAML form the same split is structural: a factory dial is a top-level `!experiment` keyword or a top-level `axes` entry, every other dial a keyword of the quoted call whose head declares it.



## The condition grid
`run_experiment` hands `list(spec.axes)` to `MassTrialRunner.run`, whose `condition_grid` takes the product of the levels in declared order and sorts each cell's key by dial name. `fixed_dials` ride as `extra_dials` and never reach a key. Each cell runs `trials_per_condition` trials, trial `i` seeded from `base_seed.child(f"{label}/{i}")`, where the label drops `WORLD_INVARIANT_DIALS` plus `matched_dials`: cells that differ only in those (agent, model, memory, the brief-side dials, the output budget, the in-world monitor …) draw byte-identical worlds, so an arm contrast is paired by construction. `idle_baseline` uses exactly this: `agent` is world-invariant, so each idle cell runs on its live twin's worlds.



## Expected turns and the estimate
`expected_turns` is the number of turns `estimate_cost` prices each live trial at. When none is stated, `ExperimentSpec.__post_init__` derives it with `default_expected_turns`, whichever form built the spec: the largest of a positive int `fixed_dials["max_turns"]` and every positive int `max_turns` axis level (T066: the axis wins at run time, so "read high" means the maximum of both), else the default of `runner.run`'s `max_turns` (50; it was the literal 8, which priced a 20-turn episode at 40% and a no-budget run at a sixth). An explicit `expected_turns` always wins.

| Term | Value |
| --- | --- |
| live trials | `llm` units only; scripted cells cost nothing |
| input per trial, `memory: full` | `P × Σ(1 + t/2)` over `t < T` |
| input per trial, `memory: none` | `P × T` |
| input per trial, `memory: k` | `P × T × (1 + min(k, T−1)/2)` |
| `memory` axis | the mean of the levels' inputs (round 4: one level priced a none/full ladder ~5.75× low) |
| output per turn | the largest of `expected_output_tokens`, `max_tokens` and every `deep`/`shallow` value, spec field or axis level (T066: an 8192-token arm was priced at 300) |
| probes | the largest declared `probes` set (fixed dial or axis level): each `every_turn` / `after_action` probe repeats the main line's input and output (as if every turn acts), each `at_commit` probe adds one last-turn call (`245f79c`) |
| compaction | with `compact_at` declared (field or axis, latest level), one summarizer call: input `P × (1 + c/2)`, output the largest `compact_budget`, else the per-turn output (`245f79c`) |
| `bury_commitment` | T027's filler (estimated tokens) sits in the system prompt of every call, so it is added to the input of each of `calls_per_trial`; the fixed dial, or the mean of a swept axis's levels (`f0604df`, T091 Q8) |
| models | every `model` axis level with an equal share of the trials, else `spec.model`, else `PINNED_MODEL` (T051 box 4) |
| cache | `expected_cache_hit_rate` of input at 10% of the input price |

`P` is `expected_prompt_tokens`, `T` is `expected_turns`. Each rule reads high where the true count is unknown. `price_for` raises for a level with no published price unless `price_usd_per_mtok` prices it, a pair override beside a published model refuses (a published price is never replaced), and since the `price` check is `estimate_cost(spec)`, an unpriced level refuses before anything is drafted, not mid-grid after a paid call. `bio suite run --dry` prints `estimated cost: $… for N llm trials x T turns — <formula>`, or `$0.00, no llm arm`, or `unavailable (pricing refused above)`, then the ceiling. The estimate is advisory; spend is stopped only by `cost_ceiling_usd` at run time.



## The manifest's view of the spec
`store._build_manifest` writes the spec twice over: as data, `spec_to_dict(spec)` with its canonical-JSON `spec_sha256`, and as resolved facts a reader should not have to derive.

| Key | From the spec |
| --- | --- |
| `spec`, `spec_sha256` | `spec_to_dict`, hashed with sorted keys |
| `model` / `models` | the id in force: `spec.model`, else `PINNED_MODEL` with `llm` in play<br>under a `model` axis: `null`, the levels under `models` |
| `model_created_at` | the snapshot date of that single id |
| `memory` / `memories` | `spec.memory`; `null` with the levels under `memories` under a `memory` axis (since `d53605e`) |
| `temperature`, `top_p` | the fields as stated |
| `registration` | the resolved registry entry, not the bare id |
| `cost_estimate`, `cost_ceiling_usd` | `asdict(estimate_cost(spec))`, the ceiling |
| `design` | `PowerDesign.to_dict()` |

`bio suite resume <DIR>`, `aggregate` and `bio suite report` rebuild the spec through `spec_from_manifest`. `aggregate` and `report` (`current=False`) execute the manifest's `helper_modules` directly, so their `_includes_` register the run's drafter and agents, then build `manifest["spec"]` with `validation="recorded"`: the experiment file is never re-read, so a finished run whose yaml was since deleted, moved or edited still aggregates, and a rule the run predates is a note on `recorded_warnings`, not a refusal (T091 K E1, Y2). A helper that is missing, or lies outside the trusted `catalog/` root, refuses, naming it. `bio suite resume` (`current=True`) re-loads the file as it is now, strictly validated, so an edit to the yaml is drift and a missing file refuses, naming the path; a manifest with no `spec_path` (a Python-built or replaced spec) is read from its `spec`, strictly. The `resume` check compares the new spec to the stored one, allowing only more trials and added levels on an existing axis.



## Refused at load, refused at preflight
The constructor refuses what a field can be wrong about alone or beside another field, for both forms; `preflight` refuses what needs the registry, the heads, the agents or a drafted world.

| At construction (both forms) | At preflight (both forms) |
| --- | --- |
| unpinned `model` or `model` axis level | unresolvable or non-covering `registration` |
| unknown `agent` axis level<br>bad `trials_per_condition`<br>non-int `base_seed` | a live model on a guarded drafter or dial, unlicensed |
| `temperature`/`top_p` out of `[0, 1]`; `top_p` with `provider-fixed` | live arm with no `temperature` |
| malformed `max_tokens`/`output_schedule`, or both | unknown dial names<br>a factory dial in `fixed_dials`<br>an episode dial in `drafter_kwargs` |
| `matched_dials` naming an unswept axis<br>a repeated or empty axis, a repeated level<br>a dial both fixed and swept | guarded drafter with no list-valued `levers` |
| under-powered or mis-aimed `design`<br>bad `memory`<br>non-positive `token_ceiling` or forgetting field | unknown `agent`<br>cross-field forgetting config<br>inert `compact_at` |
| `key_readout` not a `PLOTTERS` name | unknown `drafter`; a world or brief that refuses to draft |
| non-positive `cost_ceiling_usd`, `concurrency`, `expected_*` counts; bad `price_usd_per_mtok`, or a mapping naming a published model; empty `registration` | unpriced model level; a pair `price_usd_per_mtok` beside a published live model<br>drifted spec, another `world_scheme` or a re-drafted world that differs, on resume<br>records already in `out_dir` |

Under `validation="recorded"` the [RECORDED_NOTE_RULES](#^recorded-note-rules) in the left column (fixed-and-swept, empty axis, repeated level, published price in a mapping, unpinned model, under-powered design) become `recorded_warnings`, and `preflight` refuses the spec outright.

Not validated in `spec.py`: the scalar `agent` (the `agent` check owns it) and the cross-field forgetting rules, which stay with the `agent` check because a swept axis may supply the partner field (`a4f3b63` moved each field's own shape into the constructor).




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084, deep-scan box 3), from the source at alienbio HEAD 866b390 (`spec.py` at `245f79c`, which landed during this work and added probe and summarizer pricing to `estimate_cost` and `calls_per_trial` to `CostEstimate`; the page describes it); every member and claim traced to `suite/spec.py`, with the seams checked against `expr_experiment.py` (`experiment`, `_split_call`, `EXPERIMENT_AXES`, `load_experiment`, `spec_to_text`), `experiment.py` (`run_experiment`, `stop()`, `aggregate`), `guards.py`, `drafters.py` (the dial sets), `agents.py` (the `llm` factory), `store.py` (`_build_manifest`), `mass_trial.py` (`condition_grid`, seed labels), `llm_agent.py` (`price_for`, `cost_usd`, `validate_output_budget`), `commands/suite_cmd.py` (`--dry`, `_resume`) and the experiment, round 4/5 and leftovers tests. `condition_grid` lives in `mass_trial.py`. Left out as members: the private validators (`_validate_*`, `_expected_output_tokens`, `default_expected_turns`, `require_pinned_model`, `_DATED_MODEL_RE`, `_REPO_ROOT`), named in prose where they decide behavior; `spec_to_text` and `load_experiment` are defined in `expr_experiment.py` and described, not given blocks. The figure's six field groups are my grouping, not the source's order.
- Divergences found, not fixed (reported to the caller): a directly built `ExperimentSpec` keeps `expected_turns = 8` (`spec.py` line 71) and `spec_to_dict` then pins that 8 through every reload, so a Python-form 20-turn live spec is estimated at 8 turns; a directly built spec with `idle_baseline=True` runs no idle arm, while `aggregate` and `bio suite resume` rebuild it through `spec_from_dict` with the extra `agent` axis (verified: `spec_from_dict(spec_to_dict(s)) != s`); `memory: k` with `k ≥ T−1` is priced at about twice `full`'s history term, though it sends the same history (line 645); `--dry` prints `model: None` for a live spec on the pinned default (`suite_cmd.py` line 122) while the estimate and manifest name `claude-sonnet-5`; the `experiment` head's docstring still says the axes are the calls' free names "plus agent / model" (`expr_experiment.py` line 572); `ABIO-Experiment` gives `spec.py` 577 lines and 30 fields (736 and 31 today), and its hypotheses table still lists the fixed `PINNED_MODEL` pricing and literal-8 rows.
- 2026-10-28 — four of the divergences above fixed (T084 follow-up): `expected_turns` and the idle arm are normalised in `ExperimentSpec.__post_init__` for both forms (`4b994c2`, `60db002`); `--dry` prints the model in force via the manifest's `_single_model` / `_model_axis_levels`, the `experiment` head's docstring names the factory dials, and `ABIO-Experiment`'s counts and hypotheses rows are current (one commit after those). The `memory: k ≥ T−1` over-price stands (it errs high).
- 2026-10-28 — every field check `spec_from_dict` ran (pinned model and `model`/`agent` axis levels, output budget, cost ceiling, price override, `expected_*` counts, design, `concurrency`, `matched_dials`, `key_readout`, sampling, `expected_cache_hit_rate`, `registration`) moved into `ExperimentSpec._validate`, called from `__post_init__`, so the Python form is refused with the same messages; `spec_from_dict` now only reshapes the dict. Still unvalidated in `spec.py`: `trials_per_condition`/`base_seed` beyond the design, the scalar `agent`, `memory`, `token_ceiling` and the forgetting fields (the `agent` check owns them, per arm).
- 2026-10-28 — refreshed against 0eb23e5 (`a4f3b63`): the constructor also refuses a bad `trials_per_condition`, `base_seed`, `memory`, `token_ceiling` and forgetting field; the refusal table and the not-validated line follow; `preflight` runs seventeen checks (the `labels` check, `1d46b37`), and the figure says so.
- 2026-10-29 — refreshed for `e5ea4d0` and `661005d` (T091 B1/B5/B10, B13, D10, E1, G1/G2): construction refuses a repeated or empty axis, a repeated level by `trial.frozen_value`, and a dial both fixed and swept; `idle_baseline` appends `idle` to a swept agent axis; new `source` field; resume reloads the spec file as it is now, aggregate the manifest's own spec.
- 2026-10-29 — refreshed for `fab20be` (T091 K E1, K G1): `spec_from_manifest` reloads the yaml for aggregate/report only when `helper_modules` is non-empty, always for resume; repeated axis levels are judged NaN-equal.
- 2026-10-29 — refreshed for `f0604df` and `1e08068`/`b6d1607` (T091 Q2, Q8, R2, Y1): `price_usd_per_mtok` may be a per-model mapping and never reprices a published model; the estimate adds `bury_commitment` filler to every priced call; the preflight column names the resume's scheme and re-draft refusals.
- 2026-10-29 — refreshed for `7fcdf33` (T091 Y2, Y3): new `validation` and `recorded_warnings` fields and `RECORDED_NOTE_RULES` (read-only verbs rebuild the manifest spec in recorded mode, run-only rules as notes); `spec_from_dict(validation=)` refuses a non-mapping `axes` or non-list levels in both modes; `source` is `init=False`, set only by the new `with_source`, so `replace` drops it; the manifest-view paragraph rewritten (helpers run directly, the yaml never re-read on a read). Figure: "31 fields" now reads "31 value fields" (34 with `validation`, `recorded_warnings`, `source`).
