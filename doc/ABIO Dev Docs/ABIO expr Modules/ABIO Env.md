---
description: "`env`: the Expr environment — `Env` (a scope chain of bindings, the head registry and the run's context), `Ctx` (seed, node path, trust, limits, the per-load instance claims), `Limits` and its cumulative `Meter`, `Lazy` top-level bindings, `ExprError`; `Env.load` turns a YAML file into lazy bindings after includes resolve, `Env.pool` namespaces pool names inside a template instance. Source: `src/alienbio/expr/env.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO expr Modules](ABIO%20expr%20Modules.md) → [ABIO Env](ha://p/ABIO%20Env) 
# ABIO Env
The page for what every Expr evaluation runs in: the bindings a name resolves against, the head a call name resolves to, the seed and path each node draws under, the caps that refuse a runaway spec, and how a YAML file becomes a scope of lazily evaluated keys.

![ABIO Env](ABIO%20Env.svg) 
*Seeds and paths* is the topic behind the `child(key)` edge (one step extends the path and derives the seed); *The meter* governs the dotted `charge` edge, cumulative across one environment's evaluation.

`env.py` holds the state; the walk that consumes it is [ABIO Interp](ABIO%20Interp.md), the head table `Env.head` falls back to is [ABIO Registry](ABIO%20Registry.md), the YAML reader `Env.load` calls is [ABIO YamlTags](ABIO%20YamlTags.md), and the include and `!py` resolution it runs before binding anything is [ABIO Include](ABIO%20Include.md). The scope chain underneath `Env.bindings` is `spec_lang.scope.Scope`; the seed is `suite.dist.Seed`, the one upward import `expr/` makes. `Env.standard` is the only place the suite-side heads ([ABIO ExprHeads](../ABIO%20suite/ABIO%20ExprHeads.md), [ABIO ExprExperiment](../ABIO%20suite/ABIO%20ExprExperiment.md)) get registered. The subsystem view is [ABIO-Expr](../../ABIO%20Architecture/ABIO-Expr.md).



## Env Interface
Bindings, heads and context, immutable in spirit: every `child`, `bind`, `scope` and `with_*` returns a new `Env` sharing what it did not change. The one exception is the scope object itself, which `let`, template calls and `load` write into after creating it.

