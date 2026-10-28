---
description: "`ops`: the FT07 scripted/LLM seam — `LLMOp` calls an injected `LLMFn`, schema-validates the output, retries invalid replies on child seeds and caches by `(directive, canonical(context), seed)`; `canonical` is the stable JSON key, `estimate_tokens` the suite's `len // 4` yardstick. Source: `src/alienbio/suite/ops.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO suite](ABIO%20suite.md) → [ABIO LLMOp](ha://p/ABIO%20LLMOp) 
# ABIO LLMOp
The seam through which every model decision passes: one callable that never makes a call itself, validates what the injected model function returns, and caches the answer.

![ABIO LLMOp](ABIO%20LLMOp.svg) 
*The cache* is the topic behind the dotted hit path (a repeat of the same directive, context and seed returns the stored object without a call; ‡ the stored object is shared).

`suite/ops.py` is domain-neutral: directives, contexts and outputs are opaque. `LLMOp` and `types.ScriptedOp` both satisfy the `types.Op` protocol (`result = op(context)`). The live consumer is [ABIO LLMAgent](ABIO%20LLMAgent.md), which builds one `LLMOp` per agent with its system prompt as the directive, a counting schema and a tolerant wrapper around the provider function; the provider functions (`default_anthropic_llm_fn`) and the usage meter are LLMAgent's. `canonical` also renders the prompt text the taint audit scans, and `estimate_tokens` sizes LLMAgent's token ceiling and history window and `brief.py`'s `bury_commitment` filler ([ABIO TaskBrief](ABIO%20TaskBrief.md)). `LLMOp` is re-exported from `alienbio.suite`. The subsystem view is [ABIO-Runtime](../../ABIO%20Architecture/ABIO-Runtime.md).



## LLMOp Interface
A mutable generic dataclass (the cache is state). Equality ignores the cache.

| LLMOp | |
| --- | --- |
| [directive](#^directive) | The fixed instruction, part of the cache key |
| [out_schema](#^out-schema) | Validity predicate on a reply |
| [llm_fn](#^llm-fn) | The injected model function |
| [seed](#^seed) | Base seed of attempt 0 |
| [max_retries](#^max-retries) | Total attempts before refusing |
| [__call__](#^call) | Cached, validated, retried call |

**directive**`: Directive`
    A string (`types.Directive = str`). ^directive

**out_schema**`: Validator`
    `Callable[[Any], bool]`; a reply is returned only when it holds. ^out-schema

**llm_fn**`: LLMFn`
    `Callable[[Directive, Any, Seed], Any]`. Always injected: tests pass a mock, LLMAgent passes the provider. ^llm-fn

**seed**`: Seed = Seed(0)`
    Attempt 0's seed and the cache key's seed. ^seed

**max_retries**`: int = 3`
    Total attempts, not retries after the first. `0` raises at once without a call. ^max-retries

**__call__**`(context: Any) -> T`
    On a cache hit for `(directive, canonical(context), seed.value)`, returns the stored object. Otherwise calls `llm_fn` with `seed` on attempt 0 and `seed.child(f"attempt{i}")` on attempt `i`, caches and returns the first reply `out_schema` accepts, and raises `ValueError` naming the directive after `max_retries` invalid replies. An exception from `llm_fn` propagates on the first raise; only invalid output is retried. ^call



## ops Interface
Two type aliases and two functions.

| ops | |
| --- | --- |
| [Validator](#^validator) | The schema predicate type |
| [LLMFn](#^llmfn) | The model function type |
| [canonical](#^canonical) | Stable string key of a context |
| [estimate_tokens](#^estimate-tokens) | Characters over four |

**Validator**` = Callable[[Any], bool]`
    What `out_schema` is. ^validator

**LLMFn**` = Callable[[Directive, Any, Seed], Any]`
    What `llm_fn` is; LLMAgent's provider functions also read out-of-band keys from the context (the probe and compaction markers, the output budget). ^llmfn

**canonical**`(context: Any) -> str`
    `json.dumps(context, sort_keys=True, separators=(",", ":"), default=repr)`: equal JSON-ish contexts key equally whatever their dict order; a non-JSON leaf is keyed by its `repr`, so a set keys by its iteration order. ^canonical

**estimate_tokens**`(text: str) -> int`
    `len(text) // 4`. Sizes guards and filler, never billing, which reads the provider's usage. ^estimate-tokens




# Ops Semantics

## The cache
The key is the directive, the canonical context and the seed's value; `llm_fn` and `out_schema` are not in it, so swapping either on a live instance keeps serving old answers. The cache lives on the instance, never evicts, and is never persisted: a resumed run starts empty. A hit spends nothing and calls nothing, so it is invisible to the usage meter and the prompt log alike. The stored object is returned itself, not a copy; a caller that mutates a returned dict changes what the next hit returns.



## Retry seeds
Attempt 0 uses the base seed, so a valid first reply is cached under the same seed the key names. A retry's child seed differs per attempt but is a pure function of the base seed, so a deterministic `llm_fn` returns the same sequence every run.




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084), from the source at alienbio HEAD `64988be` and LLMAgent's `_make_op` (llm_agent.py ~825), no spend and no model call. Consumer census: `llm_agent.py` (the live path), `brief.py` (`estimate_tokens`), the `alienbio.suite` re-export. Not determined: whether any caller mutates a cached reply (T088 § suite/ops, by reading).
