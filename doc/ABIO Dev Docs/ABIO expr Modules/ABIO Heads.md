---
description: "`heads`: the Expr builtin heads registered at import — the seven distribution draws and `constant`, the plain math and conversion builtins, the metered sized builtins (`range`, `list`, `sorted`, `reversed`, `zip`, `sum`, `max`, `min`), the `op:*` heads the inline parser emits (with the metered `add`, `mul`, `pow`, `flatten`, `fstr`), and the two generic guards `nonempty` and `max_size`. Source: `src/alienbio/expr/heads.py`, draws from `src/alienbio/spec_lang/builtins.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO expr Modules](ABIO%20expr%20Modules.md) → [ABIO Heads](ha://p/ABIO%20Heads) 
# ABIO Heads
The page for every head a spec can call without registering anything: what each family returns, which ones charge the allocation meter before they build, and which ones do not.

![ABIO Heads](ABIO%20Heads.svg) 
*The meter's coverage* is the topic behind the split between the metered and unmetered columns (‡ marks the heads that build unbounded output with no charge); *Draws* governs the dotted `ctx.rng` edge.

`heads.py` only registers; the table is [ABIO Registry](ABIO%20Registry.md), the meter and its caps are `Limits` in [ABIO Env](ABIO%20Env.md), and the `op:*` names are what [ABIO Parse](ABIO%20Parse.md) emits for operators, subscripts, attributes, method calls and f-strings. `op:and`, `op:or` and the other special forms are not here; they are the interpreter's ([ABIO Interp](ABIO%20Interp.md)). The draw functions themselves live in `spec_lang/builtins.py`. The rate compiler sees this module's `math`, `op` and `dist` heads through a registry view ([ABIO RateLaw](../ABIO%20suite/ABIO%20RateLaw.md)). The head catalog as a user reads it is in [ABIO Expr Spec](../../ABIO%20Guides/ABIO%20Expr%20Spec.md).



## Distribution heads
Kind `dist`. Each draws once from `ctx.rng`, a generator built from the node's own seed, so a draw depends only on the root seed and the node's path. Evaluated, a draw is a number; to pass the distribution itself, quote it (`!q lognormal(1, 0.3)`).

