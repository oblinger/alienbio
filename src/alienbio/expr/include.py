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

import importlib
import runpy
from pathlib import Path
from typing import Any, Mapping, Optional

from .env import ExprError
from .form import Call, Include, PyRef, Quoted


class UnsafeSpecError(Exception):
    """Raised when an untrusted spec asks for code execution (a ``.py``
    include, ``!py``) or a file outside its own directory."""


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


def run_python_file(target: Path) -> dict[str, Any]:
    """Execute ``target`` (a trusted ``.py`` include); its public names."""
    namespace = runpy.run_path(str(target), run_name=f"alienbio_include_{target.stem}")
    return {k: v for k, v in namespace.items() if not k.startswith("__")}


def load_include(path: str, base: Path, *, trusted: bool, seen: frozenset[Path] = frozenset()) -> tuple[str, Any]:
    """Resolve one include: ``("yaml" | "text" | "py", value)``."""
    target = resolve_path(path, base, trusted=trusted)
    if target in seen:
        raise ExprError(f"!include cycle through {path!r}", str(base))
    if not target.is_file():
        raise ExprError(f"!include: no such file {path!r} (relative to {base})", str(base))
    suffix = target.suffix.lower()
    if suffix in YAML_SUFFIXES:
        from .yaml_tags import load_text

        data = load_text(target.read_text())
        return "yaml", hydrate(data, base=target.parent, trusted=trusted, seen=seen | {target})
    if suffix in TEXT_SUFFIXES:
        return "text", target.read_text()
    if suffix in PY_SUFFIXES:
        if not trusted:
            raise UnsafeSpecError(f"!include {path!r}: executing Python requires a trusted load")
        return "py", run_python_file(target)
    raise ExprError(f"!include {path!r}: unknown file kind {suffix!r} (yaml / yml / md / txt / py)", str(base))


def resolve_py(path: str, *, trusted: bool, modules: Optional[Mapping[str, Mapping[str, Any]]] = None) -> Any:
    """``module.attr`` -> the object: a module executed by ``_includes_`` /
    ``!include x.py`` (by its file stem) first, else the longest importable
    module prefix, then attributes."""
    if not trusted:
        raise UnsafeSpecError(f"!py {path!r}: a Python reference requires a trusted load")
    parts = path.split(".")
    if len(parts) < 2 or not all(p.isidentifier() for p in parts):
        raise ExprError(f"!py {path!r}: expected module.attr")
    if modules and parts[0] in modules:
        obj: Any = modules[parts[0]]
        for attr in parts[1:]:
            try:
                obj = obj[attr] if isinstance(obj, Mapping) else getattr(obj, attr)
            except (KeyError, AttributeError):
                raise ExprError(f"!py {path!r}: no {attr!r} in the included module {parts[0]!r}") from None
        return obj
    for i in range(len(parts) - 1, 0, -1):
        try:
            obj: Any = importlib.import_module(".".join(parts[:i]))
        except ImportError:
            continue
        for attr in parts[i:]:
            try:
                obj = getattr(obj, attr)
            except AttributeError:
                raise ExprError(f"!py {path!r}: no attribute {attr!r} on {'.'.join(parts[:i])}") from None
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
            modules[Path(entry).stem] = value
    return merged, modules


__all__ = ["UnsafeSpecError", "hydrate", "include_bindings", "load_include", "resolve_path", "resolve_py", "run_python_file"]
