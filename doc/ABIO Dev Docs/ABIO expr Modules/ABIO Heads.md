---
description: "`heads`: the Expr builtin heads registered at import — the seven distribution draws and `constant`, the plain math and conversion builtins, the metered sized builtins (`range`, `list`, `sorted`, `reversed`, `zip`, `sum`, `max`, `min`), the `op:*` heads the inline parser emits (with the metered `add`, `mul`, `pow`, `mod`, `flatten`, `method`, `fstr`, `fmt`), and the two generic guards `nonempty` and `max_size`. Source: `src/alienbio/expr/heads.py`, draws from `src/alienbio/spec_lang/builtins.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO expr Modules](ABIO%20expr%20Modules.md) → [ABIO Heads](ha://p/ABIO%20Heads) 
# ABIO Heads
The page for every head a spec can call without registering anything: what each family returns, which ones charge the allocation meter before they build, and which ones need no charge.

![ABIO Heads](ABIO%20Heads.svg) 
*The meter's coverage* is the topic behind the split between the metered and unmetered columns (‡ marks the heads that charge nothing because they build no more than an input already charged); *Draws* governs the dotted `ctx.rng` edge.

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
| [pow](#^pow) | `op:pow`'s capped function by name |
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

**pow**`(base, exp, mod=None, *, ctx)`
    Without `mod`, `op:pow` itself, so `pow(3, 2000000)` refuses exactly as `3 ** 2000000` does; with `mod`, Python's three-argument `pow`, whose result is bounded by `mod`. ^pow

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
| [op:sub, op:div, op:floordiv](#^op-arith) | The other arithmetic |
| [op:mod](#^op-mod) | `a % b`, a %-format charged its bound |
| [op:neg, op:pos, op:not](#^op-unary) | Prefix operators |
| [op:eq … op:isnot](#^op-cmp) | The ten comparisons |
| [op:set](#^op-set) | `set(xs)` |
| [op:flatten](#^op-flatten) | One level of flattening, charged |
| [op:slice](#^op-slice) | A `slice` object |
| [op:item](#^op-item) | `obj[index]` |
| [op:attr](#^op-attr) | A checked attribute or mapping key |
| [op:method](#^op-method) | A checked, non-mutating method call, charged |
| [op:fstr](#^op-fstr) | Concatenate f-string parts, charged |
| [op:fmt](#^op-fmt) | One formatted field, its width charged |

**op:add**`(a, b, *, ctx)`
    Charges the summed length of string, list and tuple operands before adding. ^op-add

**op:mul**`(a, b, *, ctx)`
    When one side is a sequence and the other an `int`, charges `len(seq) * n` before multiplying. ^op-mul

**op:pow**`(a, b, *, ctx)`
    Refuses an integer exponent above `MAX_INT_EXPONENT` in magnitude (unless the base is 0, 1, -1 or a bool), and an integer result estimated over `MAX_POW_RESULT_BITS` (`a.bit_length() * b`); converts a float `OverflowError` to `ExprError`. ^op-pow

**op:sub, op:div, op:floordiv**`(a, b)`
    Plain lambdas; none can build more than its operands. ^op-arith

**op:mod**`(a, b, *, ctx)`
    On a `str` or `bytes` left operand (printf formatting), first charges the format's length, every digit run in it read as a width or precision, a `*` width's integer argument, and the text of every interpolated argument — ten times over when the format holds a `%r` or `%a` conversion, in any spelling Python accepts — the mapping form `%(key)r`, flags, width and precision, and the ignored length modifiers `h`/`l`/`L` (`%(k)la`, `%ha`, `%lr`), matched by `_REPR_CONVERSION` = `%(?:\([^)]*\))?[^a-zA-Z%]*[hlL]?[ra]` — since a repr writes up to ten characters per character — so `'%050000000d' % 1` refuses; a number is plain `%`. ^op-mod

**op:neg, op:pos, op:not**`(a)`
    `-a`, `+a`, `not a`. ^op-unary

**op:eq, op:ne, op:lt, op:le, op:gt, op:ge, op:in, op:notin, op:is, op:isnot**`(a, b)`
    The comparison operators; a chain is joined by `op:and` at parse time. ^op-cmp

**op:set**`(xs) -> set`
    `set(xs)`, not charged. ^op-set

**op:flatten**`(xss, *, ctx) -> list`
    Charges the summed length of the sized rows, then flattens one level; an unsized row is charged by its count once materialized. ^op-flatten

**op:slice**`(lo=None, hi=None, step=None) -> slice`
    Used inside `op:item`. ^op-slice

**op:item**`(obj, index, *, env)`
    `obj[index]`; a `KeyError`, `IndexError` or `TypeError` becomes an `ExprError` naming the subscript. ^op-item

**op:attr**`(obj, name: str, *, env)`
    Refuses a name the sandbox denies (dunders, `format`, `format_map`, `mro`, `subclasses`, frame and code prefixes, and any name starting with `_`); a mapping holding the key returns the value; otherwise the receiver's type decides ([ABIO Access](ABIO%20Access.md)): plain data returns the attribute but refuses a method read as a value (call it), a domain record returns a data attribute and refuses a method, and every other type — `Env`, `QuotedForm`, a seed, a module, a class, a function — refuses, under trust too. ^op-attr

**op:method**`(obj, name: str, *args, env, **kwargs)`
    Refuses an in-place method (`append`, `extend`, `insert`, `remove`, `pop`, `clear`, `sort`, `reverse`, `update`, `setdefault`, `popitem`, `add`, `discard`, the `*_update` set methods) on a list, dict, set or bytearray, since a binding is shared by every node naming it; then checks the name, and resolves the target: a callable held under that key in a mapping must pass `check_callable` (untrusted: a plain Python function only), anything else is a method of a plain-data receiver — a domain record's methods and every other type's refuse. It refuses a non-callable, and charges a bound before calling: on text, the padding target for `ljust`/`rjust`/`center`/`zfill`, `len × tabsize` for `expandtabs`, the joined length for `join`, the worst case for `replace`, `n ×` the longest string value in the table for `translate` (a table that is neither a mapping nor a list refuses), `3n` for the case methods (`upper`, `lower`, `casefold`, `title`, `swapcase`, `capitalize`: `'ﬃ'.upper()` is three characters), `10n` for `encode` (`100n` with `namereplace`), `4n` for `decode`, `n × (2 + separator)` for `hex`, else the receiver plus its text arguments; on an int, `n` for `to_bytes(n)` (so `(1).to_bytes(10**9, 'big')` refuses) and nothing for its other methods, nor for a float's or complex's; on a container, its length plus every sized argument (`fromkeys`, `union`, …). ^op-method

**op:fstr**`(*parts, ctx) -> str`
    Charges the summed length of `str(p)` for each part, then joins. ^op-fstr

**op:fmt**`(value, spec="", conv="", *, ctx) -> str`
    Charges every digit run in `spec` as a width, then applies the `!r`/`!s`/`!a` conversion and `format(value, spec)`; `op:fstr` charges the joined text. ^op-fmt



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
A distribution head declares `ctx` and so receives the node's context; `ctx.rng` builds a fresh generator from the node's seed on every read. Two draws at different paths are independent and two draws at one path are equal; a chained comparison binds a drawn middle operand once ([ABIO Parse](ABIO%20Parse.md)), so both comparisons read one sample.



## The meter's coverage
`limits.entities` (one million by default) bounds one producer and the running total of a session. The heads split three ways:

| Behaviour | Heads |
| --- | --- |
| Charged before building | `range`, `list`, `sorted`, `reversed`, `zip`, `sum`, `max`, `min` (sized inputs), `op:add`, `op:mul`, `op:flatten`, `op:fstr`, `op:fmt` widths, `op:mod` on text, `op:method` |
| Bounded otherwise | `op:pow` and `pow` by name (exponent and result bits) |
| Not charged (‡) | `op:set`, `str`, `int`, `dict` |
| Refused by name | `str.format` / `format_map` (a format field walks attributes outside the allowlist — use an f-string), the in-place methods; `bytes` / `bytearray` are not heads |

M48.5 and T051 box 4 closed the first rows' original members; T088 (`c90ce0d`) added `pow` by name, `op:mod`, `op:method` and the `op:fmt` width, and moved `op:flatten`/`op:fstr` ahead of the build; T091 AH (`5d578ec`) added `int.to_bytes` and a container method's sized arguments. The `heads.py` module docstring carries the full charge table. The third row builds no more than an input that was already charged.




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084) from the source at alienbio HEAD `c67f052` (read with `git show`). Run against an export of that tree: `pow(3, 2000000)` returned a 3,169,926-bit integer in 0.26 s where `3 ** 2000000` refused; `'%050000000d' % 1` and `'a'.ljust(50000000)` each returned 50 million characters under the default cap; `b: !x a.clear()` emptied the mapping bound at `a`. Not run: the large `op:fmt` width (the order is read from the code). Findings filed on T088.
- 2026-10-28 — refreshed against `0eb23e5`: `pow` by name is `op:pow`'s capped function, `op:mod` on text, `op:fmt` widths and `op:method` charge a bound before they build, in-place methods refuse, `op:flatten`/`op:fstr` charge before the join (`c90ce0d`); new `op:mod` block, the meter table and the figure's unmetered box rewritten.
- 2026-10-29 — refreshed for `dc92971` (T091 C4) and `db300c9` (F6): `op:method` bounds `translate` by the table's longest value, the case methods at 3n, `encode` at 10n (100n with `namereplace`), `decode` at 4n and `hex`, so a 27-million-character `translate` refuses; `op:mod` charges 10× for `%r`/`%a`, the `%(key)` forms included. Figure still true.
- 2026-10-30 — refreshed for `5c08bc8` (T091 AG1) and `5d578ec` (AH): `op:attr` and `op:method` judge the receiver's type through [ABIO Access](ABIO%20Access.md) — methods only on plain data, a mapping-held callable through `check_callable`; `int.to_bytes(n)` charges `n` and a container method its sized arguments before it runs; `str.format`/`format_map` refused by name. Figure still true.
- 2026-10-29 — refreshed for `fab20be` (T091 K F6): `op:mod`'s repr charge also catches the `h`/`l`/`L` length modifiers (`%la`, `%hr`).
