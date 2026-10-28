---
description: "`include`: load-time resolution of `!include` and `!py`, before anything evaluates — the trust gate (an untrusted load may include only `.yaml`/`.md`/`.txt` by a contained relative path; `.py` and `!py` need a trusted load), `hydrate` over a form tree, the `_includes_` list form, `resolve_py`, `UnsafeSpecError`. Source: `src/alienbio/expr/include.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO expr Modules](ABIO%20expr%20Modules.md) → [ABIO Include](ha://p/ABIO%20Include) 
# ABIO Include
The page for what happens to `!include` and `!py` between reading a spec and evaluating it: which files an untrusted spec may pull in, what each file kind becomes, how the `_includes_` list merges, and how a Python reference is found.

![ABIO Include](ABIO%20Include.svg) 
*Trust* is the topic behind the gate every path passes (`resolve_path`); *The `_includes_` list* governs the merge into the file's scope, at the loaded file's top level and again inside every included `.yaml` (‡).

`include.py` runs inside `Env.load` and `Env.hydrate` ([ABIO Env](ABIO%20Env.md)), after the YAML loader has turned the tags into `Include` and `PyRef` nodes ([ABIO YamlTags](ABIO%20YamlTags.md), [ABIO Form](ABIO%20Form.md)) and before the interpreter sees the tree ([ABIO Interp](ABIO%20Interp.md) raises if one survives). A `.py` include matters because executing it fires its `@fn` / `@expander` / `@guard` decorators into [ABIO Registry](ABIO%20Registry.md). Which loads are trusted is decided by the caller: `suite/spec.load_spec` trusts a file whose resolved path is under the repository's `catalog/` and nothing else ([ABIO ExperimentSpec](../ABIO%20suite/ABIO%20ExperimentSpec.md)), then hands it to `load_experiment` ([ABIO ExprExperiment](../ABIO%20suite/ABIO%20ExprExperiment.md)). The design of the Python escapes is [ABIO Expr Python Escapes](../../ABIO%20Design/ABIO%20Expr/ABIO%20Expr%20Python%20Escapes.md); the sandbox seams are on [ABIO-Expr](../../ABIO%20Architecture/ABIO-Expr.md).



## include Interface
Six functions, three suffix sets and one exception.

