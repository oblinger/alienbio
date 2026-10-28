---
description: "`interp`: the Expr interpreter — `evaluate(form, env)` dispatching every call by its head's kind, the guard machinery behind `guards:` / `on_fail:`, the nine special forms, `QuotedForm` (a quoted form as a `Dist`) and `TemplateHead` (a `!template` as a callable head with namespaced pools); plus the `alienbio.expr` package's export list. Source: `src/alienbio/expr/interp.py`, `src/alienbio/expr/__init__.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO expr Modules](ABIO%20expr%20Modules.md) → [ABIO Interp](ha://p/ABIO%20Interp) 
# ABIO Interp
The page for the one function that gives Expr forms meaning: how `evaluate` walks a form tree, what each head kind receives, how guards retry, prune or reject, and how a template call evaluates its body under its own namespace.

![ABIO Interp](ABIO%20Interp.svg) 
*Dispatch by kind* is the topic behind the three-way split out of `_dispatch`; *Seeds and paths* governs the dotted `child(key)` edges, which are how every node draws from its own seed; *Template instances* governs the claim (‡) that refuses a second path taking one instance name.

`interp.py` is evaluation only: the forms it walks are [ABIO Form](ABIO%20Form.md), the scope chain, seed, path and limits it carries are [ABIO Env](ABIO%20Env.md), and the head table it dispatches through is [ABIO Registry](ABIO%20Registry.md), whose builtin functions are [ABIO Heads](ABIO%20Heads.md). It registers the special forms itself at import, which is why `registry.py` cannot import it back. The language as written is [ABIO Expr Spec](../../ABIO%20Guides/ABIO%20Expr%20Spec.md); the evaluation model it implements, with D1–D10, is [ABIO Expr](../../ABIO%20Design/ABIO%20Expr/ABIO%20Expr.md), and the template layers [ABIO Expr Templates](../../ABIO%20Design/ABIO%20Expr/ABIO%20Expr%20Templates.md).



