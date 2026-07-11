"""Data processing pipeline for Bio.fetch().

Pure functions for transforming loaded YAML data:
- Resolve !include tags
- Resolve !ref tags
- Resolve !py tags
- Expand defaults
- Hydrate to typed objects (future)
"""

from __future__ import annotations

from typing import Any

from .eval import Evaluable, Reference
from .tags import Include, PyRef, UnsafeSpecError
from .loader import transform_typed_keys, expand_defaults


def process_and_hydrate(
    data: dict[str, Any], base_dir: str, *, hydrate: bool = True, trusted: bool = False
) -> Any:
    """Process raw data through the full pipeline.

    Pipeline:
    0. Execute Python includes (register decorators)
    1. Resolve !include tags (inline other files)
    2. Transform typed keys (key.Type: → key: {_type: Type, ...})
    3. Resolve !ref tags (cross-references)
    4. Resolve !py tags (local Python access)
    5. Expand defaults
    6. Hydrate to typed objects (if hydrate=True)

    Args:
        data: Raw dict data to process
        base_dir: Directory for resolving relative includes
        hydrate: If True, convert to typed objects
        trusted: Must be True to allow executing Python from the spec
            (``include:`` .py files, ``!py`` tags). Defaults to False — the
            secure default for agent-authored specs.

    Returns:
        Processed data (dict or typed object when hydration implemented)
    """
    # Execute Python includes first (so decorators register before evaluation)
    if isinstance(data, dict) and "include" in data:
        _process_python_includes(data.get("include", []), base_dir, trusted=trusted)
        data = {k: v for k, v in data.items() if k != "include"}

    data = resolve_includes(data, base_dir, trusted=trusted)
    data = transform_typed_keys(data)
    data = resolve_refs(data, data.get("constants", {}))
    data = resolve_py_refs(data, base_dir, trusted=trusted)
    data = expand_defaults(data)

    if not hydrate:
        from .scope import Scope
        return Scope(data)

    return data


def resolve_includes(data: Any, base_dir: str, *, trusted: bool = False) -> Any:
    """Recursively resolve Include placeholders in data.

    Args:
        data: Data structure potentially containing Include placeholders
        base_dir: Directory for resolving relative paths
        trusted: Passed to Include.load — gates .py execution and lifts the
            path-containment restriction on .md/.yaml includes. Defaults to
            False (untrusted).

    Returns:
        Data with Includes replaced by loaded content
    """
    if isinstance(data, Include):
        return data.load(base_dir, trusted=trusted)
    elif isinstance(data, dict):
        return {k: resolve_includes(v, base_dir, trusted=trusted) for k, v in data.items()}
    elif isinstance(data, list):
        return [resolve_includes(item, base_dir, trusted=trusted) for item in data]
    return data


def resolve_refs(data: Any, constants: dict[str, Any]) -> Any:
    """Recursively resolve Reference and Evaluable placeholders in data.

    Args:
        data: Data structure potentially containing Reference/Evaluable placeholders
        constants: Dict of constant values for ref resolution

    Returns:
        Data with placeholders replaced by resolved values
    """
    if isinstance(data, Reference):
        return data.resolve(constants)
    elif isinstance(data, Evaluable):
        return data.evaluate(constants)
    elif isinstance(data, dict):
        # First resolve any Evaluables in constants themselves
        if "constants" in data:
            resolved_constants = {}
            for k, v in data["constants"].items():
                if isinstance(v, Evaluable):
                    resolved_constants[k] = v.evaluate(resolved_constants)
                else:
                    resolved_constants[k] = v
            data = {**data, "constants": resolved_constants}
            constants = resolved_constants

        return {k: resolve_refs(v, constants) for k, v in data.items()}
    elif isinstance(data, list):
        return [resolve_refs(item, constants) for item in data]
    return data


def resolve_py_refs(data: Any, base_dir: str, *, trusted: bool = False) -> Any:
    """Recursively resolve PyRef tags in data.

    Args:
        data: Data structure potentially containing PyRef placeholders
        base_dir: Directory to resolve relative Python imports from
        trusted: Must be True to execute the referenced Python (``!py`` runs
            arbitrary code). Defaults to False (untrusted) — PyRef.resolve then
            raises UnsafeSpecError.

    Returns:
        Data with PyRef placeholders resolved to actual Python objects
    """
    if isinstance(data, PyRef):
        return data.resolve(base_dir, trusted=trusted)
    elif isinstance(data, dict):
        return {k: resolve_py_refs(v, base_dir, trusted=trusted) for k, v in data.items()}
    elif isinstance(data, list):
        return [resolve_py_refs(item, base_dir, trusted=trusted) for item in data]
    return data


def _process_python_includes(includes: Any, base_dir: str, *, trusted: bool = False) -> None:
    """Execute Python include files to register decorators.

    Executes .py files listed in the `include:` section of a spec.
    This allows specs to define custom @rate, @scoring, @action,
    and @measurement functions that register into the global registries.

    Security: a top-level ``include:`` entry ending in ``.py`` is executed via
    ``exec_module`` — full arbitrary code execution. Agent-authored specs are
    untrusted, so this is gated behind ``trusted=True`` (the same pattern used
    for ``!py`` and ``.py`` ``!include``). Under the default (untrusted) an
    ``include:`` naming a ``.py`` file raises ``UnsafeSpecError`` before any
    code runs.

    Args:
        includes: List of include file paths
        base_dir: Directory for resolving relative paths
        trusted: Must be True to execute the listed .py files. Defaults to
            False (untrusted).
    """
    from pathlib import Path
    import importlib.util

    if not isinstance(includes, list):
        return

    for include_path in includes:
        if not isinstance(include_path, str) or not include_path.endswith(".py"):
            continue
        if not trusted:
            raise UnsafeSpecError(
                f"include: '{include_path}' executes Python code and is disabled "
                f"for untrusted specs. Pass trusted=True to enable (local dev only)."
            )
        full_path = (Path(base_dir) / include_path).resolve()
        if not full_path.exists():
            raise FileNotFoundError(f"Python include not found: {full_path}")
        spec = importlib.util.spec_from_file_location(full_path.stem, str(full_path))
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
