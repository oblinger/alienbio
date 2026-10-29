---
description: "`rate_law`: the compiled tier of Expr — `compile_rate` turns a `rate:` slot (a number, a `Dist`, or a quoted form in the rate grammar) into a `RateLaw`, either the product form `k × modulations` (`hill`, `michaelis`, `activator`, `inhibitor` over non-consumed modifier pools) or a `bio.rate_expr` tree both simulators evaluate; `ModulationSpec`; the four rate heads as plain functions; the registry view a rate law sees. Source: `src/alienbio/suite/rate_law.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO suite](ABIO%20suite.md) → [ABIO RateLaw](ha://p/ABIO%20RateLaw) 
# ABIO RateLaw
The page for what a `rate:` slot may say and what it becomes: the product form the engine has always run, the general expression it falls back to, how a bare name is told apart as a constant or a pool, and which draws are made when.

![ABIO RateLaw](ABIO%20RateLaw.svg) 
*Two shapes* is the topic behind the fork after `_compile_product` (the expression path runs only when the product form refuses); *Names: constant or pool* governs the `Name` edges (‡ marks where a misspelled parameter silently becomes a pool).

A rate law is not run by the interpreter: `compile_rate` reads the quoted form once, at world build, and the engine evaluates the result every step. The caller is the `reaction` block head ([ABIO ExprHeads](ABIO%20ExprHeads.md)), whose `RateLawBlock` realizes a law into a `ReactionImpl` with `Modulation` modifiers or a `rate_law` tree ([ABIO ReactionImpl](../ABIO%20bio/ABIO%20ReactionImpl.md)); the tree grammar and its evaluation on both simulators are [ABIO RateExpr](../ABIO%20bio/ABIO%20RateExpr.md). Constants are evaluated through a narrowed registry ([ABIO Registry](../ABIO%20expr%20Modules/ABIO%20Registry.md) § Views) with the builtin `math`, `op` and `dist` heads of [ABIO Heads](../ABIO%20expr%20Modules/ABIO%20Heads.md); quoted forms close over their environment as `QuotedForm` ([ABIO Interp](../ABIO%20expr%20Modules/ABIO%20Interp.md)). The grammar as a user writes it is in [ABIO Expr Spec](../../ABIO%20Guides/ABIO%20Expr%20Spec.md).



## RateLaw Interface
A frozen dataclass: one compiled law.

