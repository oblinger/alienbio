---
description: "`llm_agent`: the live-model agent — `LLMAgent` (history window, forgetting triggers, discarded-branch probes, token ceiling), `UsageMeter`, the Anthropic provider fn, prices, pinned models and the models snapshot, the per-turn output budget. Source: `src/alienbio/suite/llm_agent.py`."
---
:>>
# ABIO LLMAgent
The real-model agent: `LLMAgent` turns each narrowed observation into one model call over the `LLMOp` seam, parses the reply into an `Action`, keeps its own turn history, and meters every token the provider reports.

![ABIO LLMAgent](ABIO%20LLMAgent.svg) 
*The history window and forgetting* is the topic that governs the turn-history rows (the constitution entry, the compaction summary); *Probes on discarded branches* governs the probe fork; *Metering and the two ceilings* governs `UsageMeter`.

`suite/llm_agent.py` holds the one agent that spends money, plus everything it needs to do so reproducibly: the `UsageMeter` it shares with its provider fn, `default_anthropic_llm_fn` (the live provider fn; with `fetch_models_snapshot`, the module's only network calls), the price table and `cost_usd`, the pinned-model id and the recorded `models.list` snapshot, the per-turn output budget, and the reply parsers. No framework test calls a live model: every `LLMAgent` in `tests/` takes a mock `llm_fn`, except one end-to-end test skipped unless `ABIO_LLM_E2E=1` and a key are set. The turn loop that calls `begin`, `act`, `notice` and `probe` is [ABIO Runner](ABIO%20Runner.md); the brief rendered into the system prompt is [ABIO TaskBrief](ABIO%20TaskBrief.md); the surface-name wrapper `OpaqueAgent` that sits between the runner and this agent is [ABIO NameMap](ABIO%20NameMap.md). The `Agent`, `SessionAgent` and `ProbeAgent` protocols and the action types are in `suite/agent.py`; `LLMOp` and `canonical` in `suite/ops.py`; the `llm` agent factory in `suite/agents.py`; the dry-run price in `suite/spec.py` (`estimate_cost`). The subsystem view is [ABIO-Runtime](../../ABIO%20Architecture/ABIO-Runtime.md); the operator's view is [ABIO Suite Runtime](../../ABIO%20Architecture/ABIO%20Suite%20Runtime.md).



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
| [parse_failures](#^parse-failures) | Schema-invalid replies counted |
| [aborted](#^aborted) | Why the agent gave up, if it did |
| [compaction](#^compaction) | The compaction event, once it ran |
| [forgetting](#^forgetting) | When the constitution left the window |

**LLMAgent**`(llm_fn: LLMFn, seed: Seed, *, directive: Directive = DEFAULT_DIRECTIVE, max_retries: int = 3, token_ceiling: Optional[int] = None, memory: Memory = "full", meter: Optional[UsageMeter] = None, compact_at: Optional[int] = None, compact_budget: Optional[int] = None, history_token_limit: Optional[int] = None, max_tokens: Optional[int] = None, output_schedule: Optional[Mapping[str, int]] = None)`
    Runs [validate_agent_config](#^validate-agent-config) first, so every refusal in [Refusals](#Refusals) raises `ValueError` here. Each keyword is kept as a same-named attribute (`output_schedule` as a `dict` copy); `meter` defaults to a fresh `UsageMeter`; the system prompt starts as the bare `directive`, and the internal `LLMOp` is built over it with `seed` and `max_retries`. ^init

**brief**`: Optional[TaskBrief]`
    `None` until [begin](#^begin); then the brief as given (surface-named when an `OpaqueAgent` wraps this agent). ^brief

**begin**`(brief: TaskBrief) -> None`
    Sets the system prompt to `directive + "\n\n" + render_brief(brief)` and rebuilds the `LLMOp` under it, keeping the fence-tolerant wrapper and the counting schema. Under `brief.constitution_in_history` it appends `{"turn": -1, "briefing": "Constitution: …"}` as the oldest history entry, and raises `ValueError` when `memory` keeps no history (`"none"` or `0`). `act` before any `begin` works against the bare directive. ^begin

**act**`(observation: Observation) -> tuple[Action, tuple[ReasoningStep, ...]]`
    One turn ([One turn](#One%20turn)). Never raises for a bad reply or an overrun: schema exhaustion and the token ceiling both return a `Commit` of `Answer(None, "json")` tagged `params["aborted"]`, with one `ReasoningStep(kind="abort")`. A provider exception that is not retried, or one still failing after its last attempt, propagates. ^act

**notice**`(outcome: ActionOutcome) -> None`
    Writes `{"accepted", "reason"}` (plus `"result"` when the outcome carries one) into the history entry whose `turn` is `outcome.turn`; returns silently when none matches. ^notice

**probe**`(text: str) -> Optional[str]`
    Sends `text` with the current history window to `llm_fn` directly, on seed child `probe/<n>`, under the probe override; returns the reply text, `canonical(reply)` for a non-string reply, or `None`. Leaves the history, the turn counter and the main-line token count untouched ([Probes on discarded branches](#Probes%20on%20discarded%20branches)). Exceptions propagate to the runner, which records them on the `ProbeRecord`. ^probe

**meter**`: UsageMeter`
    The meter the provider fn records into; the agent reads it before and after each call to compute per-call deltas. It only fills when the same object was passed to `default_anthropic_llm_fn`, which the `llm` factory does. ^meter

**usage**`: dict[str, Any]` (property)
    `meter.snapshot()` plus `per_turn` (one usage delta per main-line or compaction call), `events` (the meter's retry log) and, once any probe has run, `per_probe`. The runner copies it onto `TrialRecord.usage`; the experiment prices it ([Metering and the two ceilings](#Metering%20and%20the%20two%20ceilings)). ^usage

**prompt_texts**`: tuple[str, ...]` (property)
    `system + "\n" + canonical(context)` for every real call — main-line, compaction and probe — in order, recorded before the output-budget key is added. `audit_prompts` scans these. ^prompt-texts

**prompt_hashes**`: tuple[str, ...]` (property)
    The sha256 hex digest of each entry of `prompt_texts`. ^prompt-hashes

**parse_failures**`: int`
    Incremented by the `LLMOp` schema check on every reply that is not a well-formed action, retries included. Not copied onto the record ([Parsing a reply](#Parsing%20a%20reply)). ^parse-failures

**aborted**`: Optional[str]`
    `"parse_exhausted"` after a schema exhaustion; the token-ceiling abort does not set it (the tag lives on the `Commit`'s `params`). ^aborted

**compaction**`: Optional[dict[str, Any]]`
    `{"turn", "budget", "displaced", "summary"}` once compaction has run, `summary` `None` when the summarizer reply was unusable. Read by the runner onto `TrialRecord.compaction`. ^compaction

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
The module-level exports, in the order a live run meets them. The module has no `__all__`. `alienbio.suite` re-exports `UsageMeter`, `MODEL_PRICES_USD_PER_MTOK`, `price_for` and `cost_usd`; `spec.py` imports `PINNED_MODEL`, `PROVIDER_FIXED_SAMPLING`, `cost_usd`, `price_for`, `load_models_snapshot` and `validate_output_budget`; `experiment.py` and `store.py` import `DEFAULT_DIRECTIVE` (hashed onto the manifest), `PINNED_MODEL` and `model_created_at`; `guards.py` imports `validate_agent_config`; `agents.py` and `expr_experiment.py` import `LLMAgent`, `UsageMeter` and `default_anthropic_llm_fn` inside their `llm` factories; `commands/suite_cmd.py` imports the two snapshot writers for `bio suite models`. `LLMFn` is `suite/ops.py`'s, imported here.

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
| [OUTPUT_BUDGET_KEY](#^output-budget-key) | Context key carrying a turn's budget |
| [OUTPUT_SCHEDULE_KEYS](#^output-schedule-keys) | The keys of an output schedule |
| [output_budget_for_turn](#^output-budget-for-turn) | One turn's output budget |
| [pop_output_budget](#^pop-output-budget) | Split the budget off a context |
| [validate_output_budget](#^validate-output-budget) | Refuse a malformed output budget |
| [validate_agent_config](#^validate-agent-config) | Refuse a malformed agent arm |
| [Memory](#^memory) | The history-window type |
| [render_observation](#^render-observation) | A context with no history |
| [render_context](#^render-context) | A context with a history window |
| [ACTION_INPUT_SCHEMA](#^action-input-schema) | JSON Schema of the action reply |
| [extract_action_json](#^extract-action-json) | Pull a JSON object out of prose |
| [reply_from_content](#^reply-from-content) | Turn provider blocks into a reply |

**PINNED_MODEL**`: str = "claude-sonnet-5"`
    The model a live arm runs when neither the spec nor a `model` axis names one; also what the manifest names then ([Pinned models and the snapshot](#Pinned%20models%20and%20the%20snapshot)). ^pinned-model

**MODEL_PRICES_USD_PER_MTOK**`: Mapping[str, tuple[float, float]]`
    `(input, output)` USD per million tokens for `claude-sonnet-5` (2, 10), `claude-opus-5` (5, 25), `claude-sonnet-4-5-20250929` (3, 15), `claude-opus-4-5-20251101` (5, 25) and `claude-haiku-4-5-20251001` (1, 5). ^model-prices-usd-per-mtok

**price_for**`(model: str, override: Optional[tuple[float, float]] = None) -> tuple[float, float]`
    `override` when given (a spec's `price_usd_per_mtok`), else the table entry; `ValueError` for an unlisted model with no override, so a paid sweep never guesses. ^price-for

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

**default_anthropic_llm_fn**`(model: str = PINNED_MODEL, max_tokens: int = 1024, *, structured: bool = True, meter: Optional[UsageMeter] = None, max_attempts: int = 5, backoff_s: float = 1.0, temperature: Optional[Union[float, str]] = None, top_p: Optional[float] = None, cache_system: bool = True) -> LLMFn`
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

**OUTPUT_BUDGET_KEY**`: str = "max_tokens"`
    The context key carrying a main-line turn's output budget to the provider fn ([Output budget](#Output%20budget)). ^output-budget-key

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

**extract_action_json**`(text: str) -> Optional[dict[str, Any]]`
    The first `dict` found trying the whole text as JSON, then each fenced block, then each `{` with `raw_decode`; `None` when there is none. ^extract-action-json

**reply_from_content**`(blocks: Sequence[Any]) -> Any`
    A `tool_use` block's `input` dict when present; else `extract_action_json` over the concatenated text blocks; else the raw text, which then fails the schema. ^reply-from-content




# LLMAgent Semantics

## One turn
`act` runs these steps in order; `_turn` counts this agent's own calls and is the `turn` in every context.

| Step | What happens |
| --- | --- |
| estimate | the prompt as it stands now (system prompt plus the current window); on the `compact_at` turn, the larger of that and summarizer prompt + post-compaction prompt + `compact_budget` |
| ceiling check | abort before anything spends ([Metering and the two ceilings](#Metering%20and%20the%20two%20ceilings)) |
| compact | on the `compact_at` turn only, the summarizer call ([The history window and forgetting](#The%20history%20window%20and%20forgetting)) |
| window | the history slice for this turn; stamp `forgetting` if the constitution entry is now gone |
| render | `render_observation`, or `render_context` when `memory` is not `"none"` |
| ceiling check | again, with this turn's real estimate |
| record prompt | add the estimate to the running count; append the prompt text and its hash |
| budget | this turn's output budget, if any ([Output budget](#Output%20budget)) |
| call | `LLMOp(context)`, bracketed by meter snapshots; the delta lands on `usage["per_turn"]` |
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

**Compaction** (T049). On the turn equal to `compact_at`, once, every entry with `turn < compact_at`, the constitution entry included, is sent to `llm_fn` directly under `COMPACT_OVERRIDE_DIRECTIVE` with context `{"compact": [...], "turn"[, "budget_tokens": compact_budget]}` on seed child `compact`. The call is main-line: its estimate joins the running count, its prompt joins `prompt_texts`, and its usage lands on `per_turn` tagged `"compaction": True`. A non-empty text reply, stripped, becomes the summary entry; anything else records `summary: None` and puts the text `(summarizer reply unusable; prior turns discarded)` in the entry, so the displacement happens either way. When nothing precedes `compact_at` nothing fires, and `compaction` stays `None`.

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
`probe(text)` (T026) builds `{"probe": text, "turn": _turn[, "history": window]}`, where the window is the same `memory`/fill-limit slice `act` would cut from the history as it stands. It carries no `compartments`: the probe sees the history and the system prompt, not the observation of the turn in progress. Under `after_action` timing `act` has already run, so `turn` is the next turn and the window includes the just-chosen action with its outcome still `None`. On the `compact_at` turn an `every_turn` probe fires before `act` and so sees the pre-compaction window.

The call goes to `llm_fn` directly, outside `LLMOp`: no schema, no cache, no schema retries, no output budget. The system prompt gets `PROBE_OVERRIDE_DIRECTIVE` appended (T028), and the provider fn, seeing the `probe` key, offers no `emit_action` tool and returns the text blocks verbatim. The seed is `seed.child("probe/<n>")`, `n` the probe count so far. The meter delta is appended to `per_probe` with its turn, and the probe's input plus output tokens are added to a separate probe count that the ceiling check subtracts, so probes on and probes off reach the ceiling on the same turn. The prompt joins `prompt_texts`, so the taint audit covers it.



## Metering and the two ceilings
**The meter.** Only the provider fn writes the meter, once per successful response. The agent snapshots it before and after each call; the delta becomes one `per_turn` entry (main-line and compaction calls, with the turn's `max_tokens` when one was set) or one `per_probe` entry. A ceiling-abort turn makes no call and writes no `per_turn` entry; a parse-exhausted turn writes the usage of its failed attempts.

**The token ceiling** (`token_ceiling`, the agent's own runaway guard). The running estimate adds `max(1, len(system + canonical(context)) // 4)` once per main-line call and once per summarizer call, whatever the number of schema retries. The check is `max(estimate so far + this turn's estimate, meter input + output − probe tokens) > token_ceiling`; cache-read and cache-write tokens are not in the meter side. It runs twice per turn, the first time before the summarizer can spend. On a trip the agent appends an abort entry, advances its turn and returns `Commit(Answer(None, "json"), params={"aborted": "token_ceiling"})`; the runner records a `committed` trial that scores 0.0. Nothing caps the summary's length at the call ([Output budget](#Output%20budget)), so a long summary can still push the second check over.

**The cost ceiling** (`cost_ceiling_usd`, the experiment's). `run_experiment` prices each landed record's `usage` totals with `price_for` and `cost_usd` (cache reads and writes included, probe calls included because the meter totals include them) and stops starting new trials once the running sum reaches the ceiling. The dry-run `estimate_cost` prices the grid from `expected_prompt_tokens`, `expected_turns` and `memory` alone; it does not model probe or summarizer calls.



## Retry
Two independent layers:

| Layer | Retries | On | Gives up as |
| --- | --- | --- | --- |
| `LLMOp` | `max_retries` (3) total attempts, attempt i on `seed.child("attempt<i>")` | a reply failing `_validate_action_json` | `ValueError`, caught by `act` as `parse_exhausted` |
| `_call_with_retry` | `max_attempts` (5) total, sleeping `backoff_s · 2^(attempt−1)` | the three kinds below | the last exception, re-raised |

`_retry_kind` matches by class name over the exception's whole MRO, so the module never imports `anthropic` and the SDK's subclasses count: `RateLimitError` → `rate_limit`; `APIConnectionError` (and `APITimeoutError` under it) → `connection_error`; `APIStatusError` with `status_code >= 500` (`InternalServerError`) → `server_error`. Any other exception propagates at once. Every retried attempt, the last included, appends an event to `meter.events`, or is logged when there is no meter. The sleep goes through the module attribute `_sleep`, which tests replace.



## Parsing a reply
`act` wraps `llm_fn` so that a string reply carrying JSON inside fences or prose reaches the schema as a `dict` (`extract_action_json`, M46.4). The schema check `_validate_action_json` requires a `type` in `measure`/`intervene`/`wait`/`commit` with its fields: a string `probe`; a string `lever` and numeric `value`; a numeric `duration`; an `answer` dict with `value` and a string `kind`. Each failure increments `parse_failures`. After `max_retries` failures `act` sets `aborted = "parse_exhausted"` and commits a null answer tagged the same way, so a sweep keeps going and the record shows the failure in its action and reasoning. `parse_failures` itself is read by nothing in the runner and does not reach the record.



## The provider fn
`default_anthropic_llm_fn` returns a closure that, per call:

- pops `OUTPUT_BUDGET_KEY` from the context and uses it as `max_tokens`, else the factory's `max_tokens` (1024);
- sends the system prompt as one text block marked `cache_control: ephemeral` when `cache_system` (M45.19), so every turn of a trial reads the cached prefix;
- sends `json.dumps(context, sort_keys=True)` as the one user message;
- with `structured` and outside probe or compaction mode, offers `ACTION_INPUT_SCHEMA` as the tool `emit_action` with `tool_choice` forcing it;
- drops `seed`: Claude has no seed parameter, so only the `LLMOp` cache key varies with it;
- wraps the request in `_call_with_retry` and records each successful response in `meter`;
- returns the concatenated text in probe or compaction mode, else `reply_from_content(response.content)`.

The key comes from `config.get_api_key("anthropic")`: `ANTHROPIC_API_KEY` in the environment first, then `ALIENBIO_ANTHROPIC_API_KEY`, then the config file's `api_keys` (the factory's docstring says environment only). The `llm` factory in `suite/agents.py` passes `model`, `meter`, `temperature` and `top_p`, and never `max_tokens`.



## Pinned models and the snapshot
A run's model must be a pinned generation (T016, `_require_pinned_model` in `suite/spec.py`, called again by the `llm` factory): not ending in `-latest`, and either dated (`-YYYYMMDD`) or present in `models_snapshot.json`. The snapshot is refreshed by `bio suite models` (`fetch_models_snapshot` then `write_models_snapshot`), and `model_created_at` puts the listed release date on the manifest, so two runs naming an undated id such as `claude-sonnet-5` can be shown to be the same generation. A `model` axis level overrides the spec's model per trial; `PINNED_MODEL` applies when neither names one.



## Sampling regime
`temperature` and `top_p` (M45.18) are forwarded to every call when given, as floats. A spec with a live arm must state `temperature` (`guards.py`). The literal `"provider-fixed"` declares a model with no sampling knob (the Claude 5 API refuses both parameters); the provider fn then sends neither, and the spec loader refuses a `top_p` beside it. `None` sends nothing.



## Output budget
A flat `max_tokens` or an `output_schedule {every, deep, shallow}` (T059), one per arm. For a main-line call `act` computes the turn's budget, and the provider-fn wrapper adds it to the context under `OUTPUT_BUDGET_KEY` after the prompt text was recorded; the provider fn pops it before sending. The model never sees the key, `prompt_texts` stays the model-facing text, and an agent without a budget sends a byte-identical context. Probe and summarizer calls skip the wrapper and get the provider fn's default; `compact_budget` reaches the summarizer only as the `budget_tokens` value in its context. Each main-line `per_turn` entry carries the turn's `max_tokens` beside the measured `output_tokens`.




# BRIEF
- 2026-10-27 — written as an ABIO module doc (T084, deep-scan box 3), from the source at alienbio HEAD 2a7c8ed (`llm_agent.py` unchanged through `af28794`), with the seams checked against `agent.py`, `ops.py`, `brief.py`, `naming.py`, `runner.py`, `agents.py`, `expr_experiment.py`, `spec.py`, `guards.py`, `experiment.py`, `store.py`, `config.py`, `models_snapshot.json` and the tests `test_llm_agent.py`, `test_r4_deep_scan.py`, `test_r4r5_leftovers.py`. Left out as members: the private helpers `_estimate_tokens`, `_validate_action_json`, `_parse_action`, `_call_with_retry`, `_retry_kind`, `_keeps_no_history`, `_sleep` and the agent's `_history_window`, `_pending_compaction`, `_compacted_history`, `_maybe_compact`, `_ceiling_abort`, `_tolerant_llm_fn`, `_counting_schema`, `_make_op` (named in the semantics where a reader needs them), and the constructor keywords kept as plain attributes (`memory`, `token_ceiling`, `compact_at`, …), covered by the constructor block. Every link is a markdown link (R-ob-repo-links); the Files tree entry the facet asks for was not added — only the Dev Docs row was in scope. The figure draws `_parse_action` and `Action` as nodes for the flow, though neither has an Interface section here; `LLMOp` is drawn because it carries the cache and the schema retries.