| Env | |
| --- | --- |
| [bindings](#^bindings) | The scope chain names resolve against |
| [registry](#^registry) | The head table |
| [ctx](#^ctx) | Seed, path, trust, limits |
| [ns](#^ns) | The namespace a template or expander call runs in |
| [depth](#^depth) | Nesting level, checked against `limits.depth` |
| [standard](#^standard) | A root environment over the default registry |
| [child](#^child) | Same scope, child seed, extended path |
| [bind](#^bind) | A child scope holding evaluated values |
| [scope](#^scope) | A child scope over a given parent |
| [with_seed](#^with-seed) | The same env under another seed |
| [with_ctx](#^with-ctx) | The same env under another context |
| [with_ns](#^with-ns) | The same env under another namespace |
| [path](#^path) | The node's dotted path |
| [error](#^error) | An `ExprError` at this node |
| [lookup](#^lookup) | Resolve a dotted name |
| [head](#^head) | Resolve a call's head name |
| [load](#^load) | A YAML document as lazy bindings |
| [hydrate](#^hydrate) | Resolve includes inside loaded forms |
| [pool](#^pool) | A pool name as this scope sees it |
| [force_all](#^force-all) | Evaluate every lazy binding in this scope |

**bindings**`: Scope`
    A `spec_lang.scope.Scope`: a mapping with a parent chain. `lookup` reads through the chain; `load`, `let` and template calls write into a fresh child. ^bindings

**registry**`: Registry`
    The head table; the default registry unless `standard` was given another or a view. ^registry

**ctx**`: Ctx`
    The per-node context; § [Ctx Interface](#ctx-interface). ^ctx

**ns**`: str = ""`
    Set by the interpreter to the call's path when it hands an env to a template or an expander; template bodies take it as their scope's namespace. ^ns

**depth**`: int = 0`
    Incremented by `child` (and by a template body or an expander's output in the interpreter); `bind`, `scope` and `with_*` keep it. ^depth

**standard**`(seed: int | Seed = 0, *, trusted=False, registry=None, limits=None, bindings=None) -> Env` (classmethod)
    Imports `expr.heads`, `suite.expr_heads` and `suite.expr_experiment` so every builtin and suite head is registered, then builds a root scope named `root` from `bindings` under `Ctx(seed, trusted, limits)`; a passed `limits` is copied with a fresh `Meter`, so two environments never share a running total. An untrusted env (the default) refuses `.py` includes and `!py`. ^standard

**child**`(label: str) -> Env`
    The env for a named sub-node: the same scope, `ctx.child(label)` (path extended, seed derived) and depth plus one. Every mapping key, list index and argument the interpreter evaluates goes through it. ^child

**bind**`(**values) -> Env`
    A child scope holding `values`, which are already evaluated; seed, path and depth unchanged. ^bind

**scope**`(data: Mapping | None = None, parent: Scope | None = None) -> Env`
    A child scope over `parent` (default: this env's bindings) holding `data`. ^scope

**with_seed**`(seed: Seed) -> Env`
    This env with `ctx.seed` replaced, path kept; what `QuotedForm.sample` uses. ^with-seed

**with_ctx**`(ctx: Ctx) -> Env`
    This env with the whole context replaced. ^with-ctx

**with_ns**`(ns: str) -> Env`
    This env with `ns` replaced. ^with-ns

**path**`: str` (property)
    `ctx.path`, the dotted document path every error message carries. ^path

**error**`(message: str) -> ExprError`
    An `ExprError` stamped with this node's path, for the caller to raise. ^error

**lookup**`(path: str) -> Any`
    Splits on `.`; resolves the first segment in the scope chain (forcing a `Lazy`), then steps into the value: a mapping key, then a sequence index for a digit segment, then an attribute through `access.read_attr` ([ABIO Access](ABIO%20Access.md)): the name passes the sandbox's check (no dunders, no `format`, `mro`, frame or code prefixes, nothing starting with `_`) and the receiver's type is judged before the lookup — plain data and the domain records' data attributes only, a method never read as a value, every other type refused by name. Raises on a refused step, an unbound name, an index out of range or a missing key and attribute. ^lookup

**head**`(name: str) -> Head`
    § [Head lookup](#head-lookup). Raises `unknown head` when neither the scope nor the registry has it. ^head

**load**`(source: str | Path, *, text: str | None = None, base=None) -> Env`
    § [Loading a file](#loading-a-file). Returns the env whose new scope holds one `Lazy` per top-level key. Raises `ExprError` when the document is not a mapping, and `UnsafeSpecError` from an untrusted include it may not make. ^load

**hydrate**`(data, *, base=None) -> Any`
    Resolves `Include` and `PyRef` nodes inside already-loaded forms under this env's trust, relative to `base` or the working directory. Unlike `load`, it passes no cycle set and no executed modules. ^hydrate

**pool**`(name: Any) -> str`
    § [Pool names](#pool-names). ^pool

**force_all**`() -> dict[str, Any]`
    Evaluates every binding local to this scope (not its parents) and returns them by key; the call a loaded document's consumer makes to get values. ^force-all



## Ctx Interface
A frozen dataclass carried by every `Env`. `child` is the only way the seed moves on its own.

| Ctx | |
| --- | --- |
| [seed](#^seed) | This node's seed |
| [path](#^ctx-path) | This node's dotted path |
| [trusted](#^trusted) | Whether `.py` includes and `!py` are allowed |
| [limits](#^limits) | The caps |
| [instances](#^instances) | Template instance name to claiming path |
| [rng](#^rng) | A generator from the seed |
| [child](#^ctx-child) | Extend the path and derive the seed |

**seed**`: Seed`
    A `suite.dist.Seed`; a function head that declares `ctx` draws from `ctx.rng`. ^seed

**path**`: str = ""`
    The dotted path from the document root, the location every `ExprError` names. ^ctx-path

**trusted**`: bool = False`
    Read by `load` and `hydrate` and passed to the include resolver. ^trusted

**limits**`: Limits`
    A fresh `Limits()` per `Env.standard`, or a copy of the passed one with its own meter. ^limits

**instances**`: dict[str, str]`
    The template instance names claimed in this load, each with the document path that claimed it. `dataclasses.replace` copies the reference, so every child context of one root shares the one dict. ^instances

**rng**`: np.random.Generator` (property)
    `seed.rng()`, a new generator on each read. ^rng

**child**`(label: str) -> Ctx`
    `path + "." + label` and `seed.child(label)`. ^ctx-child



## Limits Interface
A frozen dataclass of caps. Exceeding one raises `ExprError`; nothing is ever truncated.

| Limits | |
| --- | --- |
| [entities](#^entities) | Elements one producer may make, and in total |
| [depth](#^limits-depth) | Evaluation nesting |
| [attempts](#^attempts) | Guard retries and prune rounds |
| [meter](#^meter) | The running total |
| [charge](#^charge) | Count elements, refuse past the cap |

**entities**`: int = 1_000_000`
    The cap on one `each`, `range`, `list` or other sized producer, and on the running total in `meter`. ^entities

**depth**`: int = 100`
    The nesting cap `evaluate` checks; one template level costs about 5.5 Python frames, so 100 sits under the interpreter's own recursion limit. A forced binding counts too ([Lazy bindings and cycles](#lazy-bindings-and-cycles)), so a chain of about fifty names reaches it. ^limits-depth

**attempts**`: int = 8`
    `on_fail: retry` attempts and `on_fail: prune` rounds. ^attempts

**meter**`: Meter`
    The cumulative count; created per `Limits` object (and replaced by `Env.standard` on a passed one), excluded from equality and repr. ^meter

**charge**`(n: int, path: str, what: str) -> None`
    Refuses when `n` alone exceeds `entities`, otherwise adds `n` to the meter and refuses when the running total does. ^charge



## Lazy Interface
A top-level binding of a loaded document, evaluated on first lookup so a key may refer to any other key in its file regardless of order.

| Lazy | |
| --- | --- |
| [form](#^lazy-form) | The unevaluated form |
| [env](#^lazy-env) | The scope it evaluates in |
| [state](#^state) | `pending`, `evaluating` or `done` |
| [value](#^value) | The cached value once `done` |

**form**`: Any`
    The form as loaded and hydrated. ^lazy-form

**env**`: Env`
    The env `load` returned; the form evaluates under `env.child(key)`. ^lazy-env

**state**`: str`
    Moves `pending` → `evaluating` → `done`, back to `pending` when evaluation raises; a lookup that finds `evaluating` raises `cyclic definition`. ^state

**value**`: Any`
    Set when evaluation completes; returned on every later lookup. ^value



## ExprError Interface
A `ValueError` carrying the path of the node that failed; every Expr failure raises one, and its text is `"{path}: {message}"`.

| ExprError | |
| --- | --- |
| [message](#^message) | The failure without the path |
| [path](#^exprerror-path) | The failing node's dotted path |

**message**`: str`
    What went wrong. ^message

**path**`: str`
    The document path, `""` when the failure has no node (a YAML error). ^exprerror-path



## env Interface
Two reserved binding names a template instance carries, and the module's one helper.

| env | |
| --- | --- |
| [PASSED_KEY](#^passed-key) | Argument string to the caller's pool name |
| [INSTANCE_KEY](#^instance-key) | The instance's own namespace |
| [Meter](#^meter-class) | The allocation counter |

**PASSED_KEY**` = "__passed__"`
    Bound in a template body's scope to a mapping from each pool argument's string to the name it denotes in the caller's scope. A spec cannot name it: the parser refuses dunder identifiers. ^passed-key

**INSTANCE_KEY**` = "__instance__"`
    Bound in a template body's scope to the instance name (`krel`, `c1.krel`). ^instance-key

**Meter** (class)
    One slot, `allocated`, incremented by `Limits.charge`. ^meter-class




# Env Semantics

## Seeds and paths
`Ctx.child(label)` is the one step that moves both: the path gains `.label` and the seed becomes `seed.child(label)`. Because the interpreter calls it for every key, index and argument, a node's draws are a function of the root seed and its document path alone. `bind` and `scope` never touch the context, so a `let` binding does not shift the seed of the body that follows it.



## Head lookup
`head(name)` with an undotted name checks the scope chain first. A binding there wins over the registry when it is a head already (an evaluated `!template`), a `Lazy` whose pending form is a `template` call (forced on the spot), a `Lazy` holding a resolved `!py` object or `.py` function, or any other callable value; a callable becomes a function head with `ctx` / `env` injection read off its signature, after `access.check_callable` — in an untrusted env only a plain Python function qualifies, never a class, a builtin, a bound method or a callable object. Any other binding — a document key that merely shares a head's name, such as `world: !world {...}` — is not forced and does not shadow, so evaluating that key does not report a false cycle. Otherwise the full name goes to the registry.

A dotted name whose first segment is bound resolves its whole path through the scope (`lookup`): a head at the end of it is returned, a callable becomes a function head, and anything else — an unresolvable path included — falls to the registry. So `!t.anything {}` is `unknown head` unless the registry has `t.anything`, where it once called template `t`.



## Pool names
Inside a template instance, `pool(name)` returns the caller's spelling for a string that arrived as a pool argument (`__passed__`) and `instance.name` for any other (`__instance__`); outside any template a name is itself. That is how a parent wires a template's pools without the template knowing the parent's names. Which arguments count as pools is the template's `pools:` declaration ([ABIO Interp](ABIO%20Interp.md) § Template instances and pool names); the block heads that call `pool` are in [ABIO ExprHeads](../ABIO%20suite/ABIO%20ExprHeads.md).



## Loading a file
`load` reads the text (or takes `text=`), parses it with the Expr YAML loader, and refuses a non-mapping document. Then, in order: the `_includes_` list resolves (`.py` entries execute for their registrations, `.yaml` entries contribute top-level keys); every `Include` and `PyRef` in the tree is replaced; included keys are added where the file does not define them; each top-level key becomes a `Lazy` in a fresh child scope. Relative includes resolve against `base`, else the file's own directory, else — for text with no file behind it — the process's working directory. The file itself seeds the include cycle set.



## Lazy bindings and cycles
`_force` marks a `Lazy` `evaluating` before evaluating its form and `done` after. A lookup that meets `evaluating` is a cycle. When evaluation raises, the state returns to `pending`, so the next lookup re-evaluates and raises the binding's own error rather than `cyclic definition`. A `RecursionError` during forcing is converted to an `ExprError` at the binding. A binding evaluates one level below the deeper of its definition and the lookup forcing it, so a chain of names (`a0: a1 + 1`, `a1: a2 + 1`, …) counts toward `limits.depth` and stops at the cap — about fifty names at the default 100 — rather than at Python's recursion limit (since `dc92971`, T091 C11).



## The meter
Every sized producer (`each`, `range`, `list`, `sorted`, `zip`, `sum`, `add`, `mul`, `flatten`, `fstr`, and the text builders `op:mod`, `op:fmt` and `op:method`, charged a bound before they build) calls `limits.charge`, which refuses both a single producer over `entities` and a running total over it, so a spec that is cheap per step and ruinous in total is stopped before the memory is gone. The total lives on the `Limits` object, and `Env.standard` gives every environment its own: a fresh `Limits()`, or the passed one copied with a new `Meter`, so one `Limits` handed to several environments no longer sums their allocations.




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084) from the source at alienbio HEAD `c67f052` (read with `git show`). Run against an export of that tree: `!t.anything {}` evaluates template `t`; one `Limits(entities=1000)` passed to three `Env.standard` calls refuses the third `range(400)` at a running total of 1200; a lazy key whose evaluation raised reports `cyclic definition` on the second lookup. No caller in `src/` passes `limits=` today, so the shared meter is latent. Findings filed on T088.
- 2026-10-28 — refreshed against `0eb23e5`: `Env.standard` gives a passed `Limits` its own meter, a failed lazy binding returns to pending and re-raises its own error, a dotted head resolves its whole path, the meter list gains the text builders (`e2efa89`, `c90ce0d`).
- 2026-10-29 — refreshed for `dc92971` (T091 C11): a forced binding evaluates one level below the deeper of its definition and its lookup, so name chains count toward `limits.depth`. Figure still true.
- 2026-10-30 — refreshed for `5c08bc8` (T091 AG1): `lookup`'s attribute step and a bound callable used as a head go through [ABIO Access](ABIO%20Access.md) — receiver type judged after a mapping key or index, `_` names refused everywhere, `check_callable` on a bound callable. Figure still true.
