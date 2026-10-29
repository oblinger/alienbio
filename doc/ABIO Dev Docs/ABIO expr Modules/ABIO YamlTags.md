---
description: "`yaml_tags`: the structural spelling of Expr — `ExprLoader`, a `yaml.SafeLoader` subclass whose tag constructors turn `!x` into a parsed form, `!q` into `Quoted`, `!ref` into `Name`, `!include`/`!py` into load-time nodes and any other `!head` into a `Call`; `load_text`; and `dump_structural`, the `ExprDumper` that writes forms back as tagged YAML. Source: `src/alienbio/expr/yaml_tags.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO expr Modules](ABIO%20expr%20Modules.md) → [ABIO YamlTags](ha://p/ABIO%20YamlTags) 
# ABIO YamlTags
The page for how YAML text becomes Expr forms and back: what each tag constructs, how a tag's node shape (mapping, sequence, scalar) decides the call's arguments, which tags are reserved or retired, and where the writer does not reproduce what the reader reads.

![ABIO YamlTags](ABIO%20YamlTags.svg) 
*Tags to forms* is the topic behind the five constructors; *Round trip* governs the dotted return edge, which refuses a keyword named `args` (‡).

`yaml_tags.py` sits at the bottom of the load: `Env.load` calls `load_text` before it resolves includes ([ABIO Env](ABIO%20Env.md), [ABIO Include](ABIO%20Include.md)), the `!x` and `!q` scalars are parsed by [ABIO Parse](ABIO%20Parse.md), and every node it builds is one of [ABIO Form](ABIO%20Form.md)'s shapes. Nothing here evaluates or checks that a head exists; that is [ABIO Interp](ABIO%20Interp.md) and [ABIO Registry](ABIO%20Registry.md). `X.load` and `X.dump(style="structural")` are the Python entry points. The experiment file's own writer, `spec_to_text`, is separate ([ABIO ExprExperiment](../ABIO%20suite/ABIO%20ExprExperiment.md)). The spelling as a user writes it is [ABIO Expr Spec](../../ABIO%20Guides/ABIO%20Expr%20Spec.md).



## ExprLoader Interface
`yaml.SafeLoader` plus the Expr tags, as a subclass so the global `SafeLoader` and every other loader in the process are untouched. It adds constructors and no methods.