| RateLaw | |
| --- | --- |
| [k](#^k) | The mass-action constant |
| [modulations](#^modulations) | Product-form modifier terms |
| [expr](#^expr) | The general expression, when set |
| [modifier_pools](#^modifier-pools) | Pools the modulations read |
| [expr_pools](#^expr-pools) | Pools the expression reads |
| [realize_expr](#^realize-expr) | The expression with its draws made |

**k**`: Dist[float]`
    A `Constant`, a `Dist`, a `QuotedForm` or a `_Scaled` Dist; drawn once per world. `Constant(1.0)` when the law is an expression. ^k

**modulations**`: tuple[ModulationSpec, ...] = ()`
    The product form's factors, each over a pool that is neither a reactant nor a product. ^modulations

**expr**`: Any = None`
    A `bio.rate_expr` tree over pool names, with `("dist", Dist)` leaves and `("mod", kind, pool, params)` nodes still to draw. When it names a reactant it is the whole rate; otherwise it is the factor on mass action. ^expr

**modifier_pools**`: tuple[str, ...]` (property)
    One per modulation, in order. ^modifier-pools

**expr_pools**`: tuple[str, ...]` (property)
    Every species the expression reads, sorted; empty for the product form. ^expr-pools

**realize_expr**`(seed: Seed) -> Any`
    The tree with each `dist` leaf and each Dist modulation parameter drawn under `seed.child("law<n>")`, `n` counting draws in walk order. ^realize-expr



## ModulationSpec Interface
A frozen dataclass: one product-form modulation before its parameters are drawn.

| ModulationSpec | |
| --- | --- |
| [pool](#^pool) | The modifier pool |
| [kind](#^kind) | `hill`, `michaelis`, `activator` or `inhibitor` |
| [params](#^params) | Parameter name to Dist |
| [sample](#^sample) | Draw the parameters into a `Modulation` |

**pool**`: str`
    Spelled through `Env.pool`. ^pool

**kind**`: str`
    One of the `MODULATION_HEADS`. ^kind

**params**`: Mapping[str, Dist[float]]`
    The kind's positional parameters and given extras, with the defaults filled in (`hill`: `n = 2`, `Vmax = 1`; `michaelis`: `Vmax = 1`). ^params

**sample**`(seed: Seed) -> Modulation`
    Each parameter drawn under `seed.child(name)`. ^sample



## Rate heads
Kind `rate`, registered as ordinary functions so `!x hill(0.5, 0.5, n=2)` is a number outside a rate slot; inside one, the compiler reads them as modulations instead of calling them.

| Rate heads | |
| --- | --- |
| [hill](#^hill) | `Vmax · mⁿ / (Kⁿ + mⁿ)` |
| [michaelis](#^michaelis) | `Vmax · m / (K + m)` |
| [activator](#^activator) | `1 + a · m` |
| [inhibitor](#^inhibitor) | `1 / (1 + m / Ki)`; `Ki = 0` is the perfect inhibitor |

**hill**`(m, K, n=2.0, Vmax=1.0) -> float`
    `0.0` when the denominator is not positive. Each of the four numeric heads is `bio.rate_expr.modulation_factor` itself, so `!x` arithmetic reads exactly as the compiled law both simulators run, zero-denominator conventions included. ^hill

**michaelis**`(m, K, Vmax=1.0) -> float`
    `0.0` when `K + m` is not positive. ^michaelis

**activator**`(m, a) -> float`
    Linear activation. ^activator

**inhibitor**`(m, Ki) -> float`
    Linear inhibition. `Ki = 0` is the perfect-inhibitor limit (`rate_expr.inhibitor_ratio`): factor `0.0` with any inhibitor present, `1.0` with none; it raised `ZeroDivisionError` before `64988be`. ^inhibitor



## rate_law Interface
The entry point and its tables.

| rate_law | |
| --- | --- |
| [MODULATION_HEADS](#^modulation-heads) | Kind to positional and keyword parameters |
| [RATE_VIEW_KINDS](#^rate-view-kinds) | The head kinds a rate law may call |
| [compile_rate](#^compile-rate) | A `rate:` value to a `RateLaw` |

**MODULATION_HEADS**`: Mapping[str, tuple[tuple[str, ...], tuple[str, ...]]]`
    `hill: (K; n, Vmax)`, `michaelis: (K; Vmax)`, `activator: (a; —)`, `inhibitor: (Ki; —)`; the pool is always the first argument. ^modulation-heads

**RATE_VIEW_KINDS**` = {"rate", "math", "op", "dist"}`
    The registry view the compiler resolves heads through; a world-building head, a drafter or a Python-only function is unknown inside a rate law. ^rate-view-kinds

**compile_rate**`(value, env, *, reactants=(), products=()) -> RateLaw`
    `None` → `k = 1`; a number → `Constant`, a negative one refused; a `Dist` → `k`; a `QuotedForm` → compiled in its own environment (§ [Two shapes](#two-shapes)); a bool or anything else refuses. `reactants` and `products` are the reaction's pool names as the block spelled them. ^compile-rate




# RateLaw Semantics

## Two shapes
`_compile_product` tries first. It flattens a chain of `*` and reads each factor: a modulation head over a pool that is neither consumed nor produced becomes a `ModulationSpec` (over a reactant or product it refuses: that is substrate-saturation kinetics); a bare name of a reactant or product sends the law to the expression path, where it is the whole rate when it names a reactant (T091 E4: `0.2 * A` over `A + B` read as `0.2·A·B` while `0.2 * A + 0.0` read as `0.2·A`; the two are now one number); anything else must be a constant — a literal, a bound number or Dist, a quote, `-x`, a product of constants, or a call of a `dist` or `math` head — and the constants multiply into `k`. Two refusals are made at load, naming the node (e.g. `sk.root.children.r.rate`), before either shape is tried (T091 E9): a product of two distributions anywhere in the law (the expression path would otherwise multiply the two draws), and a negative rate constant — a negative number, a product-form `k` or an expression product chain with a negative coefficient (it ran as rate 0; `-(-0.2)` folds to 0.2 first). If any factor is not of the product form (the typed `_NotProductForm`; an unbound name, which is a pool, raises it too), `_compile_expr` compiles the whole form instead: `+ - * / **`, `neg`, `exp`, `log`, `sqrt`, the modulation heads (now allowed over any pool), constants, and species. Any other refusal is final.

| Written | Compiles to |
| --- | --- |
| `2.0` | `RateLaw(k=2)` |
| `!q "2.0 * hill('M', 0.5)"` | product form: `k = 2`, one `hill` over `M` |
| `!q "Vmax * S / (Km + S)"` over reactant `S`, `Vmax` and `Km` bound | expression: the whole rate (unbound, both become pools) |
| `!q "0.1 + hill('M', 0.5)"` | expression: a factor on mass action |
| `!q "lognormal(0, 1) * lognormal(0, 1)"` | refused: a product of two distributions |
| `!q "0.2 * A"` over reactant `A` | expression: the whole rate `0.2·A` |
| `-0.2` | refused: a negative rate constant |



## Names: constant or pool
A bare name bound in scope is a constant (a number or a Dist); an unbound one is a pool, spelled through `Env.pool`; a quoted string is always a pool. A pool named like a bound variable must be quoted to mean the pool. One consequence follows (‡), and one former one is fixed:

- In the expression shape, an unbound name the author meant as a parameter becomes a pool: `3 * S / (Kmm + S)` with `Kmm` misspelled compiles, `Kmm` becomes an extra `IN` port and a molecule that starts at zero, and the rate reads `3 · S / S`.
- In the product shape, a bare reactant name is compared as the pool it denotes there (`Env.pool`), so inside a template instance the factor `S` in `2 * S * hill('M', 0.5)` matches the consumed `inst.S` and sends the law to the expression path, as outside one; before `64988be` it was compared as written and refused `unbound name 'S'`.



## Draws
A constant factor is a Dist, drawn once per world when the block realizes: `k` under the block's `rate` seed, each modulation parameter under `mod/<pool>/<name>`, each expression draw under `law/law<n>`. Expression draws are numbered in walk order, so inserting a term before an existing draw changes the seed every later draw sees.




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084) from the source at alienbio HEAD `afd519c` (read with `git show`; `rate_law.py` unchanged since `c67f052`). Run against an export of that tree: `2 * S * hill('M', 0.5)` compiled outside a template and refused `inst.rate: unbound name 'S'` inside one; `3 * S / (Kmm + S)` compiled with ports `S, P, Kmm`. Findings filed on T088.
- 2026-10-28 — refreshed against 0eb23e5 (`64988be`): the numeric heads are `rate_expr.modulation_factor` (`inhibitor(1, 0)` = 0.0), the product-form fallback is the typed `_NotProductForm`, a reactant named inside a template is read as its pool; figure legend follows.
- 2026-10-29 — refreshed for `cce3a04` (T091 E4, E9): a factor naming a reactant or product sends the law to the expression path (the whole rate when it names a reactant); a product of two distributions anywhere and a negative rate constant refuse at load, naming the node.
