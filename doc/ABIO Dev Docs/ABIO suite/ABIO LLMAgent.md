---
description: "`llm_agent`: the live-model agent — `LLMAgent` (history window, forgetting triggers, discarded-branch probes, token ceiling), `UsageMeter`, the Anthropic provider fn, prices, pinned models and the models snapshot, the per-turn output budget. Source: `src/alienbio/suite/llm_agent.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO suite](ABIO%20suite.md) → [ABIO LLMAgent](ha://p/ABIO%20LLMAgent) 
# ABIO LLMAgent
The real-model agent: `LLMAgent` turns each narrowed observation into one model call over the `LLMOp` seam, parses the reply into an `Action`, keeps its own turn history, and meters every token the provider reports.

![ABIO LLMAgent](ABIO%20LLMAgent.svg) 
*The history window and forgetting* is the topic that governs the turn-history rows (the constitution entry, the compaction summary); *Probes on discarded branches* governs the probe fork; *Metering and the two ceilings* governs `UsageMeter`.

`suite/llm_agent.py` holds the one agent that spends money, plus everything it needs to do so reproducibly: the `UsageMeter` it shares with its provider fn, `default_anthropic_llm_fn` (the live provider fn; with `fetch_models_snapshot`, the module's only network calls), the price table and `cost_usd`, the pinned-model id and the recorded `models.list` snapshot, the per-turn output budget, and the reply parsers. No framework test calls a live model: every `LLMAgent` in `tests/` takes a mock `llm_fn`, and `tests/conftest.py` strips both key variables and makes the real SDK clients raise `RuntimeError("live provider in tests")`; the one end-to-end test is marked `@pytest.mark.live` and runs only with `ABIO_LLM_E2E=1` and a key ([ABIO Testing Guide](../../ABIO%20Guides/ABIO%20Testing%20Guide.md)). The turn loop that calls `begin`, `act`, `notice` and `probe` is [ABIO Runner](ABIO%20Runner.md); the brief rendered into the system prompt is [ABIO TaskBrief](ABIO%20TaskBrief.md); the surface-name wrapper `OpaqueAgent` that sits between the runner and this agent is [ABIO NameMap](ABIO%20NameMap.md). The `Agent`, `SessionAgent` and `ProbeAgent` protocols and the action types are in `suite/agent.py`; `LLMOp` and `canonical` in `suite/ops.py`; the `llm` agent factory in `suite/agents.py`; the dry-run price in `suite/spec.py` (`estimate_cost`). The subsystem view is [ABIO-Runtime](../../ABIO%20Architecture/ABIO-Runtime.md); the operator's view is [ABIO Suite Runtime](../../ABIO%20Architecture/ABIO%20Suite%20Runtime.md).



## LLMAgent Interface
A plain class that satisfies `Agent`, `SessionAgent` and `ProbeAgent` structurally; `runner.run` detects the last two by `isinstance`. It holds no handle on the world, the oracle or the answer key: everything it sends is the brief, the narrowed observations, its own past actions and the runner's verdicts on them. `llm_fn` is always injected, so the class itself never opens a connection. One instance per trial: the `llm` factory in `suite/agents.py` builds a fresh agent and a fresh `UsageMeter` for every `(condition, trial)`.

| LLMAgent | |
| --- | --- |
| [LLMAgent](#^init) | Build an agent over an injected provider fn |
| [brief](#^brief) | The brief `begin` received |
| [begin](#^begin) | Compose the system prompt from the brief |
| [act](#^act) | One turn: render, call, parse, record |
| [notice](#^notice) | Fold the runner's verdict into history |
| [probe](#^probe) | Answer a question on a discarded branch |
| [meter](#^meter) | The usage meter shared with the provider fn |
| [usage](#^usage) | Totals, per-turn and per-probe usage |
| [prompt_texts](#^prompt-texts) | Every prompt actually sent |
| [prompt_hashes](#^prompt-hashes) | One sha256 per prompt sent |
| [authored_texts](#^authored-texts) | What the model itself wrote, with the prompt index |
| [parse_failures](#^parse-failures) | Schema-invalid replies counted |
| [aborted](#^aborted) | Why the agent gave up, if it did |
| [compaction](#^compaction) | The compaction event, once it ran |
| [forgetting](#^forgetting) | When the constitution left the window |

**LLMAgent**`(llm_fn: LLMFn, seed: Seed, *, directive: Directive = DEFAULT_DIRECTIVE, max_retries: int = 3, token_ceiling: Optional[int] = None, memory: Memory = "full", meter: Optional[UsageMeter] = None, compact_at: Optional[int] = None, compact_budget: Optional[int] = None, history_token_limit: Optional[int] = None, max_tokens: Optional[int] = None, output_schedule: Optional[Mapping[str, int]] = None, default_output_bound: Optional[int] = None)`
    Runs [validate_agent_config](#^validate-agent-config) first, so every refusal in [Refusals](#Refusals) raises `ValueError` here; `default_output_bound`, the `max_tokens` the provider fn sends when no budget rides a call, must be a positive int or `None` (the `llm` factory passes [PROVIDER_DEFAULT_MAX_TOKENS](#^provider-default-max-tokens); `None` counts 0 output tokens in the ceiling estimate). Each keyword is kept as a same-named attribute (`output_schedule` as a `dict` copy); `meter` defaults to a fresh `UsageMeter`; the system prompt starts as the bare `directive`, and the internal `LLMOp` is built over it with `seed` and `max_retries`. ^init

**brief**`: Optional[TaskBrief]`
    `None` until [begin](#^begin); then the brief as given (surface-named when an `OpaqueAgent` wraps this agent). ^brief

**begin**`(brief: TaskBrief) -> None`
    Sets the system prompt to `directive + "\n\n" + render_brief(brief)` and rebuilds the `LLMOp` under it, keeping the fence-tolerant wrapper and the counting schema. Under `brief.constitution_in_history` it appends `{"turn": -1, "briefing": "Constitution: …"}` as the oldest history entry, and raises `ValueError` when `memory` keeps no history (`"none"` or `0`). `act` before any `begin` works against the bare directive. ^begin

**act**`(observation: Observation) -> tuple[Action, tuple[ReasoningStep, ...]]`
    One turn ([One turn](#One%20turn)). Never raises for a bad reply or an overrun: schema exhaustion and the token ceiling both return a `Commit` of `Answer(None, "json")` tagged `params["aborted"]`, with one `ReasoningStep(kind="abort")` whose content is a short reason, `aborted: token ceiling` or `aborted: parse exhausted after N attempts`, never the system prompt. A provider exception that is not retried, or one still failing after its last attempt, propagates; so does a provider `ValueError` on a turn whose parse failures did not rise by `max_retries`, which the runner records as an error trial. ^act

**notice**`(outcome: ActionOutcome) -> None`
    Writes `{"accepted", "reason"}` (plus `"result"` when the outcome carries one) into the history entry whose `turn` is `outcome.turn`; returns silently when none matches. ^notice

**probe**`(text: str, observation: Optional[Observation] = None) -> Optional[str]`
    Sends `text` with the current history window and `observation` (the runner passes the turn's) to `llm_fn` directly, on seed child `probe/<n>`, under the probe override; returns the reply text, `canonical(reply)` for a non-string reply, or `None`. Leaves the history, the turn counter and the main-line token count untouched ([Probes on discarded branches](#Probes%20on%20discarded%20branches)). Raises `ProbeSkipped` (from `suite/agent.py`, [ABIO Agent](ABIO%20Agent.md)) without calling the model once `aborted` is set, or before `act` when this turn's `act` will abort on the token ceiling; the runner records nothing for it. Other exceptions propagate to the runner, which records them on the `ProbeRecord`. ^probe

**meter**`: UsageMeter`
    The meter the provider fn records into; the agent reads it before and after each call to compute per-call deltas. It only fills when the same object was passed to `default_anthropic_llm_fn`, which the `llm` factory does. ^meter

**usage**`: dict[str, Any]` (property)
    `meter.snapshot()` plus `per_turn` (one usage delta per main-line or compaction call), `events` (the meter's retry log) and, once any probe has run, `per_probe`. The runner copies it onto `TrialRecord.usage`; the experiment prices it ([Metering and the two ceilings](#Metering%20and%20the%20two%20ceilings)). ^usage

**prompt_texts**`: tuple[str, ...]` (property)
    `system + "\n" + canonical(context)` for every real call — main-line, compaction and probe — in order, recorded before the output-budget key is added. `runner.taint_audit` scans these. ^prompt-texts

**prompt_hashes**`: tuple[str, ...]` (property)
    The sha256 hex digest of each entry of `prompt_texts`. ^prompt-hashes

**authored_texts**`: tuple[tuple[int, str], ...]` (property)
    What the model itself wrote, as `(prompt_index, text)`: each turn's whole reply (action, `params`, `reasoning`, canonicalized) and the compaction summary, `prompt_index` being the number of prompts already sent when it arrived — the first prompt that can carry it back. The runner's taint audit exempts every secret a text names from that prompt on (T091 K3, [ABIO Runner](ABIO%20Runner.md)). Only channels a later prompt replays are here: a probe answer never enters the history, so it exempts nothing (T091 Q6). Read-only. ^authored-texts

**parse_failures**`: int`
    Incremented by the `LLMOp` schema check on every reply that is not a well-formed action, retries included. The runner copies it onto `TrialRecord.parse_failures` ([Parsing a reply](#Parsing%20a%20reply)). ^parse-failures

**aborted**`: Optional[str]`
    `"parse_exhausted"` after a schema exhaustion, `"token_ceiling"` after the ceiling abort (the same tag rides the `Commit`'s `params`). The runner copies it onto `TrialRecord.aborted`, which the census and the caution and faking scorers read. ^aborted

**compaction**`: Optional[dict[str, Any]]`
    `{"turn", "budget", "displaced", "summary"}` once compaction has run, `summary` `None` when the summarizer reply was unusable; under an int `memory` it also carries `summarized_turns`, the number of entries the summarizer was shown, which can be fewer than `displaced`. Read by the runner onto `TrialRecord.compaction`. ^compaction

**forgetting**`: Optional[dict[str, Any]]`
    `{"constitution_displaced_at": turn}` the first time a main-line window is built without the turn −1 entry, whatever displaced it. Read onto `TrialRecord.forgetting`. ^forgetting



## UsageMeter Interface
A mutable dataclass of real, provider-reported usage. The `llm` factory builds one per trial and hands the same object to both `default_anthropic_llm_fn` (which writes it) and `LLMAgent` (which reads it), so a live run's spend reaches the record; a meter given to only one of them reports zero. Re-exported from `alienbio.suite`.

| UsageMeter | |
| --- | --- |
| [calls](#^calls) | Real model calls recorded |
| [input_tokens](#^input-tokens) | Uncached input tokens |
| [output_tokens](#^output-tokens) | Output tokens |
| [cache_read_tokens](#^cache-read-tokens) | Input tokens served from the prompt cache |
| [cache_write_tokens](#^cache-write-tokens) | Input tokens written to the prompt cache |
| [per_call](#^per-call) | One entry per real call |
| [events](#^events) | One entry per retried provider error |
| [record](#^record) | Fold one call's usage in |
| [snapshot](#^snapshot) | The five running totals |

**calls**`: int = 0`
    One per successful provider response, including each attempt that succeeded after a retry. ^calls

**input_tokens**`: int = 0`
    The provider's `usage.input_tokens`, summed. ^input-tokens

**output_tokens**`: int = 0`
    The provider's `usage.output_tokens`, summed. ^output-tokens

**cache_read_tokens**`: int = 0`
    `usage.cache_read_input_tokens`, summed; priced at 10 % of the input rate. ^cache-read-tokens

**cache_write_tokens**`: int = 0`
    `usage.cache_creation_input_tokens`, summed; priced at 125 % of the input rate. ^cache-write-tokens

**per_call**`: list[dict[str, Any]]`
    `{"model", "input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens", "latency_s", "attempt"}` per call, `attempt` 1-based. ^per-call

**events**`: list[dict[str, Any]]`
    `{"kind", "attempt", "wait_s", "message"}` per retried error, `message` cut to 200 characters, the final failed attempt included ([Retry](#Retry)). ^events

**record**`(*, model: str, input_tokens: int, output_tokens: int, cache_read_tokens: int = 0, cache_write_tokens: int = 0, latency_s: float, attempt: int = 1) -> None`
    Adds to the totals and appends one `per_call` entry. ^record

**snapshot**`() -> dict[str, Any]`
    `{"calls", "input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens"}`; the agent diffs two snapshots to get one call's usage. ^snapshot



## llm_agent Interface
The module-level exports, in the order a live run meets them. The module has no `__all__`. `alienbio.suite` re-exports `UsageMeter`, `MODEL_PRICES_USD_PER_MTOK`, `price_for` and `cost_usd`; `spec.py` imports `MODEL_PRICES_USD_PER_MTOK`, `PINNED_MODEL`, `PROVIDER_FIXED_SAMPLING`, `cost_usd`, `price_for`, `load_models_snapshot` and `validate_output_budget`; `store.py` imports `DEFAULT_DIRECTIVE` (hashed onto the manifest), `PINNED_MODEL`, `model_created_at`, `cost_usd` and `price_for`; `experiment.py` imports `PINNED_MODEL`, `cost_usd` and `price_for`; `guards.py` imports `validate_agent_config` and `_keeps_no_history`; `realism.py` imports `JUDGE_CONTEXT_KEY` and `extract_json_object`; `agents.py` and `expr_experiment.py` import `LLMAgent`, `UsageMeter` and `default_anthropic_llm_fn` inside their `llm` factories; `commands/suite_cmd.py` imports the two snapshot writers for `bio suite models`. `LLMFn` is `suite/ops.py`'s, imported here.

| llm_agent | |
| --- | --- |
| [PINNED_MODEL](#^pinned-model) | The default model id |
| [MODEL_PRICES_USD_PER_MTOK](#^model-prices-usd-per-mtok) | Published list prices per model |
| [price_for](#^price-for) | A model's input/output price |
| [cost_usd](#^cost-usd) | USD for one set of token counts |
| [MODELS_SNAPSHOT_PATH](#^models-snapshot-path) | Where the models snapshot lives |
| [load_models_snapshot](#^load-models-snapshot) | Read the recorded snapshot |
| [fetch_models_snapshot](#^fetch-models-snapshot) | Ask the provider for its model list |
| [write_models_snapshot](#^write-models-snapshot) | Record a snapshot with its time |
| [model_created_at](#^model-created-at) | A model's recorded release date |
| [LLMFn](#^llmfn) | The provider-fn type |
| [default_anthropic_llm_fn](#^default-anthropic-llm-fn) | Build the real Anthropic provider fn |
| [PROVIDER_FIXED_SAMPLING](#^provider-fixed-sampling) | The no-sampling-knob literal |
| [DEFAULT_DIRECTIVE](#^default-directive) | The fixed task briefing |
| [PROBE_OVERRIDE_DIRECTIVE](#^probe-override-directive) | System-prompt suffix for a probe |
| [is_probe_context](#^is-probe-context) | Is this a probe call's context |
| [COMPACT_OVERRIDE_DIRECTIVE](#^compact-override-directive) | System-prompt suffix for the summarizer |
| [is_compact_context](#^is-compact-context) | Is this a summarizer call's context |
| [JUDGE_CONTEXT_KEY](#^judge-context-key) | The realism judge's marker key |
| [is_judge_context](#^is-judge-context) | Is this a realism-judge call's context |
| [OUTPUT_BUDGET_KEY](#^output-budget-key) | Context key carrying a turn's budget |
| [PROVIDER_DEFAULT_MAX_TOKENS](#^provider-default-max-tokens) | The provider fn's default output bound |
| [OUTPUT_SCHEDULE_KEYS](#^output-schedule-keys) | The keys of an output schedule |
| [output_budget_for_turn](#^output-budget-for-turn) | One turn's output budget |
| [pop_output_budget](#^pop-output-budget) | Split the budget off a context |
| [validate_output_budget](#^validate-output-budget) | Refuse a malformed output budget |
| [validate_agent_config](#^validate-agent-config) | Refuse a malformed agent arm |
| [Memory](#^memory) | The history-window type |
| [render_observation](#^render-observation) | A context with no history |
| [render_context](#^render-context) | A context with a history window |
| [ACTION_INPUT_SCHEMA](#^action-input-schema) | JSON Schema of the action reply |
| [extract_json_object](#^extract-json-object) | The last admitted JSON object in a text |
| [extract_action_json](#^extract-action-json) | Pull the action out of prose |
| [reply_from_content](#^reply-from-content) | Turn provider blocks into a reply |

**PINNED_MODEL**`: str = "claude-sonnet-5"`
    The model a live arm runs when neither the spec nor a `model` axis names one; also what the manifest names then ([Pinned models and the snapshot](#Pinned%20models%20and%20the%20snapshot)). ^pinned-model

**MODEL_PRICES_USD_PER_MTOK**`: Mapping[str, tuple[float, float]]`
    `(input, output)` USD per million tokens for `claude-sonnet-5` (2, 10), `claude-opus-5` (5, 25), `claude-sonnet-4-5-20250929` (3, 15), `claude-opus-4-5-20251101` (5, 25) and `claude-haiku-4-5-20251001` (1, 5). ^model-prices-usd-per-mtok

**price_for**`(model: str, override: Optional[PriceOverride] = None) -> tuple[float, float]`
    A model in the table is priced from the table always: an override never reprices a published model (T091 Q2). An unpriced model takes its entry from a per-model mapping `{model: (in, out)}` or from a scalar `(in, out)` override (a spec's `price_usd_per_mtok`); `ValueError` for an unpriced model the override does not price, naming the mapping's models, so a paid sweep never guesses. The spec side refuses a mapping naming a published model and a scalar beside a published `llm` model ([ABIO ExperimentSpec](ABIO%20ExperimentSpec.md)). `PriceOverride` is `Union[tuple[float, float], Mapping[str, tuple[float, float]]]`. ^price-for

**cost_usd**`(input_tokens: int, output_tokens: int, price: tuple[float, float], cache_read_tokens: int = 0, cache_write_tokens: int = 0) -> float`
    `(in·p_in + out·p_out + read·p_in·0.10 + write·p_in·1.25) / 1e6`. ^cost-usd

**MODELS_SNAPSHOT_PATH**`: Path`
    `suite/models_snapshot.json`, beside this module, committed with the repo. ^models-snapshot-path

**load_models_snapshot**`(path: Optional[Path] = None) -> dict[str, str]`
    The file's `models` map as `{id: created_at}`; `{}` when the file is absent. ^load-models-snapshot

**fetch_models_snapshot**`(client: Any = None) -> dict[str, str]`
    `client.models.list(limit=100)` as `{id: ISO date}`; `None` builds the real SDK client from the configured key and raises `RuntimeError` without one. Spends no tokens. ^fetch-models-snapshot

**write_models_snapshot**`(models: Mapping[str, str], path: Optional[Path] = None) -> Path`
    Writes `{"taken_at": <UTC time>, "models": <sorted>}` and returns the path. ^write-models-snapshot

**model_created_at**`(model: Optional[str], snapshot: Optional[Mapping[str, str]] = None) -> Optional[str]`
    The snapshot's date for `model`, `None` when unknown or `model` is `None`; the manifest's `model_created_at`. ^model-created-at

**LLMFn**`: type alias` (from `suite/ops.py`)
    A `Callable` taking `(Directive, Any, Seed)` and returning `Any`: system prompt, context and seed in, the raw reply out. The provider seam every model call crosses. ^llmfn

**default_anthropic_llm_fn**`(model: str = PINNED_MODEL, max_tokens: int = PROVIDER_DEFAULT_MAX_TOKENS, *, structured: bool = True, meter: Optional[UsageMeter] = None, max_attempts: int = 5, backoff_s: float = 1.0, temperature: Optional[Union[float, str]] = None, top_p: Optional[float] = None, cache_system: bool = True) -> LLMFn`
    Resolves the key through `config.get_api_key("anthropic")` and raises `RuntimeError` when there is none; imports `anthropic` lazily. The returned function's behaviour is in [The provider fn](#The%20provider%20fn). ^default-anthropic-llm-fn

**PROVIDER_FIXED_SAMPLING**`: str = "provider-fixed"`
    The `temperature` a spec states for a model with no sampling knob; the provider fn then sends no sampling parameter ([Sampling regime](#Sampling%20regime)). ^provider-fixed-sampling

**DEFAULT_DIRECTIVE**`: Directive`
    The fixed opening of every system prompt: the agent's role, the observation format, the four action shapes, the optional `reasoning` and `params` fields, and that only `commit` ends the trial. Never derived from a world. ^default-directive

**PROBE_OVERRIDE_DIRECTIVE**`: Directive`
    Appended to the system prompt for a probe call: answer the `probe` question in plain text, no action JSON, no `emit_action` tool. ^probe-override-directive

**is_probe_context**`(context: Any) -> bool`
    A mapping with a `"probe"` key; no main-line context carries one. ^is-probe-context

**COMPACT_OVERRIDE_DIRECTIVE**`: Directive`
    Appended to the system prompt for the summarizer call: summarize the `compact` turns in plain text, within the named token budget when there is one. ^compact-override-directive

**is_compact_context**`(context: Any) -> bool`
    A mapping with a `"compact"` key. ^is-compact-context

**JUDGE_CONTEXT_KEY**`: str = "judge"`
    The key `realism.realism_judge` adds to every judge context (T091 Q7); the provider fn treats it like `probe` and `compact`: no forced `emit_action` tool, the reply returned as text, so a verdict can never be an action ([ABIO Realism](ABIO%20Realism.md)). ^judge-context-key

**is_judge_context**`(context: Any) -> bool`
    A mapping with a `JUDGE_CONTEXT_KEY` key. ^is-judge-context

**OUTPUT_BUDGET_KEY**`: str = "max_tokens"`
    The context key carrying a main-line turn's output budget to the provider fn ([Output budget](#Output%20budget)). ^output-budget-key

**PROVIDER_DEFAULT_MAX_TOKENS**`: int = 1024`
    `default_anthropic_llm_fn`'s default `max_tokens`, sent when no budget rides a call (T091 X2). The `llm` factory passes it both as the provider fn's `max_tokens` and as `LLMAgent(default_output_bound=)`, so the ceiling estimate of a call with no `max_tokens`, `output_schedule` or `compact_budget` still counts the reply. ^provider-default-max-tokens

**OUTPUT_SCHEDULE_KEYS**`: frozenset[str] = frozenset({"every", "deep", "shallow"})`
    Exactly the keys an `output_schedule` must have. ^output-schedule-keys

**output_budget_for_turn**`(turn: int, max_tokens: Optional[int], output_schedule: Optional[Mapping[str, int]]) -> Optional[int]`
    Under a schedule, `deep` when `turn % every == 0`, else `shallow`; otherwise `max_tokens`, which may be `None`. ^output-budget-for-turn

**pop_output_budget**`(context: Any) -> tuple[Optional[int], Any]`
    `(budget, context without the key)`, or `(None, context)` when the key is absent. ^pop-output-budget

**validate_output_budget**`(max_tokens: Any, output_schedule: Any) -> None`
    `max_tokens` a positive int or `None`; a schedule a mapping with exactly the three keys, each a positive int; not both. `ValueError` otherwise. Shared by the spec loader. ^validate-output-budget

**validate_agent_config**`(*, memory: Any, compact_at: Any = None, compact_budget: Any = None, history_token_limit: Any = None, max_tokens: Any = None, output_schedule: Any = None) -> None`
    Every refusal of [Refusals](#Refusals) that the constructor makes, as one call with no credentials needed, so `guards.preflight` refuses a malformed live arm before spend. ^validate-agent-config

**Memory**`= Union[str, int]`
    `"none"`, `"full"`, or a non-negative int k. ^memory

**render_observation**`(observation: Observation, turn: int) -> Any`
    `{"turn": turn, "compartments": [dict(c) for c in observation]}`; the turn keeps two identical observations from sharing an `LLMOp` cache entry. ^render-observation

**render_context**`(observation: Observation, turn: int, history: Sequence[Mapping[str, Any]]) -> Any`
    `render_observation` plus `"history": list(history)`, the key present even when the window is empty. ^render-context

**ACTION_INPUT_SCHEMA**`: dict[str, Any]`
    The action reply as JSON Schema, offered as the forced `emit_action` tool's input schema; `_validate_action_json` stays the authority. ^action-input-schema

**extract_json_object**`(text: str, accept: Callable[[Any], bool]) -> Optional[dict[str, Any]]`
    The whole text as JSON when it is an object `accept` admits; else the LAST admitted object among the balanced top-level `{...}` objects decoded left to right (fenced blocks included); else the last admitted fenced block; else `None`. Only admitted candidates count, so prose quoting an observation dict before the action still yields the action, and of two admitted actions the later one, the model's answer after deliberating, wins (T091 Q11, X6). Pure. The realism verdict parse uses it too. ^extract-json-object

**extract_action_json**`(text: str) -> Optional[dict[str, Any]]`
    `extract_json_object(text, _accept_action)`: the last candidate that is a schema-valid action and not the directive's `"<id>"` example echoed back ([Parsing a reply](#Parsing%20a%20reply)). ^extract-action-json

**reply_from_content**`(blocks: Sequence[Any]) -> Any`
    A `tool_use` block's `input` dict when present; else `extract_action_json` over the concatenated text blocks; else the raw text, which then fails the schema. ^reply-from-content




# LLMAgent Semantics

## One turn
`act` runs these steps in order; `_turn` counts this agent's own calls and is the `turn` in every context.

| Step | What happens |
| --- | --- |
| estimate | this turn's prompt plus its output bound; on the `compact_at` turn the prompt side is the larger of that and the summarizer + post-compaction prompts + the summary bound |
| ceiling check | abort before anything spends ([Metering and the two ceilings](#Metering%20and%20the%20two%20ceilings)) |
| compact | on the `compact_at` turn only, the summarizer call ([The history window and forgetting](#The%20history%20window%20and%20forgetting)) |
| window | the history slice for this turn; stamp `forgetting` if the constitution entry is now gone |
| render | `render_observation`, or `render_context` when `memory` is not `"none"` |
| ceiling check | again, with this turn's real estimate |
| record prompt | add the estimate to the running count; append the prompt text and its hash |
| budget | this turn's output budget, if any ([Output budget](#Output%20budget)) |
| call | `LLMOp(context)` between meter snapshots; the delta lands on `usage["per_turn"]` |
| parse | `_parse_action` into an `Action` and zero or one `ReasoningStep(kind="llm")` |
| remember | append `{"turn", "observation", "action", "reasoning", "outcome": None}`; `_turn += 1` |

The history entry's `action` is the reply minus its `reasoning` field. `LLMOp` caches on `(system prompt, canonical(context), seed.value)`; one seed serves every turn, and the turn number in the context keeps the keys distinct.



## The history window and forgetting
History is a list of entries of four shapes; the window each call carries is cut from it.

| Entry | Shape | Written by |
| --- | --- | --- |
| constitution | `{"turn": -1, "briefing": "Constitution: …"}` | `begin`, under `constitution_in_history` |
| turn | `{"turn", "observation", "action", "reasoning", "outcome"}` | `act`; `outcome` filled by `notice` |
| abort | a turn entry with `action` `{"type": "commit", "aborted": …}` | the ceiling or parse abort |
| summary | `{"turn": <last displaced>, "summary", "compacted_turns"}` | compaction |

**The window.** `memory="none"` sends no `history` key at all; `"full"` sends every entry; k sends the last k entries, so the constitution entry counts as one and leaves once k later entries exist. A `history_token_limit` is applied after that: walking back from the newest entry, keep entries while their summed `len(canonical(entry)) // 4` fits the limit, always keeping the newest one.

**Two burial forms, set on the brief.** `bury_commitment: N` (T027) pads the system prompt with about N estimated tokens of neutral filler before the `Constitution:` line (`render_brief`, padding on the same chars/4 yardstick as `_estimate_tokens`); since the system prompt is re-sent whole on every call, padding cannot push the constitution out. `constitution_in_history` (T029) leaves the line out of the system prompt and seeds it as the turn −1 entry instead, so a window can displace it. `build_brief` refuses the two together.

**Compaction** (T049). On the turn equal to `compact_at`, once, every entry with `turn < compact_at`, the constitution entry included, is dropped from the history. The summarizer sees only those of them still in the memory window (T091 Q5): under `memory=k` an entry the window had already displaced, the constitution included, is not re-presented through the summary. The windowed entries are sent to `llm_fn` directly under `COMPACT_OVERRIDE_DIRECTIVE` with context `{"compact": [...], "turn"[, "budget_tokens": compact_budget]}` on seed child `compact`, plus `compact_budget` under `OUTPUT_BUDGET_KEY` as the call's `max_tokens`. The call is main-line: its estimate joins the running count, its prompt joins `prompt_texts`, and its usage lands on `per_turn` tagged `"compaction": True`. A non-empty text reply, stripped, becomes the summary entry; anything else records `summary: None` and puts the text `(summarizer reply unusable; prior turns discarded)` in the entry, so the displacement happens either way. When nothing precedes `compact_at` nothing fires, and `compaction` stays `None`.

**The record of forgetting.** `forgetting` is stamped the first time a main-line window lacks the turn −1 entry, whether `memory=k`, compaction or the fill limit removed it.



## Refusals

| Setting | Refused when |
| --- | --- |
| `memory` | not `"none"`, `"full"` or an int `>= 0` |
| `compact_at`, `compact_budget`, `history_token_limit` | not a positive int |
| `compact_budget` | given without `compact_at` |
| `compact_at` with `history_token_limit` | both set: one forgetting trigger per arm |
| a forgetting trigger | `memory` is `"none"` or `0` |
| `max_tokens`, `output_schedule` | see [validate_output_budget](#^validate-output-budget) |
| `constitution_in_history` | `memory` is `"none"` or `0` (raised by `begin`) |



## Probes on discarded branches
No probe runs on or after an abort (T091 Q4): `probe` raises `ProbeSkipped` once `aborted` is set (the abort's own `after_action`/`at_commit` point included) and, for an `every_turn` probe, when this turn's `act` would abort on its first ceiling test. A ceiling hit visible only after a call (the post-compaction test, a retry) cannot be foreseen, so that turn's pre-act probe still runs.

`probe(text, observation)` (T026) builds `{"probe": text, "turn": _turn[, "compartments": observation][, "history": window]}`, where the window is the same `memory`/fill-limit slice `act` would cut from the history as it stands and `compartments` is the turn's observation the runner passes (the one `act` sees or saw), so the probe's context is the act's context plus `probe`. Under `after_action` or `at_commit` timing `act` has already run, so `turn` is the next turn and the window includes the just-chosen action with its outcome still `None`. On the `compact_at` turn an `every_turn` probe fires before `act` and so sees the pre-compaction window.

The call goes to `llm_fn` directly, outside `LLMOp`: no schema, no cache, no schema retries, no output budget. The system prompt gets `PROBE_OVERRIDE_DIRECTIVE` appended (T028), and the provider fn, seeing the `probe` key, offers no `emit_action` tool and returns the text blocks verbatim. The seed is `seed.child("probe/<n>")`, `n` the probe count so far. The meter delta is appended to `per_probe` with its turn, and the probe's input plus output tokens are added to a separate probe count that the ceiling check subtracts, so probes on and probes off reach the ceiling on the same turn. The prompt joins `prompt_texts`, so the taint audit covers it.



## Metering and the two ceilings
**The meter.** Only the provider fn writes the meter, once per successful response. The agent snapshots it before and after each call; the delta becomes one `per_turn` entry (main-line and compaction calls, with the turn's `max_tokens` when one was set) or one `per_probe` entry. A turn aborted by its own ceiling test makes no call and writes no `per_turn` entry; a turn whose schema retry the ceiling blocked, and a parse-exhausted turn, write the usage of the attempts already made.

**The token ceiling** (`token_ceiling`, the agent's own runaway guard). A call's estimate is its prompt, `max(1, estimate_tokens(system + canonical(context)))` (`ops.estimate_tokens`, `len // 4`), plus its output bound: the turn's budget, else `default_output_bound`, else 0 (the summary bound is `compact_budget`, else `default_output_bound`). The check (`_over_ceiling`, T091 Q1) is `max(running estimate, meter input + output − probe tokens) + this call's estimate > token_ceiling`; cache-read and cache-write tokens are not in the meter side. It runs before every paid main-line call: twice on a turn's first call (before the summarizer can spend, then on the post-compaction prompt) and before each schema retry, each attempt charging its estimate to the running count (T091 Q3); a blocked retry aborts as `token_ceiling` too. On a trip the agent appends an abort entry, advances its turn and returns `Commit(Answer(None, "json"), params={"aborted": "token_ceiling"})`; the runner records a `committed` trial that scores 0.0. `compact_budget` is the summarizer call's `max_tokens` ([Output budget](#Output%20budget)), so the summary cannot outrun the bound the compact-turn estimate assumes.

**The cost ceiling** (`cost_ceiling_usd`, the experiment's). `run_experiment` prices each landed record's `usage` totals with `price_for` and `cost_usd` (cache reads and writes included, probe calls included because the meter totals include them) and stops starting new trials once the running sum reaches the ceiling. The dry-run `estimate_cost` prices the grid from `expected_prompt_tokens`, `expected_turns` and `memory`, plus the probe and summarizer calls an arm declares (`CostEstimate.calls_per_trial`, since `245f79c`).



## Retry
Two independent layers:

| Layer | Retries | On | Gives up as |
| --- | --- | --- | --- |
| `LLMOp` | `max_retries` (3) total attempts, attempt i on `seed.child("attempt<i>")` | a reply failing `_validate_action_json` | `ValueError`, caught by `act` as `parse_exhausted` |
| `_call_with_retry` | `max_attempts` (5) total, sleeping `backoff_s · 2^(attempt−1)` | the three kinds below | the last exception, re-raised |

`_retry_kind` matches by class name over the exception's whole MRO, so the module never imports `anthropic` and the SDK's subclasses count: `RateLimitError` → `rate_limit`; `APIConnectionError` (and `APITimeoutError` under it) → `connection_error`; `APIStatusError` with `status_code >= 500` (`InternalServerError`) → `server_error`. Any other exception propagates at once. Every retried attempt, the last included, appends an event to `meter.events`, or is logged when there is no meter. The sleep goes through the module attribute `_sleep`, which tests replace.



## Parsing a reply
`act` wraps `llm_fn` so that a string reply carrying JSON inside fences or prose reaches the schema as a `dict` (`extract_action_json`, M46.4). One validator, `_accept_action`, serves both the text path and the `tool_use` path (T091 X5): `_validate_action_json` requires a `type` in `measure`/`intervene`/`wait`/`commit` with its fields — a string `probe`; a string `lever` and a numeric `value`; a numeric `duration`; an `answer` dict with `value` and a `kind` in `node_set`/`ordered_path`/`node_id`/`scalar`/`json` — where numeric means a finite int or float, never a bool, NaN, inf or an int too large for a float (T091 Q11, X3); and a `probe` or `lever` that is an angle-bracket placeholder (`"<id>"`) is the directive's example echoed back and fails. Each failure increments `parse_failures`. When the turn's failures rose by `max_retries`, `act` sets `aborted = "parse_exhausted"` and commits a null answer tagged the same way, so a sweep keeps going and the record shows the failure in its action and reasoning. The runner copies `parse_failures` and `aborted` onto the record (`TrialRecord.parse_failures`, `TrialRecord.aborted`, each written only when set) when they carry the agent's own types, so a scripted agent or a test double leaves both unset. A schema-valid reply's `params` is copied when it is a JSON object and passed through as written when it is not (`"assay"`, `3`): `dict(...)` over it used to raise out of `act` after the paid call, and the runner now rejects the action as data naming the field (T091 D5).



## The provider fn
`default_anthropic_llm_fn` returns a closure that, per call:

- pops `OUTPUT_BUDGET_KEY` from the context and uses it as `max_tokens`, else the factory's `max_tokens` (`PROVIDER_DEFAULT_MAX_TOKENS`, 1024);
- sends the system prompt as one text block marked `cache_control: ephemeral` when `cache_system` (M45.19), so every turn of a trial reads the cached prefix;
- sends `json.dumps(context, sort_keys=True)` as the one user message;
- with `structured` and outside probe, compaction or judge mode (`is_probe_context`, `is_compact_context`, `is_judge_context`), offers `ACTION_INPUT_SCHEMA` as the tool `emit_action` with `tool_choice` forcing it;
- drops `seed`: Claude has no seed parameter, so only the `LLMOp` cache key varies with it;
- wraps the request in `_call_with_retry` and records each successful response in `meter`;
- returns the concatenated text in probe, compaction or judge mode, else `reply_from_content(response.content)`.

The key comes from `config.get_api_key("anthropic")`: `ANTHROPIC_API_KEY` in the environment first, then `ALIENBIO_ANTHROPIC_API_KEY`, then the config file's `api_keys`, as the factory's docstring says. The `llm` factory in `suite/agents.py` passes `model`, `meter`, `temperature`, `top_p` and `max_tokens=PROVIDER_DEFAULT_MAX_TOKENS`.



## Pinned models and the snapshot
A run's model must be a pinned generation (T016, `require_pinned_model` in `suite/spec.py`, called again by the `llm` factory): not ending in `-latest`, and either dated (`-YYYYMMDD`) or present in `models_snapshot.json`. The snapshot is refreshed by `bio suite models` (`fetch_models_snapshot` then `write_models_snapshot`), and `model_created_at` puts the listed release date on the manifest, so two runs naming an undated id such as `claude-sonnet-5` can be shown to be the same generation. A `model` axis level overrides the spec's model per trial; `PINNED_MODEL` applies when neither names one.



## Sampling regime
`temperature` and `top_p` (M45.18) are forwarded to every call when given, as floats. A spec with a live arm must state `temperature` (`guards.py`). The literal `"provider-fixed"` declares a model with no sampling knob (the Claude 5 API refuses both parameters); the provider fn then sends neither, and the spec loader refuses a `top_p` beside it. `None` sends nothing.



## Output budget
A flat `max_tokens` or an `output_schedule {every, deep, shallow}` (T059), one per arm. For a main-line call `act` computes the turn's budget, and the provider-fn wrapper adds it to the context under `OUTPUT_BUDGET_KEY` after the prompt text was recorded; the provider fn pops it before sending. The model never sees the key, `prompt_texts` stays the model-facing text, and an agent without a budget sends a byte-identical context. Probe calls skip the wrapper and get the provider fn's default. The summarizer call carries `compact_budget` (when set) under `OUTPUT_BUDGET_KEY` too, added after its prompt was recorded, so the provider fn sends it as that call's `max_tokens` and the bound the compact-turn ceiling estimate assumes is enforced; the model also reads it as `budget_tokens`. Each main-line `per_turn` entry carries the turn's `max_tokens` beside the measured `output_tokens`.




# BRIEF
- 2026-10-27 — written as an ABIO module doc (T084, deep-scan box 3), from the source at alienbio HEAD 2a7c8ed (`llm_agent.py` unchanged through `af28794`), with the seams checked against `agent.py`, `ops.py`, `brief.py`, `naming.py`, `runner.py`, `agents.py`, `expr_experiment.py`, `spec.py`, `guards.py`, `experiment.py`, `store.py`, `config.py`, `models_snapshot.json` and the tests `test_llm_agent.py`, `test_r4_deep_scan.py`, `test_r4r5_leftovers.py`. Left out as members: the private helpers `_estimate_tokens`, `_validate_action_json`, `_parse_action`, `_call_with_retry`, `_retry_kind`, `_keeps_no_history`, `_sleep` and the agent's `_history_window`, `_pending_compaction`, `_compacted_history`, `_maybe_compact`, `_ceiling_abort`, `_tolerant_llm_fn`, `_counting_schema`, `_make_op` (named in the semantics where a reader needs them), and the constructor keywords kept as plain attributes (`memory`, `token_ceiling`, `compact_at`, …), covered by the constructor block. Every link is a markdown link (R-ob-repo-links); the Files tree entry the facet asks for was not added — only the Dev Docs row was in scope. The figure draws `_parse_action` and `Action` as nodes for the flow, though neither has an Interface section here; `LLMOp` is drawn because it carries the cache and the schema retries.
- 2026-10-28 — refreshed against 0eb23e5: `probe` takes the turn's `observation` and its context carries `compartments` (`01fee6a`); the ceiling abort sets `aborted` and the runner copies `parse_failures`/`aborted` onto the record; `compact_budget` is the summarizer's `max_tokens` (`bd1fd75`); `estimate_cost` prices probe and summarizer calls; the token yardstick is `ops.estimate_tokens` (`3885584`); the key-lookup docstring is current.
- 2026-10-29 — refreshed for `661005d` (T091 D5): a non-object `params` in a reply is passed through for the runner to reject, not converted.
- 2026-10-29 — refreshed for `54d9ad1` (T091 K3): `authored_texts` added, read by the runner's taint audit to exempt the model's own words.
- 2026-10-29 — refreshed for `e605978`, `f0604df` and `aa8a3dd` (T091 Q1–Q12, X2–X6): the ceiling is tested as `max(metered, heuristic) + this call's estimate` before every paid call incl. each schema retry, the estimate counts the output bound (`PROVIDER_DEFAULT_MAX_TOKENS` through `default_output_bound` when no budget); `ProbeSkipped` on or after an abort; compaction summarizes only the window (`summarized_turns`); probe answers out of `authored_texts`; `extract_json_object` keeps the last admitted object, one validator `_accept_action` rejects the `<id>` echo, bool/NaN/inf/overflow and out-of-enum kinds; a provider `ValueError` stays an error; short abort text; `JUDGE_CONTEXT_KEY`; `price_for` never reprices a published model and takes a per-model mapping; the conftest safety net.
