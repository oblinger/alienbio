---
description: "`registry`: the Expr head table — `Head` (name, kind, callable, injection), `Registry` (register with collision refusal, kind-filtered views), the process-wide `registry`, and the decorators `fn`, `expander`, `guard` and `special` through which Python enters the language; `GuardViolation`. Source: `src/alienbio/expr/registry.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO expr Modules](ABIO%20expr%20Modules.md) → [ABIO Registry](ha://p/ABIO%20Registry) 
# ABIO Registry
The page for the one table a spec can reach Python through: what a head is, the kinds that decide how its arguments arrive, how a decorator puts a function into the table, when a second registration of a name refuses, and the narrowed views the rate compiler sees.

![ABIO Registry](ABIO%20Registry.svg) 
*Head kinds* is the topic behind the `kind` sub-label on every head; *Collisions and replace* governs the refusal (‡) on a second registration; *Views* governs the dotted `view` edge.

`registry.py` holds the table and the doors into it, and is the sandbox: a name absent here (and not bound in scope) cannot be called. It imports nothing from the rest of `expr/`, so every other module can import it. The interpreter that dispatches on a head's kind is [ABIO Interp](ABIO%20Interp.md) (which registers the special forms), the environment that resolves a call name to a head, letting a bound template shadow the table, is [ABIO Env](ABIO%20Env.md), and the builtin heads are [ABIO Heads](ABIO%20Heads.md). The suite registers blocks and worlds in [ABIO ExprHeads](../ABIO%20suite/ABIO%20ExprHeads.md) and drafters, agents and experiments in [ABIO ExprExperiment](../ABIO%20suite/ABIO%20ExprExperiment.md); how a Python author writes one is [ABIO Expr Python Escapes](../../ABIO%20Design/ABIO%20Expr/ABIO%20Expr%20Python%20Escapes.md).



## Head Interface
A dataclass: one entry of the table.