| include | |
| --- | --- |
| [UnsafeSpecError](#^unsafespecerror) | An untrusted spec asked for more than it may |
| [YAML_SUFFIXES](#^yaml-suffixes) | `.yaml`, `.yml` |
| [TEXT_SUFFIXES](#^text-suffixes) | `.md`, `.txt` |
| [PY_SUFFIXES](#^py-suffixes) | `.py` |
| [resolve_path](#^resolve-path) | The file an include names, under trust |
| [load_include](#^load-include) | One include to `(kind, value)` |
| [run_python_file](#^run-python-file) | Execute a trusted `.py`, return its names |
| [resolve_py](#^resolve-py) | `module.attr` to the object |
| [hydrate](#^hydrate) | Replace every `Include` / `PyRef` in a tree |
| [include_bindings](#^include-bindings) | The `_includes_` list to bindings and modules |

**UnsafeSpecError** (exception)
    Raised for a `.py` include or a `!py` on an untrusted load, an absolute include path, and a path that resolves outside its base. A subclass of `ExprError` (and so of `ValueError`), so a caller reporting a bad spec catches it with every other refusal. ^unsafespecerror

**YAML_SUFFIXES**` = {".yaml", ".yml"}`
    Spliced as forms, their own includes resolved relative to their own directory. ^yaml-suffixes

**TEXT_SUFFIXES**` = {".md", ".txt"}`
    Read as one string. ^text-suffixes

**PY_SUFFIXES**` = {".py"}`
    Executed, trusted loads only. ^py-suffixes

**resolve_path**`(path: str, base: Path, *, trusted: bool) -> Path`
    Trusted: `base / path` (or the absolute path), resolved, anywhere. Untrusted: refuses an absolute path, resolves `base / path` with symlinks followed, and refuses a result that is neither `base` nor under it. § [Trust](#trust). ^resolve-path

**load_include**`(path: str, base: Path, *, trusted: bool, seen=frozenset()) -> tuple[str, Any]`
    Resolves the path; refuses one already in `seen` (a cycle) and a missing file; returns `("yaml", hydrated forms)` — a mapping's own `_includes_` resolved first, relative to that file, its own keys winning — `("text", str)` or `("py", namespace)` by suffix, refusing any other suffix and an untrusted `.py`. ^load-include

**run_python_file**`(target: Path) -> dict[str, Any]`
    `runpy.run_path` under the module name `alienbio_include_<stem>`, returning every name not starting with `__`. Executes the file on every call; nothing is cached, by design (a cache would break the registry snapshot/restore the spec-example tests rely on), so its decorators re-register as the same definition and any other module-level side effect repeats per load. ^run-python-file

**resolve_py**`(path: str, *, trusted: bool, modules=None) -> Any`
    Refuses untrusted. Requires at least `module.attr`, all identifiers. Looks the first segment up among the `modules` executed by `_includes_` (by file stem) and steps through keys or attributes; otherwise imports the longest importable prefix and steps through attributes. Raises `ExprError` when nothing resolves. ^resolve-py

**hydrate**`(data, *, base: Path, trusted: bool, seen=frozenset(), modules=None) -> Any`
    Returns a copy of the tree with every `Include` replaced by its loaded value and every `PyRef` by its object, descending dicts, lists, call arguments and quoted forms; anything else is returned as is. ^hydrate

**include_bindings**`(entries, base: Path, *, trusted: bool, seen=frozenset()) -> tuple[dict, dict]`
    For a `_includes_:` list of path strings: each `.yaml` must be a mapping and contributes its top-level keys (a later entry wins); each `.py` is executed and its namespace kept under its stem, a second `.py` with the same stem refusing (`!py stem.…` would be ambiguous); a text file refuses (it has no key to bind to). Returns `(bindings, modules)`; the caller lets the file's own keys win. ^include-bindings




# Include Semantics

## Trust

| | Untrusted (the default) | Trusted |
| --- | --- | --- |
| `.yaml` / `.yml` / `.md` / `.txt` | relative path, resolved inside `base` | any path |
| `.py` include | `UnsafeSpecError` | executed |
| `!py module.attr` | `UnsafeSpecError` | imported or looked up |

`base` is the directory of the file that holds the include: the top-level file's directory for its own includes, an included file's directory for its nested ones. Resolution follows symlinks before the containment test, so a link inside the spec's directory that points out of it is refused. For text loaded with no file behind it, `Env.load` passes the working directory as `base`. Trust is the caller's flag on `Env.standard`; this module only obeys it.



## The `_includes_` list
`Env.load` pops `_includes_` from the top level of the file it loads and passes it to `include_bindings` before hydrating the rest, so a `.py` listed there has run (and its heads are registered, and its namespace answers `!py stem.attr`) before any other key is resolved. A `.yaml` listed there contributes its top-level keys under the file's own. An included `.yaml` mapping — through `_includes_` or `!include` — has its own `_includes_:` popped and resolved the same way by `load_include`, relative to that file, its own keys winning over what it includes (‡), so a chain `a → b → c` binds `c`'s keys and runs any `.py` listed in `b`.



## Cycles
`seen` holds the resolved paths on the current include chain: `Env.load` seeds it with the file itself, and each `.yaml` include adds its own path for its nested includes. A file reached twice along one chain refuses; the same file included from two siblings is loaded twice.




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084) from the source at alienbio HEAD `c67f052` (read with `git show`). Run against an export of that tree: `a.yaml` listing `b.yaml` in `_includes_`, where `b.yaml` lists `c.yaml`, binds `main`, `from_b` and a key `_includes_: [c.yaml]`, and `from_c` is never loaded; `x: !include b.yaml` gives `x` the same stray key. Findings filed on T088.
- 2026-10-28 — refreshed against `0eb23e5`: an included `.yaml`'s own `_includes_` loads, `UnsafeSpecError` is an `ExprError`, two `.py` entries sharing a stem refuse, `run_python_file`'s re-execution documented as deliberate (`c90ce0d`); figure's ‡ notes updated.
