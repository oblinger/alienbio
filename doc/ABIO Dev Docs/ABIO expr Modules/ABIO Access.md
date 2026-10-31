---
description: "`access`: what an Expr expression may read off a value — the receiver-type allowlist (`PLAIN_TYPES` by exact type, the domain records named in `DOMAIN_CLASS_NAMES`), the attribute-name rule, `read_attr` and `method` for attribute steps and method calls, `check_callable` for a bound callable used as a head, `check_reference` for what a `!py` walk or an included helper hands back, `DENIED_ENTRY_POINTS`, the framework modules refused whole under trust too, `PY_ALLOWED_MODULES` + `allowed_framework_code`, the framework code a `!py` reference may land on, and `check_returned` for what a trusted helper returns. Source: `src/alienbio/expr/access.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO expr Modules](ABIO%20expr%20Modules.md) → [ABIO Access](ha://p/ABIO%20Access) 
# ABIO Access
The page for the sandbox's type allowlist: which values an expression may read attributes from or call methods on, which ones it may only read data from, and why every other value — environments, quoted forms, seeds, modules, classes, functions — is opaque even to a trusted spec.

![ABIO Access](ABIO%20Access.svg) 
*The three receiver classes* is the topic behind the three verdict boxes; *Bound callables* governs the `check_callable` branch, *Denied modules and allowed code* its trusted leg.

`access.py` is consulted by every path that reads an attribute or calls a method: the dotted-name steps of `Env.lookup` and a bound callable turned into a head ([ABIO Env](ABIO%20Env.md)), and `op:attr` / `op:method` ([ABIO Heads](ABIO%20Heads.md)). The attribute-name filter it builds on (no dunders, `format`, `format_map`, `mro`, `subclasses`, frame and code prefixes) is `spec_lang.safe_eval._check_attr_name`. The other half of the Python boundary is the `!py` import-root allowlist in [ABIO Include](ABIO%20Include.md); the head table, the only door a spec has into Python, is [ABIO Registry](ABIO%20Registry.md). The user-facing rule is [ABIO Expr Spec](../../ABIO%20Guides/ABIO%20Expr%20Spec.md) § Files, includes and trust; the subsystem view is [ABIO-Expr](../../ABIO%20Architecture/ABIO-Expr.md).



## Access Interface
Three allowlists, a deny list, four predicates and six checks. Every refusal raises `UnsafeExpressionError` (from `spec_lang.safe_eval`), which the callers turn into an `ExprError` at the node's path.

