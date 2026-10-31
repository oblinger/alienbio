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
Ten functions, three suffix sets, two names for the `!py` allowlist, the include budget, the helper namespace class and one exception.

| include | |
| --- | --- |
| [UnsafeSpecError](#^unsafespecerror) | An untrusted spec asked for more than it may |
| [YAML_SUFFIXES](#^yaml-suffixes) | `.yaml`, `.yml` |
| [TEXT_SUFFIXES](#^text-suffixes) | `.md`, `.txt` |
| [PY_SUFFIXES](#^py-suffixes) | `.py` |
| [PY_IMPORT_ROOTS](#^py-import-roots) | The packages `!py` may import from |
| [INCLUDE_MODULE_PREFIX](#^include-module-prefix) | The module name an included `.py` runs as |
| [helper_module_name](#^helper-module-name) | That name for one file |
| [allowed_module_name](#^allowed-module-name) | Under the import roots or a helper |
| [HelperNamespace](#^helpernamespace) | An included `.py` as a spec sees it |
| [resolve_path](#^resolve-path) | The file an include names, under trust |
| [MAX_INCLUDE_LOADS](#^max-include-loads) | File loads per document |
| [IncludeBudget](#^includebudget) | One document's include count and clock |
| [include_session](#^include-session) | One budget over a load |
| [load_include](#^load-include) | One include to `(kind, value)` |
| [run_python_file](#^run-python-file) | Execute a trusted `.py`, return its names |
| [recording_python_files](#^recording-python-files) | Collect every `.py` a load executes |
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

**PY_IMPORT_ROOTS**` = ("alienbio",)`
    The only top-level packages `resolve_py` imports from, trusted or not (design D1, restored at `5e7cd03`, T091 AG2). ^py-import-roots

**INCLUDE_MODULE_PREFIX**` = "alienbio_include_"`
    `run_python_file` executes a helper as `alienbio_include_<stem>`, so its own functions carry that `__module__` and pass the `!py` walk's owner check. ^include-module-prefix

**helper_module_name**`(target: Path) -> str`
    `alienbio_include_<stem>`: what a helper's own definitions carry as `__module__`. ^helper-module-name

**allowed_module_name**`(name) -> bool`
    `name` is a `PY_IMPORT_ROOTS` package or under one, or starts with `INCLUDE_MODULE_PREFIX`. ^allowed-module-name

**HelperNamespace**`(module: str, namespace: Mapping)` (a read-only `Mapping`)
    What a `.py` include returns (`h: !include helper.py`, an `_includes_` entry's module) since `d943ce4` (T091 AL2). Iterating its keys is free; reading a name judges the value: a function, class or module must be defined in the helper (`__module__` equals `module`), anything else must pass `access.check_reference` — so the helper's own imports (`h.os`, `h.run` → `subprocess.run`) and a `Path` refuse, as `!py helper.os` does. A denied entry point refuses first. `.module` is the helper's module name. ^helpernamespace

**resolve_path**`(path: str, base: Path, *, trusted: bool) -> Path`
    Trusted: `base / path` (or the absolute path), resolved, anywhere. Untrusted: refuses an absolute path, resolves `base / path` with symlinks followed, and refuses a result that is neither `base` nor under it. § [Trust](#trust). ^resolve-path

**MAX_INCLUDE_LOADS**` = 256`
    File loads one document's includes may make, a file named twice counted twice; `_includes_` entries and `!include` both count, and past it the load refuses naming the cap (`c0094c7`, T091 AP6: ten `!include next.yaml` per file chained six deep parsed 10^5 files before any meter or clock). ^max-include-loads

**IncludeBudget**`(limits=None)`
    Two slots: `loads`, the count so far, and `limits`, the load's `Limits`, whose clock each include ticks. ^includebudget

**include_session**`(limits=None) -> Iterator[IncludeBudget]` (context manager)
    One budget over the block, held in a `ContextVar` and shared by every nested load: `Env.load` opens one per document with its `Limits`; a bare `load_include` or `hydrate` opens its own (`c0094c7`, T091 AP6). ^include-session

**load_include**`(path: str, base: Path, *, trusted: bool, seen=frozenset()) -> tuple[str, Any]`
    Counts one load against the document's `MAX_INCLUDE_LOADS` and ticks its clock; then resolves the path, refuses one already in `seen` (a cycle) and a missing file, and returns by suffix: `("yaml", hydrated forms)` — read through `read_spec_text` (refused over `MAX_SPEC_BYTES` before it is read) and parsed once by `load_text(text, source=<file>)`, whose duplicate-key check and every syntax or depth error name the included file (`c0094c7`, T091 AP7, AP9; duplicate keys since `661005d`, T091 G3); a mapping's own `_includes_` resolved first, relative to that file, its own keys winning — `("text", str)`, size-checked the same way, or `("py", HelperNamespace)`, the file size-checked before `runpy` compiles it. Refuses any other suffix and an untrusted `.py`. ^load-include

**run_python_file**`(target: Path) -> dict[str, Any]`
    `runpy.run_path` under the module name `alienbio_include_<stem>`, returning every name not starting with `__`. Executes the file on every call; nothing is cached, by design (a cache would break the registry snapshot/restore the spec-example tests rely on), so its decorators re-register as the same definition and any other module-level side effect repeats per load. Inside a `recording_python_files` block it appends the resolved path to that block's list. ^run-python-file

**recording_python_files**`() -> Iterator[list[Path]]` (context manager)
    Yields a list that collects, in order, every `.py` file `run_python_file` executes inside the block (a `ContextVar`, so nested or concurrent loads keep their own). `suite/spec.py`'s experiment loader wraps the load in it to write the manifest's `helper_modules`. Since `661005d`. ^recording-python-files

**resolve_py**`(path: str, *, trusted: bool, modules=None) -> Any`
    Refuses untrusted. Requires at least `module.attr`, all identifiers, and refuses any segment starting with `_` (private or dunder). Looks the first segment up among the `modules` executed by `_includes_` (by file stem), reads the name off the helper and steps through attributes, every step judged as `HelperNamespace` judges a name — a callable or module must be defined in that helper. Otherwise refuses a first segment outside `PY_IMPORT_ROOTS` before importing anything, then imports the longest importable prefix and steps through attributes; that prefix and every module, class or callable step must belong to `PY_IMPORT_ROOTS` or an included helper (`INCLUDE_MODULE_PREFIX`), so `alienbio.config.os.system` and a helper's `from subprocess import run` refuse like `os.system`. Since `d943ce4` (T091 AL3) no step may be one of `access.DENIED_ENTRY_POINTS` (`!py alienbio.expr.include.run_python_file` ran any `.py` on disk), a non-callable step must be plain data or a domain value, and the result must pass `access.check_reference` — never a module ([ABIO Access](ABIO%20Access.md)). Since `df0bc6c` (T091 AP2) a function or class a step lands on that is not a helper's must pass `access.allowed_framework_code` — a registered head's function or a name in `PY_ALLOWED_MODULES` (`alienbio.suite.dist`, `alienbio.bio.makers`); `DENIED_ENTRY_POINTS` is seventeen whole modules. Raises `UnsafeSpecError` on a refusal, `ExprError` when nothing resolves. ^resolve-py

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
| `!py module.attr` | `UnsafeSpecError` | defined in an included helper, or under `alienbio.*` — a function or class only a registered head's or one in `PY_ALLOWED_MODULES`; never a denied module's name or a module |

`base` is the directory of the file that holds the include: the top-level file's directory for its own includes, an included file's directory for its nested ones. Resolution follows symlinks before the containment test, so a link inside the spec's directory that points out of it is refused. For text loaded with no file behind it, `Env.load` passes the working directory as `base`. Trust is the caller's flag on `Env.standard`; this module only obeys it. `suite/spec.load_spec` resolves the spec path once and hands the loader that resolved path and its text, and `Env.load` takes its include base from the resolved file (`d943ce4`, T091 AL1): a symlink into `catalog/` loads catalog's own helpers, one resolving outside loads untrusted, and nothing is re-resolved between the trust check and the read. Trust does not widen `!py`: the import roots, the owner check on every step and the deny set hold for a trusted load too, a refused module is never imported, and a helper exposes only what it defines.



## The `_includes_` list
`Env.load` pops `_includes_` from the top level of the file it loads and passes it to `include_bindings` before hydrating the rest, so a `.py` listed there has run (and its heads are registered, and its namespace answers `!py stem.attr`) before any other key is resolved. A `.yaml` listed there contributes its top-level keys under the file's own. An included `.yaml` mapping — through `_includes_` or `!include` — has its own `_includes_:` popped and resolved the same way by `load_include`, relative to that file, its own keys winning over what it includes (‡), so a chain `a → b → c` binds `c`'s keys and runs any `.py` listed in `b`.



## Cycles
`seen` holds the resolved paths on the current include chain: `Env.load` seeds it with the file itself, and each `.yaml` include adds its own path for its nested includes. A file reached twice along one chain refuses; the same file included from two siblings is loaded twice — and counted twice against `MAX_INCLUDE_LOADS`, which bounds the fan-out cycles cannot.




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084) from the source at alienbio HEAD `c67f052` (read with `git show`). Run against an export of that tree: `a.yaml` listing `b.yaml` in `_includes_`, where `b.yaml` lists `c.yaml`, binds `main`, `from_b` and a key `_includes_: [c.yaml]`, and `from_c` is never loaded; `x: !include b.yaml` gives `x` the same stray key. Findings filed on T088.
- 2026-10-28 — refreshed against `0eb23e5`: an included `.yaml`'s own `_includes_` loads, `UnsafeSpecError` is an `ExprError`, two `.py` entries sharing a stem refuse, `run_python_file`'s re-execution documented as deliberate (`c90ce0d`); figure's ‡ notes updated.
- 2026-10-29 — refreshed for `661005d` (T091 G3, D): an included `.yaml` is checked for duplicate keys before it loads; `recording_python_files` (new) collects the helper `.py` files a load ran, for the manifest's `helper_modules`. Figure still true.
- 2026-10-30 — refreshed for `5e7cd03` (T091 AG2): `resolve_py` imports only under `PY_IMPORT_ROOTS = ("alienbio",)` or an included helper, trusted or not; every module or callable step is owner-checked, `_` segments refuse. New `PY_IMPORT_ROOTS` / `INCLUDE_MODULE_PREFIX` blocks; figure's `resolve_py` box now says so.
- 2026-10-30 — refreshed for `d943ce4` (T091 AL1–AL3): a `.py` include is a `HelperNamespace` exposing only the helper's own definitions plus plain or domain data; `resolve_py` refuses `DENIED_ENTRY_POINTS` at every step and a module result (`access.check_reference`); `load_spec` and `Env.load` work from the one resolved path. New blocks `HelperNamespace`, `helper_module_name`, `allowed_module_name`. Figure still true.
- 2026-10-30 — refreshed for `c0094c7` (T091 AP6, AP7, AP9) and `df0bc6c` (AP2): `MAX_INCLUDE_LOADS = 256` per document via `include_session` / `IncludeBudget` (new), each load ticking the clock; includes and `.py` files size-capped at `MAX_SPEC_BYTES`; one parse per included `.yaml` (the separate `refuse_duplicate_keys` pass is gone), errors naming the included file; `resolve_py` allow-lists framework code. Figure still true.
