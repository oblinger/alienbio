"""Includes and Python references — resolved at load, before evaluation (M47.5).

``!include x.yaml`` splices the file's forms in place (its own includes
resolved relative to *its* directory); ``!include x.md`` / ``.txt`` reads
text; ``!include x.py`` executes the file so its ``@fn`` / ``@expander`` /
``@guard`` decorators register heads, and yields the module namespace.
``_includes_: [...]`` at the top of a file is the list form: ``.py`` entries
execute, ``.yaml`` entries merge their top-level keys into the file's scope
(the file's own keys win). ``!py module.attr`` yields a Python object.

**Trust.** An untrusted load (the default) may include only ``.yaml`` /
``.md`` / ``.txt`` files by a relative path that stays inside the including
file's directory; ``.py`` includes and ``!py`` raise
:class:`UnsafeSpecError`. A trusted load
(``Env.standard(trusted=True)``) may do all of it, from any path.
"""

from __future__ import annotations

import contextlib
import contextvars
import importlib
import runpy
import types
from pathlib import Path
from typing import Any, Iterator, Mapping, Optional

from .env import ExprError
from .form import Call, Include, PyRef, Quoted


class UnsafeSpecError(ExprError):
    """Raised when an untrusted spec asks for code execution (a ``.py``
    include, ``!py``) or a file outside its own directory. An
    :class:`ExprError` (and so a ``ValueError``) like every other refusal of
    a bad spec — T088 include 2: it escaped callers that catch ``ExprError``
    to report one."""


def _resolve_contained_path(path: str, base: str) -> Path:
    """Resolve an untrusted include path: relative, no ``..``, inside ``base``."""
    p = Path(path)
    if p.is_absolute():
        raise UnsafeSpecError(f"absolute !include paths are not allowed for untrusted specs: {path!r}")
    root = Path(base).resolve()
    resolved = (root / p).resolve()
    if resolved != root and root not in resolved.parents:
        raise UnsafeSpecError(f"!include path escapes its base directory: {path!r} (resolved to {resolved}, base {root})")
    return resolved

YAML_SUFFIXES: frozenset[str] = frozenset({".yaml", ".yml"})
TEXT_SUFFIXES: frozenset[str] = frozenset({".md", ".txt"})
PY_SUFFIXES: frozenset[str] = frozenset({".py"})


def resolve_path(path: str, base: Path, *, trusted: bool) -> Path:
    """The file an include names. Untrusted: relative, no ``..``, inside ``base``."""
    if trusted:
        p = Path(path)
        return (p if p.is_absolute() else base / p).resolve()
    return _resolve_contained_path(path, str(base))


#: The ``.py`` files a load executed, while :func:`recording_python_files`
#: is active (T091 E1: the run manifest names an experiment's helpers).
_EXECUTED: contextvars.ContextVar[Optional[list[Path]]] = contextvars.ContextVar("alienbio_executed_py", default=None)


@contextlib.contextmanager
def recording_python_files() -> Iterator[list[Path]]:
    """Collect, in order, every ``.py`` file :func:`run_python_file` executes
    inside the block (a trusted load's ``_includes_`` helpers)."""
    executed: list[Path] = []
    token = _EXECUTED.set(executed)
    try:
        yield executed
    finally:
        _EXECUTED.reset(token)


def run_python_file(target: Path) -> dict[str, Any]:
    """Execute ``target`` (a trusted ``.py`` include); its public names.

    The file executes on every load that names it — nothing is cached, so its
    decorators re-register (the registry accepts the same definition again)
    and any other module-level side effect (a counter, a mutated global in a
    shared helper) repeats per load (T088 include 3). A catalog helper keeps
    its module level to definitions."""
    executed = _EXECUTED.get()
    if executed is not None:
        executed.append(Path(target).resolve())
    namespace = runpy.run_path(str(target), run_name=helper_module_name(target))
    return {k: v for k, v in namespace.items() if not k.startswith("__")}


def helper_module_name(target: Path) -> str:
    """The module name a ``.py`` include executes as: what its own
    definitions carry as ``__module__``."""
    return f"{INCLUDE_MODULE_PREFIX}{Path(target).stem}"


class HelperNamespace(Mapping[str, Any]):
    """An included ``.py`` file's namespace as a spec sees it (``h: !include
    helper.py``, ``!py helper.name``). Reading a name applies the ``!py``
    rule (T091 AL2): a function or class must be DEFINED in the helper
    (``__module__`` is the helper's), anything else must be plain data or a
    domain value — so the helper's own imports (``h.os``, ``h.run`` →
    ``subprocess.run``) refuse, as ``!py helper.os`` does. Iterating the keys
    is free; a value is judged when it is read."""

    def __init__(self, module: str, namespace: Mapping[str, Any]) -> None:
        self._module = module
        self._ns = dict(namespace)

    @property
    def module(self) -> str:
        return self._module

    def __getitem__(self, key: str) -> Any:
        value = self._ns[key]
        _check_helper_object(self._module, f"included helper name {key!r}", value, key)
        return value

    def __iter__(self) -> Iterator[str]:
        return iter(self._ns)

    def __len__(self) -> int:
        return len(self._ns)

    def __repr__(self) -> str:
        return f"<included helper {self._module} {sorted(self._ns)}>"