| Head | |
| --- | --- |
| [name](#^name) | The name a spec calls it by |
| [kind](#^kind) | Decides how arguments arrive |
| [fn](#^fn) | The callable |
| [meta](#^meta) | Free metadata, `summary` by convention |
| [guarded](#^guarded) | A drafter the no-peeking guard watches |
| [guarded_params](#^guarded-params) | Its dials the guard watches |
| [injects](#^injects) | Which of `ctx` / `env` it receives |
| [is_special](#^is-special) | Kind `special` |
| [is_expander](#^is-expander) | Kind `expander` or `template` |
| [is_function](#^is-function) | Kind in `FUNCTION_KINDS` |

**name**`: str`
    The decorator's `name=`, else the function's `__name__`. ^name

**kind**`: str`
    § [Head kinds](#head-kinds). ^kind

**fn**`: Callable`
    For a function kind, called with evaluated arguments; for `expander` and `special`, called as `fn(args, kwargs, env)` with forms; for a guard, called as `fn(value, ctx, **params)`. ^fn

**meta**`: dict = {}`
    The decorator's extra keywords; `describe` reads `summary`. ^meta

**guarded**`: bool = False`
    Metadata only: the interpreter never reads it. The suite's no-peeking guard reads `guarded_drafters()` off the table to know which drafters may not host a live model without a registration. ^guarded

**guarded_params**`: frozenset[str]`
    The dials of a guarded drafter that the same guard checks. ^guarded-params

**injects**`: frozenset[str]`
    Computed at registration from the signature: `ctx` and/or `env` when the callable declares a parameter of that name (keyword-only or positional-or-keyword). The interpreter passes them; a spec cannot. ^injects

**is_special**`: bool` (property)
    `kind == "special"`. ^is-special

**is_expander**`: bool` (property)
    `kind in ("expander", "template")`. ^is-expander

**is_function**`: bool` (property)
    `kind in FUNCTION_KINDS`. ^is-function



## Registry Interface
A name → `Head` table. A view is the same table filtered to some kinds.

| Registry | |
| --- | --- |
| [register](#^register) | Add a head, refusing a collision |
| [get](#^get) | The head by name |
| [__contains__](#^contains) | Whether `get` would succeed |
| [names](#^names) | Every visible name, sorted |
| [view](#^view) | A live, kind-filtered view |
| [describe](#^describe) | Name, kind, signature, summary per head |

**register**`(head: Head, *, replace: bool = False) -> Head`
    Refuses on a view. Refuses when the name is taken by a different callable that is not the same definition (§ [Collisions and replace](#collisions-and-replace)), naming the existing head's kind and `module.qualname`; with `replace=True` the new head wins. ^register

**get**`(name: str) -> Head`
    Raises `KeyError` for an absent name, or on a view for a head whose kind the view hides (special forms always show). ^get

**__contains__**`(name) -> bool`
    `get` without the raise. ^contains

**names**`() -> list[str]`
    Sorted names this registry (or view) shows. ^names

**view**`(kinds) -> Registry`
    A registry over the same dict, showing only `kinds` plus the special forms; it sees heads registered after it was made. ^view

**describe**`() -> list[dict]`
    One `{name, kind, signature, summary}` per visible head; read only by the capability test that proves every head is called. ^describe



## GuardViolation Interface
The exception a guard raises to reject what a call produced.

| GuardViolation | |
| --- | --- |
| [message](#^message) | Why |
| [offenders](#^offenders) | What `on_fail: prune` may drop |

**message**`: str = "guard failed"`
    Carried into the `ExprError` the interpreter raises. ^message

**offenders**`: tuple[str, ...]`
    Keys of the produced mapping, dotted for depth; a violation without them cannot be pruned. ^offenders



## registry Interface
The process-wide table and the four doors into it.

| registry | |
| --- | --- |
| [FUNCTION_KINDS](#^function-kinds) | The kinds whose arguments arrive evaluated |
| [registry](#^registry) | The one table |
| [fn](#^fn-decorator) | Register a function head |
| [expander](#^expander) | Register an expander head |
| [guard](#^guard) | Register a guard |
| [special](#^special) | Register a special form |

**FUNCTION_KINDS**`: frozenset[str]`
    `fn`, `dist`, `math`, `rate`, `scoring`, `action`, `measurement`, `guard`, `constructor`, `op`, `drafter`, `agent`, `experiment`. ^function-kinds

**registry**`: Registry`
    The default table every `Env.standard` uses; filled at import time by the modules that decorate into it. ^registry

**fn**`(_f=None, *, name=None, kind="fn", guarded=False, guarded_params=(), into=registry, replace=False, **meta)`
    Decorator, bare or called. Refuses an unknown `kind`. Registers, then sets `func.head` where the object allows it, and returns the function unchanged. ^fn-decorator

**expander**`(_f=None, *, name=None, guarded=False, guarded_params=(), into=registry, replace=False, **meta)`
    Decorator for `fn(args, kwargs, env) -> form`: receives the argument forms, and its returned form is evaluated under the call's seed. ^expander

**guard**`(_f=None, *, name=None, into=registry, replace=False, **meta)`
    Decorator for `fn(value, ctx, **params) -> bool`: `False` or `GuardViolation` rejects. Always `guarded=False`. ^guard

**special**`(name: str, func, *, into=registry, **meta) -> Head`
    Registers an interpreter-internal form with `replace=True`; only `interp.py` calls it. ^special




# Registry Semantics

## Head kinds

| Kind | Arguments arrive | Registered by |
| --- | --- | --- |
| `special` | as forms, with `env`; returns a value | `special` (interp) |
| `expander` | as forms, with `env`; returns a form | `expander` |
| `template` | as forms; a `TemplateHead` made by the `template` form, bound in scope, never in the table | the interpreter |
| the function kinds | evaluated, `ctx` / `env` injected | `fn(kind=…)`, `guard` |

The function kinds differ only as tags: `dist` for draws, `math` and `op` for the builtins, `constructor` for entity heads, `drafter`/`agent`/`experiment` for the suite's layers 4–6. Views filter on them; dispatch does not. A guard is a function kind too, so `nonempty([1])` called as a head returns `True` (its `ctx` parameter is injected).



## Collisions and replace
A second registration of a name refuses unless the callable is the same object or the same definition: equal `module.qualname` and either the same file and first line, or equal source text with leading `@` lines dropped. The case it exists for is one `helpers.py` copied verbatim across catalog examples, each executed by a trusted `.py` include under the module name `alienbio_include_helpers`. Before T054 #6 every decorator passed `replace=True`, so a trusted include naming a function `max` shadowed the builtin for the rest of the process.

Only lines that begin with `@` are dropped, so a decorator call spread over several lines leaves its continuation lines in the compared text (‡): two copies of a helper that differ only in a multi-line decorator's `summary=` refuse, where the same pair written on one decorator line is accepted. When the same definition does re-register, the later `Head` (with its metadata) replaces the earlier one.



## Views
`view(kinds)` shares the dict rather than copying it, so a head registered after the view was made is visible through it, and registering into a view refuses. The rate compiler evaluates a rate law through `view({"rate", "math", "op", "dist"})`, so a rate law can call `exp` but not a drafter or a block head.



## Registration is import
Nothing is registered until a module that decorates into the table is imported: `expr/__init__` imports `heads` (and `interp`, for the special forms); `Env.standard` imports `suite.expr_heads` and `suite.expr_experiment`; the drafters register when their module imports. A process that builds an `Env` by hand without importing those sees fewer heads.




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084) from the source at alienbio HEAD `c67f052` (read with `git show`). Run against an export of that tree: two `.py` files under one stem whose `@fn` differs only in `summary=` register both when the decorator is one line and refuse the second when it spans four. Findings filed on T088.