## interp Interface
The module-level surface: one function and two tuples. The special forms are registered heads, not exports (§ [The special forms](#the-special-forms)).

| interp | |
| --- | --- |
| [evaluate](#^evaluate) | Evaluate one form in one environment |
| [GUARD_KEYS](#^guard-keys) | The keywords every call accepts |
| [ON_FAIL](#^on-fail) | The three failure policies |

**evaluate**`(form: Any, env: Env) -> Any`
    Refuses first when `env.depth` exceeds `limits.depth`. Then: a `Name` is `env.lookup(path)`; a `Quoted` becomes a `QuotedForm` closed over `env`; a `Call` dispatches (§ [Dispatch by kind](#dispatch-by-kind)); a `Lazy` is forced; an `Include` or `PyRef` raises (they are resolved at load, never here); a mapping carrying `_type:` is the call `_type(**rest)`; any other mapping or list is rebuilt from its evaluated elements, each under `env.child(key)`; anything else is returned as is. Raises `ExprError` carrying the failing node's path. ^evaluate

**GUARD_KEYS**` = ("guards", "on_fail")`
    Stripped from a call's keywords before dispatch; either one present routes the call through the guard machinery. ^guard-keys

**ON_FAIL**` = ("retry", "prune", "reject")`
    The accepted `on_fail` values; anything else refuses, and `!ref retry` is read as the name `retry`. ^on-fail



## QuotedForm Interface
A frozen dataclass: a form held as a value together with the environment it was written in. It satisfies `suite.dist.Dist` (`sample(seed)`), which is how a `!q` argument reaches a drafter unsampled.

| QuotedForm | |
| --- | --- |
| [form](#^form) | The quoted form |
| [env](#^env) | The environment it closes over |
| [sample](#^sample) | Evaluate under a given seed |
| [run](#^run) | Evaluate with extra bindings |
| [__eq__](#^eq) | Equal when the forms are equal |

**form**`: Any`
    The unevaluated form. ^form

**env**`: Env`
    The definition environment: its bindings, registry, context and path. ^env

**sample**`(seed: Seed) -> Any`
    `evaluate(form, env.with_seed(seed))`: the same bindings and path, a different seed. ^sample

**run**`(bindings: Mapping | None = None, *, seed: Seed | None = None) -> Any`
    Evaluates the form in a child scope holding `bindings`, under `seed` when one is given; the `run` special form passes the caller's current seed. ^run

**__eq__**`(other) -> bool`
    True when `other` is a `QuotedForm` with an equal form, whatever either closes over; `__hash__` is `hash(repr(form))`. ^eq



## TemplateHead Interface
A `Head` of kind `template`, made by the `template` special form: the parameter list, the body, and the defining environment as a closure. Calling one evaluates the body in a child of the definition scope under the call's seed and the call's instance namespace.

| TemplateHead | |
| --- | --- |
| [positional](#^positional) | Positional parameter names |
| [params](#^params) | Keyword parameters with default forms |
| [body](#^body) | The unevaluated body |
| [env_def](#^env-def) | The definition environment |
| [pools](#^pools) | Which parameters carry pool names |
| [expand](#^expand) | Bind arguments, namespace, evaluate the body |

**positional**`: tuple[str, ...]`
    Names bound from positional arguments, in order; each may also be passed by keyword. ^positional

**params**`: dict[str, Any]`
    Keyword parameters and their default forms. A default is evaluated per call, under the call's seed, in a scope that already holds the parameters bound before it, so a default may use an earlier one. ^params

**body**`: Any`
    The form the call evaluates. ^body

**env_def**`: Env`
    The environment the `template` form was evaluated in; its bindings are the parent of every call's scope. ^env-def

**pools**`: tuple[str, ...] | None`
    `None` (every template written before T054 #5): every string argument, and every string inside a list argument, keeps the caller's spelling. A tuple: only those parameters' strings do. § [Template instances and pool names](#template-instances-and-pool-names). ^pools

**expand**`(args, kwargs, env: Env) -> Any`
    Evaluates each argument form in the caller's environment under `env.child(name)`, raising on too many positionals, a missing positional or an unknown keyword; evaluates the missing defaults; records which argument strings are pool names (`__passed__`); claims the instance name (`__instance__`); evaluates the body one level deeper. A keyword naming a positional parameter that was also passed positionally refuses (`argument 'a' is bound twice`). ^expand



## expr Interface
`alienbio.expr` (`__init__.py`) re-exports the language's public surface — `X`, `Env`, `Ctx`, `Limits`, `ExprError`, `UnsafeSpecError`, the forms `Call`/`Name`/`Quoted` with `is_form`/`contains_form`/`walk`, `evaluate`, `QuotedForm`, `TemplateHead`, the registry's `Head`/`Registry`/`registry`/`fn`/`expander`/`guard`/`GuardViolation`, and the loader's `ExprLoader`/`load_text`/`dump_structural` — and imports `heads` for its side effect, so importing the package registers the builtins. The suite-side heads register only when `Env.standard` imports `suite.expr_heads` and `suite.expr_experiment`.




# Interp Semantics

## Dispatch by kind
`_dispatch` asks the environment for the head (a locally bound template shadows the registry; [ABIO Env](ABIO%20Env.md)) and splits three ways on its kind:

| Kind | Receives | Then |
| --- | --- | --- |
| `special` | the argument forms and `env` | its return is the value |
| `template` | the argument forms and the caller's env, namespace set to the call's path | `expand` evaluates the body |
| `expander` | the argument forms and `env` | its returned form is evaluated one level deeper, under the call's seed |
| every function kind (`fn`, `dist`, `math`, `op`, `guard`, `constructor`, `drafter`, `agent`, `experiment`, …) | evaluated arguments; `ctx` / `env` injected when the callable declares them | its return is the value |

A function's positional arguments evaluate under `env.child("0")`, `env.child("1")`, …, its keywords under `env.child(name)`. A `TypeError`, `ValueError` or `ArithmeticError` from the callable becomes an `ExprError` naming the head and the node path, the exception class prefixed for the latter two (`exp: OverflowError: math range error`); anything else propagates as Python raised it.



## Seeds and paths
`Env.child(label)` extends the path and derives the seed `parent.child(label)` in one step, and `evaluate` calls it for every mapping key, list index and argument. A node's draws therefore depend only on the root seed and its path: editing one key never re-rolls a sibling, and the same form under a different key draws differently. `bind` and `scope` add bindings without moving the seed. A guard retry evaluates attempt `n` under `env.with_seed(seed.child(f"retry{n}"))`: a new seed at the same path.



## Guards and on_fail
A call carrying `guards:` or `on_fail:` is evaluated without them, then each guard runs over the produced value with its evaluated parameters; a guard fails by returning `False` or by raising `GuardViolation`, whose `offenders` name keys (dotted for depth) of a produced mapping.

| on_fail | On the first failing guard |
| --- | --- |
| `reject` (default) | raise `ExprError` naming the guard and its message |
| `retry` | re-evaluate under the next child seed, up to `limits.attempts` (8); raise after the last |
| `prune` | delete the named offenders from the produced mapping in place and re-check, until every guard passes or `attempts` rounds; refuse when the guard names nothing or nothing it names is present |

Guards are resolved by name (`nonempty`) or as calls with keyword parameters only (`max_size(n=3)`); a name that is not a `guard` head refuses.



## The special forms
Registered at import; each receives forms, so only the branch it takes is evaluated.

| Form | Arguments | Value |
| --- | --- | --- |
| `let` | `bindings` (mapping), `body` | `body` in a child scope;<br>a binding sees the earlier ones |
| `each` | `over`, `as`, `body`, optional `key`, `where` | a list, or a mapping when `key` is given; a duplicate key refuses; the length is charged to the meter before the loop |
| `if` | `cond`, `then`, optional `else` | the taken branch; `None` when false with no `else` |
| `quote` | `form` | a `QuotedForm` |
| `run` | `form`, optional `bindings` | a quoted form evaluated now, under the current seed |
| `seed` | `label` | `ctx.seed.child(label)`, a `Seed` |
| `template` | keywords `positional`, `params`, `body`, `name`, `pools` | a `TemplateHead`, named by `name` or the key it is bound to |
| `op:and` / `op:or` | operands | the first falsy / truthy operand, short-circuit |

Each refuses an unknown keyword; surplus positional arguments are not checked.



## Template instances and pool names
A template call names its instance by the last segment of the call's path (the key it is bound to, or the list index), nested under the enclosing instance: `krel`, and `c1.krel` inside instance `c1`. The name is claimed in `ctx.instances`, shared by every child context of one load, against the call's document path; a second path claiming the same name refuses (‡ in the figure), so two `cell:` keys under different non-template parents must be renamed apart. Inside the body, `Env.pool(name)` returns the caller's spelling for a string that arrived as a pool argument and `instance.name` for any other; [ABIO Env](ABIO%20Env.md) § Pool names.

A retried call keeps its path, so its instance on every attempt is named by its key and two retried templates under one parent do not collide; only the seed moves.



## Depth
`limits.depth` (100) is checked on entry to `evaluate`. `Env.child`, a template body and an expander's output each add a level; `bind` and `scope` do not. A `RecursionError` that still slips past is converted where a lazy binding is forced ([ABIO Env](ABIO%20Env.md)).




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084) from the source at alienbio HEAD `c67f052` (read with `git show`, a concurrent worker editing `src/`). Run against an export of that tree: the retried template instance comes out `retry1.P` where the unretried one is `plain.P`; `t(1, a=2)` with `a` positional returns 1; `exp(1000)` raises a bare `OverflowError`. Not determined: whether any caller dedups on `QuotedForm` equality (it ignores the closure). Findings filed on T088.
- 2026-10-28 — refreshed against `0eb23e5`: a retry re-draws on a child seed at the same path (the instance keeps its key), a keyword rebinding a bound positional refuses, `ValueError`/`ArithmeticError` from a callable become `ExprError` (`e2efa89`).