#: File loads one document's includes may make, counting a file named
#: twice twice (T091 AP6: ten ``!include next.yaml`` per file, chained six
#: deep, parsed 10^5 files before any meter or clock). ``_includes_`` and
#: ``!include`` both count; past it the load refuses by name.
MAX_INCLUDE_LOADS = 256


class IncludeBudget:
    """The include count of one document load, and its clock."""

    __slots__ = ("loads", "limits")

    def __init__(self, limits: Any = None) -> None:
        self.loads = 0
        self.limits = limits


_SESSION: contextvars.ContextVar[Optional[IncludeBudget]] = contextvars.ContextVar("alienbio_include_budget", default=None)


@contextlib.contextmanager
def include_session(limits: Any = None) -> Iterator[IncludeBudget]:
    """One include budget (:data:`MAX_INCLUDE_LOADS`) over the block, shared
    by every nested load — ``Env.load`` opens one per document with its
    ``Limits`` (whose clock each include ticks); a bare
    :func:`load_include` / :func:`hydrate` call opens its own."""
    current = _SESSION.get()
    if current is not None:
        yield current
        return
    budget = IncludeBudget(limits)
    token = _SESSION.set(budget)
    try:
        yield budget
    finally:
        _SESSION.reset(token)


def load_include(path: str, base: Path, *, trusted: bool, seen: frozenset[Path] = frozenset()) -> tuple[str, Any]:
    """Resolve one include: ``("yaml" | "text" | "py", value)``. Counted
    against the document's :data:`MAX_INCLUDE_LOADS` and its clock; a file
    over ``MAX_SPEC_BYTES`` refuses before it is read."""
    with include_session() as budget:
        budget.loads += 1
        if budget.loads > MAX_INCLUDE_LOADS:
            raise ExprError(f"!include {path!r}: more than MAX_INCLUDE_LOADS={MAX_INCLUDE_LOADS} file loads in one document", str(base))
        if budget.limits is not None:
            budget.limits.tick(str(base))
        return _load_include(path, base, trusted=trusted, seen=seen)


def _load_include(path: str, base: Path, *, trusted: bool, seen: frozenset[Path]) -> tuple[str, Any]:
    from .yaml_tags import check_spec_size, load_text, read_spec_text

    target = resolve_path(path, base, trusted=trusted)
    if target in seen:
        raise ExprError(f"!include cycle through {path!r}", str(base))
    if not target.is_file():
        raise ExprError(f"!include: no such file {path!r} (relative to {base})", str(base))
    suffix = target.suffix.lower()
    if suffix in YAML_SUFFIXES:
        # T091 G3 — the duplicate-key check every experiment file gets (B5),
        # one file down, inside the single parse (T091 AP7); a syntax error
        # or a too-deep nest names the included file (T091 AP9).
        data = load_text(read_spec_text(target), source=str(target))
        inner_seen = seen | {target}
        if isinstance(data, Mapping) and "_includes_" in data:
            # T088 include 1: only ``Env.load`` popped ``_includes_``, so an
            # included file's own list was bound as a stray key and never
            # loaded. Resolved here relative to the included file, its own
            # keys winning, as ``Env.load`` does for the top file.
            data = dict(data)
            included, modules = include_bindings(data.pop("_includes_"), target.parent, trusted=trusted, seen=inner_seen)
            own = hydrate(data, base=target.parent, trusted=trusted, seen=inner_seen, modules=modules)
            return "yaml", {**included, **own}
        return "yaml", hydrate(data, base=target.parent, trusted=trusted, seen=inner_seen)
    if suffix in TEXT_SUFFIXES:
        return "text", read_spec_text(target)
    if suffix in PY_SUFFIXES:
        if not trusted:
            raise UnsafeSpecError(f"!include {path!r}: executing Python requires a trusted load")
        check_spec_size(target)  # before runpy compiles it
        return "py", HelperNamespace(helper_module_name(target), run_python_file(target))
    raise ExprError(f"!include {path!r}: unknown file kind {suffix!r} (yaml / yml / md / txt / py)", str(base))


#: The import roots ``!py`` may name (Audit Findings 2026-07-10 § D1,
#: restored T091 AG2): the framework's own package. A ``.py`` file the spec's
#: ``_includes_`` executed is the other source (its stem, see ``modules``) —
#: the Expr successor of D1's registered source roots.
PY_IMPORT_ROOTS: tuple[str, ...] = ("alienbio",)

