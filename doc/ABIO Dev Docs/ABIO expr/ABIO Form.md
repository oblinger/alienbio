---
description: "`form`: the Expr abstract syntax — `Name`, `Call`, `Quoted`, and the two load-time nodes `Include` and `PyRef`, with `is_form`, `contains_form` and `walk`; plus `x.py`'s `X`, the Python spelling that builds the same forms (`X.<head>(...)`, `X.name`, `X.quote`, `X.parse`, `X.load`, `X.dump`). Source: `src/alienbio/expr/form.py`, `src/alienbio/expr/x.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO expr](../../ABIO%20Design/ABIO%20Expr/ABIO%20Expr.md) → [ABIO Form](ha://p/ABIO%20Form) 
# ABIO Form
The page for the data every Expr spec becomes: the three tagged forms the interpreter gives meaning to, the two that exist only until load resolves them, the walkers over a form tree, and `X`, which builds the same tree from Python.

![ABIO Form](ABIO%20Form.svg) 
*Three spellings, one tree* is the topic behind the three arrows into the form tree; *Equality and hashing* governs the note on `Call` (‡).

`form.py` defines shapes only and imports nothing from the rest of `expr/`; meaning is given by [ABIO Interp](ABIO%20Interp.md). The inline text spelling is [ABIO Parse](ABIO%20Parse.md), the YAML spelling [ABIO YamlTags](ABIO%20YamlTags.md), and the resolution of `Include` and `PyRef` before evaluation [ABIO Include](ABIO%20Include.md). `x.py` has no page of its own and is covered here, in § [X Interface](#x-interface). The design of the five shapes is [ABIO Expr](../../ABIO%20Design/ABIO%20Expr/ABIO%20Expr.md); the user's view is [ABIO Expr Spec](../../ABIO%20Guides/ABIO%20Expr%20Spec.md) and [ABIO Expr Python API](../../ABIO%20Guides/ABIO%20Expr%20Python%20API.md).



## Name Interface
A frozen dataclass: a lookup in the environment.

| Name | |
| --- | --- |
| [path](#^path) | `ident(.ident)*` |

**path**`: str`
    The first segment resolves in the scope chain; each further segment steps into the value (mapping key, sequence index, then attribute). Spelled `!ref a.b` in YAML and `a.b` inline. ^path



## Call Interface
A frozen dataclass: a head applied to positional and keyword argument forms. Whether the arguments are evaluated first depends on the head's kind, decided at evaluation, not here.

| Call | |
| --- | --- |
| [head](#^head) | The head's name |
| [args](#^args) | Positional argument forms |
| [kwargs](#^kwargs) | Keyword argument forms |

**head**`: str`
    A registered function, expander, guard or special form, a template bound in scope, or an `op:*` operator. ^head

**args**`: tuple[Any, ...] = ()`
    Coerced to a tuple on construction. ^args

**kwargs**`: Mapping[str, Any]`
    Copied into a plain `dict` on construction. The dataclass is frozen, but this dict is not: it can be mutated in place, and it makes every `Call` unhashable. ^kwargs



## Quoted Interface
A frozen dataclass: a form held as a value. Evaluating one yields a `QuotedForm` closed over the evaluating environment ([ABIO Interp](ABIO%20Interp.md)), sampleable as a `Dist`.

| Quoted | |
| --- | --- |
| [form](#^form) | The held form |

**form**`: Any`
    Not evaluated until the `QuotedForm` is sampled or run. Spelled `!q` in YAML and `quote(f)` inline. ^form



## Include Interface
A frozen dataclass for `!include path`: resolved at load by `hydrate` and never seen by the interpreter, which raises if one reaches it.

| Include | |
| --- | --- |
| [path](#^include-path) | The file named |

**path**`: str`
    Relative to the including file's directory; `.yaml` splices forms, `.md` / `.txt` read text, `.py` executes under a trusted load. ^include-path



## PyRef Interface
A frozen dataclass for `!py module.attr`: a Python object as a value, resolved at load under a trusted load only. It is a value, not a head; bind it with `let` to call it.

| PyRef | |
| --- | --- |
| [path](#^pyref-path) | `module.attr` |

**path**`: str`
    Resolved against a `_includes_`-executed module by stem first, else the longest importable module prefix. ^pyref-path



## form Interface
The module-level helpers.

| form | |
| --- | --- |
| [Form](#^form-alias) | The type alias for any form |
| [is_form](#^is-form) | One of the three tagged shapes |
| [contains_form](#^contains-form) | A tagged shape anywhere inside |
| [walk](#^walk) | Pre-order walk over a form tree |

**Form**` = Any`
    `Name | Call | Quoted | list | dict | scalar`, written as `Any`. ^form-alias

**is_form**`(value) -> bool`
    True for a `Name`, `Call` or `Quoted`. A literal or a data container is a form too, but carries no meaning beyond its Python value; `Include` and `PyRef` are not counted. ^is-form

**contains_form**`(value) -> bool`
    True when `value` is, or holds anywhere inside its data, a tagged form; how a consumer tells literal data from data that still needs evaluating. ^contains-form

**walk**`(value) -> Iterator[Any]`
    Yields every node pre-order: a call's positional then keyword arguments, a quote's form, a dict's values (not its keys), a list's or tuple's items. ^walk



## X Interface
`X` is the one instance of `x._X`: attribute access builds a call, so a Python caller writes the same tree a YAML author does.

| X | |
| --- | --- |
| [X.head](#^x-head) | `X.<head>(*args, **kwargs)` builds a `Call` |
| [call](#^call) | A call whose head is not an identifier or collides |
| [name](#^name) | A `Name` |
| [quote](#^quote) | A `Quoted` |
| [parse](#^parse) | Inline text to a form |
| [load](#^load) | YAML text to forms |
| [dump](#^dump) | A form to inline or structural text |

**X.head**`(*args, **kwargs) -> Call`
    Any attribute not starting with `_` returns a builder for `Call(attr, args, kwargs)`; nothing checks that the head exists until evaluation. ^x-head

**call**`(head: str, *args, **kwargs) -> Call` (static)
    For a head the attribute spelling cannot write: `X.call("op:add", 1, 2)`, or a head named `call`, `name`, `quote`, `parse`, `load` or `dump`. ^call

**name**`(path: str) -> Name` (static)
    `Name(path)`. ^name

**quote**`(form) -> Quoted` (static)
    `Quoted(form)`. ^quote

**parse**`(text: str) -> Any` (static)
    [ABIO Parse](ABIO%20Parse.md) `parse`. ^parse

**load**`(text: str) -> Any` (static)
    [ABIO YamlTags](ABIO%20YamlTags.md) `load_text`; includes are not resolved. ^load

**dump**`(form, style: str = "inline") -> str` (static)
    `"inline"` through [ABIO Parse](ABIO%20Parse.md) `dump`, `"structural"` through `dump_structural`; any other style raises `ValueError`. ^dump




# Form Semantics

## Three spellings, one tree

| Form | Python | Inline (`!x`) | Structural (YAML) |
| --- | --- | --- | --- |
| `Name("a.b")` | `X.name("a.b")` | `a.b` | `!ref a.b` |
| `Call("normal", (0, 1))` | `X.normal(0, 1)` | `normal(0, 1)` | `!normal [0, 1]` |
| `Call("f", (), {"k": 2})` | `X.f(k=2)` | `f(k=2)` | `!f {k: 2}` |
| `Quoted(Call("lognormal", (1, 0.3)))` | `X.quote(X.lognormal(1, 0.3))` | `quote(lognormal(1, 0.3))` | `!q lognormal(1, 0.3)` |
| `Include("x.yaml")` | — | — | `!include x.yaml` |
| `PyRef("m.f")` | — | — | `!py m.f` |

Untagged YAML and plain Python lists, dicts and scalars are data in every spelling. An untagged mapping carrying `_type:` is the fourth spelling of a call, read by the interpreter, not here.



## Equality and hashing
The forms compare by value, so a test can assert on a parsed or loaded tree directly. `Name`, `Quoted`, `Include` and `PyRef` hash; `Call` does not, because its `kwargs` field is a `dict` (‡), and an `args` tuple holding a list would not either. A `Call` can therefore not key a mapping or sit in a set, and since the dataclass's `frozen=True` covers only rebinding the field, `call.kwargs["k"] = 3` changes a call in place. The interpreter copies `kwargs` before stripping `guards:`, so it never mutates a form it was given.




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084) from the source at alienbio HEAD `c67f052` (read with `git show`). Run against an export of that tree: `hash(X.f(1, k=2))` raises `unhashable type: 'dict'` and `c.kwargs["k"] = 3` mutates the call; `X._x` raises `AttributeError`. No caller in `expr/` hashes a `Call`. Findings filed on T088.
