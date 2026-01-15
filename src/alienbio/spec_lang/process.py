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

from .tags import EvTag, RefTag, IncludeTag, PyRef
from .loader import transform_typed_keys, expand_defaults


def process_and_hydrate(
    data: dict[str, Any], base_dir: str, *, hydrate: bool = True
) -> Any:
    """Process raw data through the full pipeline.

    Pipeline:
    1. Resolve !include tags (inline other files)
    2. Transform typed keys (key.Type: → key: {_type: Type, ...})
    3. Resolve !ref tags (cross-references)
    4. Resolve !py tags (local Python access)
    5. Expand defaults
    6. Hydrate to typed objects (if hydrate=True) — NOT YET IMPLEMENTED

    Args:
        data: Raw dict data to process
        base_dir: Directory for resolving relative includes
        hydrate: If True, convert to typed objects (not yet implemented)

    Returns:
        Processed data (dict or typed object when hydration implemented)
    """
    data = resolve_includes(data, base_dir)
    data = transform_typed_keys(data)
    data = resolve_refs(data, data.get("constants", {}))
    data = resolve_py_refs(data, base_dir)
    data = expand_defaults(data)

    # TODO: If hydrate=True, convert dicts with _type to typed objects

    return data


def resolve_includes(data: Any, base_dir: str) -> Any:
    """Recursively resolve IncludeTags in data.

    Args:
        data: Data structure potentially containing IncludeTag placeholders
        base_dir: Directory for resolving relative paths

    Returns:
        Data with IncludeTags replaced by loaded content
    """
    if isinstance(data, IncludeTag):
        return data.load(base_dir)
    elif isinstance(data, dict):
        return {k: resolve_includes(v, base_dir) for k, v in data.items()}
    elif isinstance(data, list):
        return [resolve_includes(item, base_dir) for item in data]
    return data


def resolve_refs(data: Any, constants: dict[str, Any]) -> Any:
    """Recursively resolve RefTags and EvTags in data.

    Args:
        data: Data structure potentially containing RefTag/EvTag placeholders
        constants: Dict of constant values for ref resolution

    Returns:
        Data with tags replaced by resolved values
    """
    if isinstance(data, RefTag):
        return data.resolve(constants)
    elif isinstance(data, EvTag):
        return data.evaluate(constants)
    elif isinstance(data, dict):
        # First resolve any EvTags in constants themselves
        if "constants" in data:
            resolved_constants = {}
            for k, v in data["constants"].items():
                if isinstance(v, EvTag):
                    resolved_constants[k] = v.evaluate(resolved_constants)
                else:
                    resolved_constants[k] = v
            data = {**data, "constants": resolved_constants}
            constants = resolved_constants

        return {k: resolve_refs(v, constants) for k, v in data.items()}
    elif isinstance(data, list):
        return [resolve_refs(item, constants) for item in data]
    return data


def resolve_py_refs(data: Any, base_dir: str) -> Any:
    """Recursively resolve PyRef tags in data.

    Args:
        data: Data structure potentially containing PyRef placeholders
        base_dir: Directory to resolve relative Python imports from

    Returns:
        Data with PyRef placeholders resolved to actual Python objects
    """
    if isinstance(data, PyRef):
        return data.resolve(base_dir)
    elif isinstance(data, dict):
        return {k: resolve_py_refs(v, base_dir) for k, v in data.items()}
    elif isinstance(data, list):
        return [resolve_py_refs(item, base_dir) for item in data]
    return data
