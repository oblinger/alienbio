---
description: "`yaml_tags`: the structural spelling of Expr — `ExprLoader`, a `yaml.SafeLoader` subclass whose tag constructors turn `!x` into a parsed form, `!q` into `Quoted`, `!ref` into `Name`, `!include`/`!py` into load-time nodes and any other `!head` into a `Call`; `load_text`; and `dump_structural`, the `ExprDumper` that writes forms back as tagged YAML. Source: `src/alienbio/expr/yaml_tags.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO expr](../../ABIO%20Design/ABIO%20Expr/ABIO%20Expr.md) → [ABIO YamlTags](ha://p/ABIO%20YamlTags) 
# ABIO YamlTags
The page for how YAML text becomes Expr forms and back: what each tag constructs, how a tag's node shape (mapping, sequence, scalar) decides the call's arguments, which tags are reserved or retired, and where the writer does not reproduce what the reader reads.

![ABIO YamlTags](ABIO%20YamlTags.svg) 
*Tags to forms* is the topic behind the five constructors; *Round trip* governs the dotted return edge, which loses a lone non-string argument (‡).

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
    `yaml.load(text, Loader=ExprLoader)`: untagged YAML is data, tagged nodes are forms. A `yaml.YAMLError` becomes `ExprError("YAML error: …")`; a constructor's `ExprError` carries `line N`. Includes are not resolved. ^load-text

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
`dump_structural` promises text that loads back to an equal form. It does for names, quotes of inline-expressible forms, calls with keyword arguments, calls with several positionals, calls whose lone positional is a string, and plain data. It does not (‡):

| Form | Written | Read back |
| --- | --- | --- |
| `Call("poisson", (3,))` | `!poisson '3'` | `poisson('3')`, which then fails to evaluate |
| `Call("h", (0.5,))`, `(1e20,)`, `(True,)` | `!h '0.5'`, `'1e+20'`, `'True'` | the same value as a string |
| `Call("h", ("",))` | `!h ""` | `h()`, the argument gone |
| `Call("h", (), {"args": [1]})` | `!h {args: [1]}` | `h(1)`, a keyword turned positional |
| a `Quoted` comprehension or set | `!q "each(over=xs, as='x', …)"` | refused at load ([ABIO Parse](ABIO%20Parse.md)) |

The first two rows are the representer writing `str(value)` with no style under a custom tag; the emitter then single-quotes it, and the loader reads any quoted scalar as a string.




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084) from the source at alienbio HEAD `c67f052` (read with `git show`). Run against an export of that tree: every row of the round-trip table was dumped and reloaded, and `evaluate` of the reloaded `poisson('3')` raised `must be real number, not str`; `!ev 1` refuses naming `!x`. Not determined: whether any production path calls `dump_structural` (the experiment writer `spec_to_text` does not; `X.dump` does). Findings filed on T088.