| access | |
| --- | --- |
| [PLAIN_TYPES](#^plain-types) | Values with attributes and methods, by exact type |
| [DOMAIN_CLASS_NAMES](#^domain-class-names) | Records with readable data attributes |
| [domain_types](#^domain-types) | The resolved domain classes |
| [is_plain](#^is-plain) | Exact-type membership in `PLAIN_TYPES` |
| [is_domain](#^is-domain) | An instance of a domain class |
| [check_name](#^check-name) | The attribute-name rule |
| [read_attr](#^read-attr) | `value.name` for an expression |
| [method](#^method) | The bound method for `op:method` |
| [check_callable](#^check-callable) | A bound callable called as a head |
| [DENIED_ENTRY_POINTS](#^denied-entry-points) | Framework modules refused whole |
| [PY_ALLOWED_MODULES](#^py-allowed-modules) | Framework modules `!py` code may come from |
| [denied_entry_point](#^denied-entry-point) | The deny entry an object falls under |
| [allowed_framework_code](#^allowed-framework-code) | A head's function or allow-listed code |
| [check_reference](#^check-reference) | What a `!py` walk or helper name yields |
| [check_returned](#^check-returned) | What a trusted helper returns |

**PLAIN_TYPES**`: frozenset[type]`
    `str`, `bytes`, `int`, `float`, `complex`, `bool`, `NoneType`, `list`, `tuple`, `dict`, `set`, `frozenset`. Matched by exact type, so a subclass such as `spec_lang.scope.Scope` is not plain. ^plain-types

**DOMAIN_CLASS_NAMES**`: tuple[str, ...]`
    Thirty-nine `module:qualname` strings: the five `Dist` classes (`Constant`, `Uniform`, `Normal`, `LogNormal`, `Choice`); `Entity` and its subclasses, `WorldImpl`, `Compartment`, `Transport`, `GrowthLaw`, `DeathLaw`, `CountFlowSpec`, `Modulation`; `Skeleton`, `SkeletonBlock`, `Fragment`, `Port`, `PoolBinding`, `Provenance`, `PortDir`, `Role`, `PoissonSchedule`; the `suite.types` records (`Timeline` through `Suite`); `Draft`, `TrialRecord`, `ProbeRecord`. Strings because the classes live above `expr/` in the import graph. A `QuotedForm` is a `Dist` too and is deliberately absent. ^domain-class-names

**domain_types**`() -> tuple[type, ...]`
    Imports and resolves every entry on first call (cached). A missing class or a non-class entry raises at import rather than shortening the list. ^domain-types

**is_plain**`(value) -> bool`
    `type(value) in PLAIN_TYPES`. ^is-plain

**is_domain**`(value) -> bool`
    An instance of a domain class, subclasses included; a class object is never a domain value, even a domain class itself. ^is-domain

**check_name**`(name: str) -> None`
    Refuses what `_check_attr_name` refuses, and any name starting with `_`. ^check-name

**read_attr**`(value, name: str) -> Any`
    Checks the name, then judges the receiver's type before looking the attribute up: plain data returns the attribute, refusing a method read as a value (`call it`); a domain value returns a data attribute, refusing a method; any other type refuses, naming it (`module 'os'`, `class 'Env'`, `alienbio.expr.interp.QuotedForm`). A missing attribute on an allowed type is `AttributeError`, the caller's "no attribute". Mapping keys are the caller's to read first. ^read-attr

**method**`(value, name: str) -> Any`
    The bound method `value.name`, for a plain receiver only; a domain value's methods (`Entity.save`, `Skeleton.materialize`) and every other type's refuse. `op:method` then applies its in-place refusal and its charge ([ABIO Heads](ABIO%20Heads.md)). ^method

**check_callable**`(func, *, trusted: bool) -> None`
    A bound value that is not a registered head, called as one. Untrusted: always refuses — only registered heads and templates are callable (`d943ce4`, T091 AL8; untrusted YAML cannot define a function, so any function it reaches leaked out of framework data). Trusted: passes what the author bound, except a name in a denied module; what it returns is then judged by `check_returned` (`df0bc6c`, T091 AP1 — `Env._callable_head` wraps the call). ^check-callable

**DENIED_ENTRY_POINTS**`: tuple[str, ...]`
    Seventeen `module:*` entries, each the module and everything in or under it (`df0bc6c`, T091 AP2 — by module, not by function: `!py alienbio.report.example_rows` ran every catalog example, and `resolve_source_path` + `write_models_snapshot` wrote any file). Loading and evaluating specs, running helper code: `expr.include`, `expr.interp`, `expr.yaml_tags`, `expr.env`, `suite.spec`, `suite.expr_experiment`. Running experiments and writing results: `suite.experiment`, `suite.store`, `suite.mass_trial`, `suite.runner`. Network, key and snapshot: `suite.llm_agent`. Report, config, CLI: `report`, `_report_plugin`, `capabilities`, `config`, `commands`, `cli` (all under `alienbio.`). Checked at every `!py` step, on every name read off an included helper, in `check_callable` under trust and on every value `check_returned` walks. ^denied-entry-points

**PY_ALLOWED_MODULES**`: tuple[str, ...]`
    `("alienbio.suite.dist", "alienbio.bio.makers")` — the `alienbio` modules whose functions and classes a `!py` reference may land on, beside the registered heads' own functions (`df0bc6c`, T091 AP2). ^py-allowed-modules

**denied_entry_point**`(obj) -> str | None`
    The entry whose module `obj`'s owner module equals or sits under, else `None`. A `functools.partial` or bound method is unwrapped to the function it wraps first (T091 AP1: a partial has no `__qualname__`, so `partial(load_spec, …)` passed); only a module, class or callable has an owner — a data value, whatever its class's module, never matches. ^denied-entry-point

**allowed_framework_code**`(obj) -> bool`
    `obj`, unwrapped, is a registered head's function (`Registry.has_fn`, [ABIO Registry](ABIO%20Registry.md)) or owned by a module in `PY_ALLOWED_MODULES`. Plain data and domain values elsewhere in `alienbio` are not judged by it and stay readable. ^allowed-framework-code

**check_reference**`(value, what: str) -> None`
    What a trusted spec obtains by reference — a `!py` walk's result, a name read off an included helper: refuses a denied entry point and a module; passes a callable (the caller checks its owner), plain data or a domain value; refuses anything else (a `Path`, a logger, a `Registry`, an `Env`). ^check-reference

**check_returned**`(value, what: str) -> None`
    What a trusted bound callable — an included helper's function, a `!py` function — returned (`df0bc6c`, T091 AP1: a helper's `return subprocess` or `partial(load_spec, …)` passed). Walks plain lists, tuples, sets, frozensets and dict keys and values (each object once); an instance of the helper's own class is inert data and passes; every other item goes through `check_reference`, and a callable or class must be the helper's own code or, under `alienbio`, `allowed_framework_code` — else `UnsafeExpressionError` naming its module. Called by `Env._callable_head`'s wrapper and by `op:method` on a function held in a mapping ([ABIO Heads](ABIO%20Heads.md)). ^check-returned




# Access Semantics

## Why the receiver's type
Filtering attribute names alone does not hold a sandbox: any live framework object a head hands back is walkable by plain names. Before `5c08bc8`, `q.env.standard(trusted=True).load(...)` on a quoted form minted a trusted environment from an untrusted spec and ran `!py os.system` (T091 AG1). So the decision keys on what the value is, not on what the name looks like, and it holds under trust too: a trusted spec reaches Python through `!py` and `.py` includes explicitly, never by walking attributes.



## The three receiver classes
- **Plain data** — attributes and methods; `op:method` still refuses the in-place methods and charges a bound before calling.
- **Domain values** — the frozen records heads hand back; data attributes only. A method of one is Python API, not language.
- **Everything else** — refused with one error naming the type: `Env`, `Ctx`, `Registry`, `Head`, `QuotedForm`, `Seed`, modules, classes, functions, bound methods, numpy scalars.

A name beginning with `_` is refused on every receiver, so private state (`QuotedForm._env`) is not an interface; Python code reads that one through `closure_env` ([ABIO Interp](ABIO%20Interp.md)).



## Bound callables
A callable reaches a call position three ways: a `!py` object or an included module's function bound in scope (`Env.head` → `_callable_head`), and a function held under a key of a mapping (`op:method` on an included module's namespace). Each passes `check_callable` under the environment's trust. An untrusted spec cannot `!py` or include `.py` at all, so every callable it could reach arrived as a value — a constraint predicate, an agent factory — and `check_callable` refuses them all; it calls registered heads and templates only. A rule admitting plain functions (the one before `d943ce4`) would admit whatever a future head leaks.



## Denied modules and allowed code
The receiver-type rule stops attribute walking; it does not stop a trusted spec naming framework code directly. `!py alienbio.expr.include.run_python_file` passed the import-root rule (it lives under `alienbio`) and ran any `.py` on disk (T091 AL3); a by-function deny list then missed `report.example_rows` and the file writers (T091 AP2). So the rule is by module and has two halves. **Denied modules** refuse every name in a module that loads a spec, runs an experiment or pytest, writes files, reads keys or calls the network, at every door a trusted spec has: each `!py` step ([ABIO Include](ABIO%20Include.md) § `resolve_py`), each name read off an included helper (`HelperNamespace`), `check_callable`, and a helper's return value — a partial or bound method judged by what it wraps. **Allowed code**: a `!py` reference into `alienbio` that lands on a function or class must be a registered head's function or live in `PY_ALLOWED_MODULES`; everything else a spec needs is a head. `check_reference` adds the value rule at the same doors: a reference yields a callable, plain data or a domain value — never a module, a `Path`, a `Registry` or an `Env`.

A spec's own included helpers are the helper author's code and trusted as such — a helper may import `subprocess` itself. The rule keeps a YAML-only trusted spec from reaching side effects, and `check_returned` keeps a helper's imports from leaking through it by reference.




# BRIEF
- 2026-10-30 — written as an ABIO module doc from the source at alienbio HEAD `76fa1d6` (read with `git show`); the module landed at `5c08bc8` (T091 AG1), with `5e7cd03` (AG2) restoring the `!py` import roots beside it and `5d578ec` (AH) charging the methods it admits. A concurrent worker (round AN) is editing `src/alienbio/expr/` — anything AN adds (a deny set) is not on this page yet.
- 2026-10-30 — refreshed for `d943ce4` (T091 AL3, AL8): `DENIED_ENTRY_POINTS`, `denied_entry_point` and `check_reference` (new); `check_callable` refuses every bound callable untrusted and a denied entry point trusted. Figure's `check_callable` legs relabelled.
- 2026-10-30 — refreshed for `df0bc6c` (T091 AP1, AP2): `DENIED_ENTRY_POINTS` is seventeen whole modules; `PY_ALLOWED_MODULES`, `allowed_framework_code` and `check_returned` (new); `denied_entry_point` unwraps partials and bound methods and judges only modules, classes and callables; § Denied entry points → § Denied modules and allowed code. Figure's trusted leg names the deny list and the allow-list. (`c0094c7` does not touch this module.)
