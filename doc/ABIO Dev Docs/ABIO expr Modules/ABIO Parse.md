---
description: "`parse`: the inline spelling — `parse(text)` validates Python-expression text against the spec sandbox's AST allowlist and converts it to forms (names, calls, `op:*` operator calls, `each` for comprehensions, `if` for conditionals, `Quoted` for `quote(f)`); `dump(form)` writes a form back as inline text. Source: `src/alienbio/expr/parse.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO expr Modules](ABIO%20expr%20Modules.md) → [ABIO Parse](ha://p/ABIO%20Parse) 
# ABIO Parse
The page for the `!x` spelling of Expr: which Python expressions are accepted, the form each one becomes, and which forms `dump` can write back as text that parses to the same form.

![ABIO Parse](ABIO%20Parse.svg) 
*The sandbox check* is the topic behind `validate_expression`, the gate every text passes before conversion; *Text to forms* governs the `_convert` switch; *What dump can write back* governs the dotted return edge (‡ marks the forms that do not round-trip).

`parse.py` is text in, forms out, and nothing is evaluated here: the forms are [ABIO Form](ABIO%20Form.md), the operator heads they call are registered in [ABIO Heads](ABIO%20Heads.md), and `each`, `if`, `op:and` and `op:or` are special forms of [ABIO Interp](ABIO%20Interp.md). The structural loader calls `parse` for every `!x` and `!q` scalar and `dump` for every `Quoted` it writes ([ABIO YamlTags](ABIO%20YamlTags.md)); the Python spelling reaches both through `X.parse` and `X.dump`. The allowlist lives in `spec_lang/safe_eval.py`. The language as a user writes it is [ABIO Expr Spec](../../ABIO%20Guides/ABIO%20Expr%20Spec.md).



## parse Interface
Two functions.

| parse | |
| --- | --- |
| [parse](#^parse) | Inline text to a form |
| [dump](#^dump) | A form to inline text |

**parse**`(text: str, *, path: str = "") -> Any`
    Runs `validate_expression(text)`, then converts the expression body (§ [Text to forms](#text-to-forms)). Raises `ExprError` at `path` on a syntax error, on a construct outside the allowlist, on nesting deep enough to exhaust the parser, and on a construct the converter refuses (lambda, `**` unpacking, a non-literal dict key, a call whose target is neither a name nor an attribute, an async or destructuring comprehension). ^parse

**dump**`(form: Any) -> str`
    Writes a form as inline text: a name as its path, a `Quoted` as `quote(...)`, an operator call in its infix or prefix spelling with full parentheses, `if` as a conditional expression, an `op:fstr` as an f-string, any other call as `head(args, key=value)`, data as Python literals. § [What dump can write back](#what-dump-can-write-back). ^dump




# Parse Semantics

## The sandbox check
`validate_expression` parses the text in `eval` mode and walks every AST node against a fixed allowlist of node types, then checks names and attribute names: no dunder identifier or attribute, none of `getattr`, `eval`, `exec`, `open`, `__import__`, `type`, `format` and the rest of the denied names, no `format`/`format_map`/`mro`/`subclasses` attribute and no frame, generator or code-object attribute prefix, no `**` unpacking. Only then does `_convert` see the tree, so every form `parse` returns has passed it.



## Text to forms

| Python | Form |
| --- | --- |
| a constant | the Python value |
| `a`, `a.b.c` | `Name("a")`, `Name("a.b.c")` |
| `(f(x)).b` | `op:attr(f(x), "b")` |
| `[...]`, `(...)` | a list |
| `{...}` set | `op:set([...])` |
| `{k: v}` | a dict; keys must be literals |
| `a + b` and the other binary operators | `op:add(a, b)`, `sub`, `mul`, `div`, `floordiv`, `mod`, `pow` |
| `-a`, `+a`, `not a` | `op:neg`, `op:pos`, `op:not` |
| `a and b`, `a or b` | `op:and(a, b)`, `op:or(a, b)` (special, short-circuit) |
| `a < b`, `==`, `in`, `is`, … | `op:lt(a, b)`, `eq`, `in`, `is`, … |
| `a < b < c` | `op:and(op:lt(a, b), op:lt(b, c))` |
| `t if c else e` | `if(cond=c, then=t, else=e)` |
| `f"…{x:spec!r}…"` | `op:fstr("…", op:fmt(x, "spec", "r"), "…")` |
| `x[i]`, `x[a:b]` | `op:item(x, i)`, `op:item(x, op:slice(a, b, None))` |
| `f(a, k=v)` | `Call("f", (a,), {"k": v})` |
| `quote(f)` | `Quoted(f)`, when it has exactly one argument and no keywords |
| `a.b(x)` | `op:method(Name("a"), "b", x)` |
| a comprehension | `each(...)`; § [Comprehensions](#comprehensions) |

A chained comparison repeats its middle operand as a form, not as a value: `0 < f() < 2` evaluates `f()` twice, each under its own child seed, so a draw in the middle (`0 < normal(0, 1) < 1`) compares two different samples. A method-shaped call always becomes `op:method`, so the inline spelling cannot call a head whose name is dotted.



## Comprehensions
Each generator becomes one `each(over=, as=, body=)`, innermost wrapping the element; several `if` clauses on one generator are joined with `op:and` into `where=`. With more than one generator the outer `each` calls are wrapped in `op:flatten`, so a nested list comprehension is one flat list as in Python. A set comprehension is wrapped in `op:set`. A dict comprehension puts `key=` on the innermost `each` only and adds no flatten, so `{a*10+b: 1 for a in [1, 2] for b in [3, 4]}` evaluates to `[{13: 1, 14: 1}, {23: 1, 24: 1}]`, a list of dicts, where Python builds one dict. Targets must be a single name; tuple unpacking is refused.



## What dump can write back
`dump` re-parses to an equal form for names, data, quotes, infix and prefix operators, attribute, item and slice access, method calls, f-strings, conditionals and calls of plain-identifier heads. It does not for the forms whose head the inline spelling cannot type (‡ in the figure):

| Form | `dump` writes | Why it does not parse |
| --- | --- | --- |
| `each(...)` from a comprehension | `each(over=xs, as='x', body=…)` | `as` is a Python keyword |
| `op:set`, `op:flatten`, `op:fmt` outside an f-string | `op:set([1, 2])` | `:` is not an identifier character |
| a call of a dotted head | `a.b(...)` | it parses back as `op:method` |

A slice dumps with a trailing colon (`a[1:2:]`), which parses back to the same form.




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084) from the source at alienbio HEAD `c67f052` (read with `git show`). Run against an export of that tree: `dump(parse(t))` re-parses equal for slices, f-strings, methods, `-1`, conditionals and chained comparisons, and fails for a list comprehension and a set literal; a counting head in the middle of `0 < f() < 2` ran twice; the nested dict comprehension above returned a list of two dicts. Findings filed on T088.