#: The module a ``.py`` include executes as (``run_python_file``): what a
#: helper's own functions carry as ``__module__``.
INCLUDE_MODULE_PREFIX = "alienbio_include_"


def allowed_module_name(name: Any) -> bool:
    """``name`` is under :data:`PY_IMPORT_ROOTS` or is an included helper's module."""
    if not isinstance(name, str):
        return False
    return any(name == root or name.startswith(root + ".") for root in PY_IMPORT_ROOTS) or name.startswith(INCLUDE_MODULE_PREFIX)


def _deny(what: str, obj: Any, step: str) -> None:
    from .access import denied_entry_point

    entry = denied_entry_point(obj)
    if entry is not None:
        raise UnsafeSpecError(f"{what}: {step!r} is a framework entry point that loads or executes code ({entry})")


def _check_final(what: str, obj: Any, step: str) -> None:
    """The object a walk lands on passes :func:`.access.check_reference`."""
    from ..spec_lang.safe_eval import UnsafeExpressionError
    from .access import check_reference

    try:
        check_reference(obj, f"{what}: {step!r}")
    except UnsafeExpressionError as exc:
        raise UnsafeSpecError(str(exc)) from None


def _check_py_object(path: str, obj: Any, step: str, *, final: bool = False) -> None:
    """A ``!py`` walk never leaves the allowed roots: a module it passes
    through, and a function or class it lands on, must belong to
    :data:`PY_IMPORT_ROOTS` or an included helper — so ``alienbio.x.os.system``
    or a helper's ``from subprocess import run`` refuses like ``os.system``.
    No step may be a denied entry point (:data:`.access.DENIED_ENTRY_POINTS`),
    a non-module step that is not callable must be plain data or a domain
    value, and the result must not be a module (T091 AL3). A function or
    class it lands on under ``alienbio`` must be allowed framework code
    (:func:`.access.allowed_framework_code`, T091 AP2)."""
    what = f"!py {path!r}"
    _deny(what, obj, step)
    if isinstance(obj, types.ModuleType):
        owner: Any = obj.__name__
    elif callable(obj):
        owner = getattr(obj, "__module__", None)
    else:
        _check_final(what, obj, step)  # plain data or a domain value
        return
    if not allowed_module_name(owner):
        raise UnsafeSpecError(
            f"!py {path!r}: {step!r} belongs to {owner!r}, outside the allowed import roots "
            f"{list(PY_IMPORT_ROOTS)} and the spec's included helpers"
        )
    if final:
        _check_final(what, obj, step)
        if not isinstance(obj, types.ModuleType) and not str(owner).startswith(INCLUDE_MODULE_PREFIX):
            from .access import PY_ALLOWED_MODULES, allowed_framework_code

            # T091 AP2: framework code is allow-listed, not deny-listed.
            if not allowed_framework_code(obj):
                raise UnsafeSpecError(
                    f"!py {path!r}: {step!r} is framework code a spec may not reference — only registered "
                    f"heads and {list(PY_ALLOWED_MODULES)} (call a head by name instead)"
                )


def _check_helper_object(module: str, what: str, obj: Any, step: str) -> None:
    """A name read off an included helper (and every step past it): a
    callable must be defined in that helper, anything else must pass
    :func:`.access.check_reference` (T091 AL2)."""
    _deny(what, obj, step)
    if isinstance(obj, types.ModuleType) or callable(obj):
        owner: Any = obj.__name__ if isinstance(obj, types.ModuleType) else getattr(obj, "__module__", None)
        if owner != module:
            raise UnsafeSpecError(
                f"{what}: {step!r} belongs to {owner!r}, not to the included helper {module!r} — a helper "
                f"exposes only what it defines (outside the allowed import roots {list(PY_IMPORT_ROOTS)} for a spec)"
            )
        return
    _check_final(what, obj, step)