| ExprLoader | |
| --- | --- |
| [!x](#^x) | Inline text, parsed |
| [!q](#^q) | A quoted form |
| [!ref](#^ref) | A name lookup |
| [!include](#^include) | A load-time include |
| [!py](#^py) | A load-time Python reference |
| [!head](#^head) | Any other tag: a call |

**!x**` <scalar>`
    `parse(text)`; a mapping or sequence node refuses. ^x

**!q**` <scalar | node>`
    A scalar is parsed and quoted; a mapping or sequence is constructed as data and quoted. ^q

**!ref**` <scalar>`
    `Name(text)`; any other node refuses. ^ref

**!include**` <scalar>`
    `Include(path)`. ^include

**!py**` <scalar>`
    `PyRef(path)`. ^py

**!head**` <mapping | sequence | scalar>`
    The multi-constructor for every other tag: `Call(head, ...)`; § [Tags to forms](#tags-to-forms). Refuses a retired spelling (naming its replacement), a reserved tag, and a head that is not identifiers joined by `.` or `:`. ^head



## yaml_tags Interface
The reader, the writer and their tables.

| yaml_tags | |
| --- | --- |
| [RESERVED_TAGS](#^reserved-tags) | Tags no head may take |
| [LEGACY_TAGS](#^legacy-tags) | Retired spellings and their replacements |
| [load_text](#^load-text) | YAML text to forms |
| [ExprDumper](#^exprdumper) | `SafeDumper` with representers for the forms |
| [dump_structural](#^dump-structural) | Forms to YAML text |

**RESERVED_TAGS**` = {"x", "q", "ref", "include", "py"}`
    Constructed by their own constructors; `!x` written as a head would be read by its constructor first, and the multi-constructor refuses the names outright. ^reserved-tags

**LEGACY_TAGS**` = {"ev": "!x", "_": "!q", "quote": "!q"}`
    The M1 spellings, each a load error that names its replacement (M47.7: no aliases survive). ^legacy-tags

**load_text**`(text: str) -> Any`
    `yaml.load(text, Loader=ExprLoader)`: untagged YAML is data, tagged nodes are forms. A `yaml.YAMLError` becomes `ExprError("YAML error: …")`, and a `RecursionError` (PyYAML composes recursively, so a deeply nested document overflows before any Expr limit sees it) becomes `ExprError("YAML nesting deeper than limits.depth allows …")` (since `dc92971`, T091 C11); a constructor's `ExprError` carries `line N`. Includes are not resolved. ^load-text

**ExprDumper** (class)
    A `yaml.SafeDumper` with representers for `Call` (`!head` with a flow mapping, a flow sequence, or one scalar), `Name` (`!ref path`) and `Quoted` (`!q "<inline text>"`, always double-quoted so commas and braces survive a flow context). ^exprdumper

**dump_structural**`(form) -> str`
    `yaml.dump` with `ExprDumper`, keys in insertion order, flow style chosen by the dumper. § [Round trip](#round-trip). ^dump-structural




# YamlTags Semantics

## Tags to forms
A `!head` tag's node shape decides the arguments:

| Written | Form |
| --- | --- |
| `!f {a: 1, b: 2}` | `Call("f", (), {"a": 1, "b": 2})` |
| `!f {args: [1, 2], k: 3}` | `Call("f", (1, 2), {"k": 3})` — `args` is reserved for positionals |
| `!f [1, 2]` | `Call("f", (1, 2))` |
| `!f 3` | `Call("f", (3,))` — the scalar takes YAML's implicit type |
| `!f "3"` | `Call("f", ("3",))` — a quoted scalar is a string |
| `!f` or `!f ""` | `Call("f")` — no arguments |
| `!x a + 1` | `op:add(Name("a"), 1)` |
| `!q lognormal(1, 0.3)` | `Quoted(lognormal(1, 0.3))` |
| `!ref a.b` | `Name("a.b")` |

Mapping keyword names must be identifiers. Keys and values inside a tagged node are constructed deep, so nested tags inside a call's arguments are forms too. An untagged mapping is plain data even when it carries `_type:`; the interpreter, not the loader, reads that as a call.



## Round trip
`dump_structural` promises text that loads back to an equal form. It does for names, calls with keyword arguments, calls with several positionals, calls with a lone positional of any type, and plain data; a quote round-trips whenever its form is one `dump` writes back as inline text ([ABIO Parse](ABIO%20Parse.md) § What dump can write back), comprehensions and set literals included. The exceptions (‡):

| Form | Written | Read back |
| --- | --- | --- |
| `Call("h", (), {"args": [1]})` | nothing: `ExprError` | — the mapping form reads `args` as the positionals |
| a `Quoted` hand-built `each(as=…)` or bare `op:flatten` | `!q "each(over=xs, as='x', …)"` | refused at load |

A lone non-empty string positional is written as a double-quoted tagged scalar (`!h "a"`); any other lone positional — a number, a bool, `""` — as a one-element flow sequence (`!poisson [3]`), so it reads back with its type, where a tagged scalar would come back a string or, empty, as no argument.




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084) from the source at alienbio HEAD `c67f052` (read with `git show`). Run against an export of that tree: every row of the round-trip table was dumped and reloaded, and `evaluate` of the reloaded `poisson('3')` raised `must be real number, not str`; `!ev 1` refuses naming `!x`. Not determined: whether any production path calls `dump_structural` (the experiment writer `spec_to_text` does not; `X.dump` does). Findings filed on T088.
- 2026-10-28 — refreshed against `0eb23e5`: a lone non-string or empty-string positional dumps as a one-element flow sequence and round-trips, a keyword named `args` refuses to dump, and quoted comprehensions survive (`c90ce0d`); round-trip table and figure ‡ note rewritten.
- 2026-10-29 — refreshed for `dc92971` (T091 C11): `load_text` turns a `RecursionError` into an `ExprError`. Figure still true.