| Distribution heads | |
| --- | --- |
| [normal](#^normal) | Gaussian draw |
| [uniform](#^uniform) | Uniform draw on an interval |
| [lognormal](#^lognormal) | Log-normal draw |
| [poisson](#^poisson) | Poisson count |
| [exponential](#^exponential) | Exponential draw |
| [choice](#^choice) | One element, uniformly |
| [discrete](#^discrete) | An index, by weight |
| [constant](#^constant) | Always its argument |

**normal**`(mean, std, *, ctx) -> float`
    `ctx.rng.normal(mean, std)`. ^normal

**uniform**`(low, high, *, ctx) -> float`
    `ctx.rng.uniform(low, high)`. ^uniform

**lognormal**`(mean, sigma, *, ctx) -> float`
    `ctx.rng.lognormal(mean, sigma)`; `mean` and `sigma` are of the underlying normal. ^lognormal

**poisson**`(lam, *, ctx) -> int`
    `ctx.rng.poisson(lam)`. ^poisson

**exponential**`(scale, *, ctx) -> float`
    `ctx.rng.exponential(scale)`; `scale` is the mean. ^exponential

**choice**`(options: list, *, ctx) -> Any`
    `options[rng.integers(0, len(options))]`. ^choice

**discrete**`(weights: list[float], *, ctx) -> int`
    An index drawn with probability proportional to its weight; the weights are normalized by their sum. ^discrete

**constant**`(value) -> Any`
    The value unchanged; the degenerate distribution, so a dial can be a draw or a fixed number with one spelling. ^constant



## Math heads
Kind `math`. Thin registrations of Python builtins; arguments arrive evaluated.

| Math heads | |
| --- | --- |
| [abs, round, sqrt, exp, log, len, int, float, str, bool, dict, all, any](#^plain-math) | The Python builtins of those names |
| [pow](#^pow) | Python's `pow`, unmetered ‡ |
| [range](#^range) | A list, charged by length |
| [list](#^list) | A list, charged by length |
| [sorted](#^sorted) | Sorted list, charged |
| [reversed](#^reversed) | Reversed list, charged |
| [zip](#^zip) | List of lists, each input charged |
| [sum](#^sum) | Sum, charged by input and by list output |
| [max](#^max) | Maximum, sized inputs charged |
| [min](#^min) | Minimum, sized inputs charged |

**abs, round, sqrt, exp, log, len, int, float, str, bool, dict, all, any**
    The builtins (and `math.sqrt`, `math.exp`, `math.log`) registered under their names. A `TypeError` they raise becomes an `ExprError`; any other exception (`exp(1000)`'s `OverflowError`, `log(0)`'s `ValueError`) propagates as raised. ^plain-math

**pow**`(base, exp, mod=None)`
    The builtin, registered under `pow` with no bound: `pow(3, 2000000)` builds a 3.2-million-bit integer where `3 ** 2000000` refuses (§ [The meter's coverage](#the-meters-coverage)). ^pow

**range**`(*a, ctx) -> list`
    `list(range(*a))`, charged by its length before the list is built. ^range

**list**`(x=(), *, ctx) -> list`
    `list(x)`, charged by `len(x)` when `x` is sized and not a string. ^list

**sorted**`(x, *, ctx, key=None, reverse=False) -> list`
    Charged as `list`. ^sorted

**reversed**`(x, *, ctx) -> list`
    Charged as `list`; returns a list, not an iterator. ^reversed

**zip**`(*a, ctx) -> list[list]`
    Each sized input charged; rows are lists. ^zip

**sum**`(x, start=0, *, ctx) -> Any`
    When `x` is a list or tuple, first charges the total length of its string, list and tuple items (a sum of lists is sized by its output and built quadratically), then charges `x` itself and sums. ^sum

**max**`(*a, ctx, **kw) -> Any`
    Each sized positional argument charged, then `max`. ^max

**min**`(*a, ctx, **kw) -> Any`
    As `max`. ^min



## Operator heads
Kind `op`. What the inline parser emits; a structural spec may call them by name (`!op:add [1, 2]`).

| Operator heads | |
| --- | --- |
| [op:add](#^op-add) | `a + b`, charged by sized operands |
| [op:mul](#^op-mul) | `a * b`, a repeated sequence charged |
| [op:pow](#^op-pow) | `a ** b`, exponent and result bounded |
| [op:sub, op:div, op:floordiv, op:mod](#^op-arith) | The other arithmetic, unmetered ‡ |
| [op:neg, op:pos, op:not](#^op-unary) | Prefix operators |
| [op:eq … op:isnot](#^op-cmp) | The ten comparisons |
| [op:set](#^op-set) | `set(xs)` |
| [op:flatten](#^op-flatten) | One level of flattening, charged |
| [op:slice](#^op-slice) | A `slice` object |
| [op:item](#^op-item) | `obj[index]` |
| [op:attr](#^op-attr) | A checked attribute or mapping key |
| [op:method](#^op-method) | A checked method call, unmetered ‡ |
| [op:fstr](#^op-fstr) | Concatenate f-string parts, charged |
| [op:fmt](#^op-fmt) | One formatted field |

**op:add**`(a, b, *, ctx)`
    Charges the summed length of string, list and tuple operands before adding. ^op-add

**op:mul**`(a, b, *, ctx)`
    When one side is a sequence and the other an `int`, charges `len(seq) * n` before multiplying. ^op-mul

**op:pow**`(a, b, *, ctx)`
    Refuses an integer exponent above `MAX_INT_EXPONENT` in magnitude (unless the base is 0, 1, -1 or a bool), and an integer result estimated over `MAX_POW_RESULT_BITS` (`a.bit_length() * b`); converts a float `OverflowError` to `ExprError`. ^op-pow

**op:sub, op:div, op:floordiv, op:mod**`(a, b)`
    Plain lambdas. `op:mod` on a string is printf formatting, so `'%050000000d' % 1` builds a 50-million-character string with no charge. ^op-arith

**op:neg, op:pos, op:not**`(a)`
    `-a`, `+a`, `not a`. ^op-unary

**op:eq, op:ne, op:lt, op:le, op:gt, op:ge, op:in, op:notin, op:is, op:isnot**`(a, b)`
    The comparison operators; a chain is joined by `op:and` at parse time. ^op-cmp

**op:set**`(xs) -> set`
    `set(xs)`, not charged. ^op-set

**op:flatten**`(xss, *, ctx) -> list`
    Flattens one level, then charges the result's length (after it is built). ^op-flatten

**op:slice**`(lo=None, hi=None, step=None) -> slice`
    Used inside `op:item`. ^op-slice

**op:item**`(obj, index, *, env)`
    `obj[index]`; a `KeyError`, `IndexError` or `TypeError` becomes an `ExprError` naming the subscript. ^op-item

**op:attr**`(obj, name: str, *, env)`
    Refuses a name the sandbox denies (dunders, `format`, `format_map`, `mro`, `subclasses`, frame and code prefixes); a mapping holding the key returns the value, else `getattr`. ^op-attr

**op:method**`(obj, name: str, *args, env, **kwargs)`
    `op:attr`, then refuses a non-callable, then calls it. Nothing is charged and nothing restricts which methods: `'a'.ljust(50000000)` builds 50 million characters, and `a.clear()` empties the mapping bound at `a` for every later reader. ^op-method

**op:fstr**`(*parts, ctx) -> str`
    Joins `str(p)` for each part, then charges the result's length. ^op-fstr

**op:fmt**`(value, spec="", conv="") -> str`
    Applies the `!r`/`!s`/`!a` conversion, then `format(value, spec)`; a width in `spec` is built before `op:fstr` charges the joined string. ^op-fmt



## Guards
Kind `guard`; called as `fn(value, ctx, **params)` from a call's `guards:` list.

| Guards | |
| --- | --- |
| [nonempty](#^nonempty) | The value has length above zero |
| [max_size](#^max-size) | The value has at most `n` elements |

**nonempty**`(value, ctx) -> bool`
    `len(value) > 0`; an unsized value passes unless it is `None`. ^nonempty

**max_size**`(value, ctx, n: int = 1) -> bool`
    `len(value) <= n`; an unsized value passes. ^max-size



## heads Interface
The module's exports beyond its registrations.

| heads | |
| --- | --- |
| [MAX_INT_EXPONENT](#^max-int-exponent) | `op:pow`'s exponent cap |
| [MAX_POW_RESULT_BITS](#^max-pow-result-bits) | `op:pow`'s result-size cap |
| [flatten_iter](#^flatten-iter) | Unmetered one-level flatten |

**MAX_INT_EXPONENT**` = 10_000`
    The largest integer exponent `op:pow` takes (M48.5: `10 ** 10 ** 10`). ^max-int-exponent

**MAX_POW_RESULT_BITS**` = 1 << 24`
    The largest estimated result `op:pow` builds (T051 box 4: `(10 ** 10000) ** 10000` was within the exponent cap and ~15 minutes of one core). ^max-pow-result-bits

**flatten_iter**`(xs) -> list`
    A plain Python helper, not a head. ^flatten-iter




# Heads Semantics

## Draws
A distribution head declares `ctx` and so receives the node's context; `ctx.rng` builds a fresh generator from the node's seed on every read. Two draws at different paths are independent and two draws at one path are equal, which is why a chained comparison that repeats a draw ([ABIO Parse](ABIO%20Parse.md)) compares two different samples: the copies sit at different paths.



## The meter's coverage
`limits.entities` (one million by default) bounds one producer and the running total of a session. The heads split three ways:

| Behaviour | Heads |
| --- | --- |
| Charged before building | `range`, `list`, `sorted`, `reversed`, `zip`, `sum`, `max`, `min` (sized inputs), `op:add`, `op:mul` |
| Charged after building | `op:flatten`, `op:fstr` (and so every `op:fmt` field inside it) |
| Bounded otherwise | `op:pow` (exponent and result bits) |
| Not charged (‡) | `pow`, `op:mod` on a string, `op:method`, `op:fmt` widths, `op:set`, `str`, `int`, `dict` |

The first row is what M48.5 and T051 box 4 closed; the last row is what an untrusted spec can still use to build an unbounded value. `pow` is the same operation `op:pow` bounds, reached by name.




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084) from the source at alienbio HEAD `c67f052` (read with `git show`). Run against an export of that tree: `pow(3, 2000000)` returned a 3,169,926-bit integer in 0.26 s where `3 ** 2000000` refused; `'%050000000d' % 1` and `'a'.ljust(50000000)` each returned 50 million characters under the default cap; `b: !x a.clear()` emptied the mapping bound at `a`. Not run: the large `op:fmt` width (the order is read from the code). Findings filed on T088.