def resolve_py(path: str, *, trusted: bool, modules: Optional[Mapping[str, Mapping[str, Any]]] = None) -> Any:
    """``module.attr`` -> the object: a module executed by ``_includes_`` /
    ``!include x.py`` (by its file stem) first, else the longest importable
    module prefix under :data:`PY_IMPORT_ROOTS`, then attributes. Trusted
    loads only; the root allowlist holds under trust too (D1)."""
    if not trusted:
        raise UnsafeSpecError(f"!py {path!r}: a Python reference requires a trusted load")
    parts = path.split(".")
    if len(parts) < 2 or not all(p.isidentifier() for p in parts):
        raise ExprError(f"!py {path!r}: expected module.attr")
    if any(p.startswith("_") for p in parts):
        raise UnsafeSpecError(f"!py {path!r}: a private or dunder name is not a Python reference")
    if modules and parts[0] in modules:
        obj: Any = modules[parts[0]]
        helper = obj.module if isinstance(obj, HelperNamespace) else f"{INCLUDE_MODULE_PREFIX}{parts[0]}"
        raw = obj._ns if isinstance(obj, HelperNamespace) else obj
        for i, attr in enumerate(parts[1:]):
            try:
                obj = raw[attr] if i == 0 else getattr(obj, attr)
            except (KeyError, AttributeError, TypeError):
                raise ExprError(f"!py {path!r}: no {attr!r} in the included module {parts[0]!r}") from None
            _check_helper_object(helper, f"!py {path!r}", obj, attr)
        return obj
    if parts[0] not in PY_IMPORT_ROOTS:
        raise UnsafeSpecError(
            f"!py {path!r}: module {parts[0]!r} is outside the allowed import roots {list(PY_IMPORT_ROOTS)} "
            "(and is not a .py file this spec includes)"
        )
    for i in range(len(parts) - 1, 0, -1):
        try:
            obj = importlib.import_module(".".join(parts[:i]))
        except ImportError:
            continue
        _check_py_object(path, obj, parts[i - 1])
        for j in range(i, len(parts)):
            attr = parts[j]
            try:
                obj = getattr(obj, attr)
            except AttributeError:
                raise ExprError(f"!py {path!r}: no attribute {attr!r} on {'.'.join(parts[:i])}") from None
            _check_py_object(path, obj, attr, final=j == len(parts) - 1)
        return obj
    raise ExprError(f"!py {path!r}: no importable module prefix")


def hydrate(
    data: Any,
    *,
    base: Path,
    trusted: bool,
    seen: frozenset[Path] = frozenset(),
    modules: Optional[Mapping[str, Mapping[str, Any]]] = None,
) -> Any:
    """Replace every :class:`Include` / :class:`PyRef` inside ``data`` (forms
    included) with what it names. ``modules`` are the ``.py`` includes already
    executed (stem -> namespace), which ``!py`` resolves against first.
    Everything else is returned as is."""
    rec = lambda v: hydrate(v, base=base, trusted=trusted, seen=seen, modules=modules)  # noqa: E731
    if isinstance(data, Include):
        _kind, value = load_include(data.path, base, trusted=trusted, seen=seen)
        return value
    if isinstance(data, PyRef):
        return resolve_py(data.path, trusted=trusted, modules=modules)
    if isinstance(data, dict):
        return {k: rec(v) for k, v in data.items()}
    if isinstance(data, list):
        return [rec(v) for v in data]
    if isinstance(data, Call):
        return Call(data.head, tuple(rec(a) for a in data.args), {k: rec(v) for k, v in data.kwargs.items()})
    if isinstance(data, Quoted):
        return Quoted(rec(data.form))
    return data


def include_bindings(
    entries: Any, base: Path, *, trusted: bool, seen: frozenset[Path] = frozenset()
) -> tuple[dict[str, Any], dict[str, Mapping[str, Any]]]:
    """The ``_includes_:`` list: execute each ``.py`` (its namespace is kept
    under the file's stem, for ``!py``); collect each ``.yaml`` file's
    top-level keys (later entries win among themselves; the including file's
    own keys win over all of them — the caller applies that). Returns
    ``(bindings, modules)``."""
    if not isinstance(entries, list) or not all(isinstance(e, str) for e in entries):
        raise ExprError("_includes_ must be a list of file paths", str(base))
    merged: dict[str, Any] = {}
    modules: dict[str, Mapping[str, Any]] = {}
    for entry in entries:
        kind, value = load_include(entry, base, trusted=trusted, seen=seen)
        if kind == "yaml":
            if not isinstance(value, Mapping):
                raise ExprError(f"_includes_: {entry!r} must be a mapping at the top level", str(base))
            merged.update(value)
        elif kind == "text":
            raise ExprError(f"_includes_: {entry!r} is text — give it a name with `key: !include {entry}`", str(base))
        else:  # "py": executed for its registrations; the namespace answers !py
            stem = Path(entry).stem
            if stem in modules:
                # T088 include 3: a second file with the same stem silently
                # replaced the first's namespace for `!py stem.attr`.
                raise ExprError(f"_includes_: {entry!r} has the same stem {stem!r} as an earlier .py entry; `!py {stem}.…` would be ambiguous", str(base))
            modules[stem] = value
    return merged, modules


__all__ = [
    "HelperNamespace",
    "INCLUDE_MODULE_PREFIX",
    "IncludeBudget",
    "MAX_INCLUDE_LOADS",
    "PY_IMPORT_ROOTS",
    "UnsafeSpecError",
    "allowed_module_name",
    "helper_module_name",
    "hydrate",
    "include_bindings",
    "include_session",
    "load_include",
    "recording_python_files",
    "resolve_path",
    "resolve_py",
    "run_python_file",
]
