"""Spec loading and transformation functions."""

from __future__ import annotations
from typing import Any
import copy


def transform_typed_keys(data: dict[str, Any], type_registry: set[str] | None = None) -> dict[str, Any]:
    """Transform type.name keys to nested structure with _type field.

    Args:
        data: Dict with keys like "world.foo", "suite.bar"
        type_registry: Set of known type names (default: built-in types)

    Returns:
        Transformed dict with _type fields

    Example:
        {"world.foo": {"molecules": {}}}
        becomes:
        {"foo": {"_type": "world", "molecules": {}}}
    """
    if type_registry is None:
        type_registry = {"world", "suite", "scenario", "chemistry", "spec"}

    result: dict[str, Any] = {}

    for key, value in data.items():
        if "." in key and isinstance(value, dict):
            type_name, rest = key.split(".", 1)

            if type_name in type_registry:
                # Recursively transform nested typed keys in value
                transformed_value = transform_typed_keys(value, type_registry)

                # Add _type field
                transformed_value = {"_type": type_name, **transformed_value}

                # Store under the rest of the name
                result[rest] = transformed_value
            else:
                # Not a known type, keep as-is but still recurse
                result[key] = transform_typed_keys(value, type_registry)
        elif isinstance(value, dict):
            # Recurse into non-typed dicts
            result[key] = transform_typed_keys(value, type_registry)
        else:
            result[key] = value

    return result


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Deep merge two dicts, with override taking precedence.

    Args:
        base: Base dict
        override: Dict to merge on top

    Returns:
        Merged dict (new copy, inputs unchanged)

    Rules:
        - Dicts are deep-merged
        - null (~) removes the key
        - All other values replace
    """
    result = copy.deepcopy(base)

    for key, value in override.items():
        if value is None:
            # Explicit null removes the key
            result.pop(key, None)
        elif isinstance(value, dict) and isinstance(result.get(key), dict):
            # Deep merge dicts
            result[key] = deep_merge(result[key], value)
        else:
            # Replace value
            result[key] = copy.deepcopy(value)

    return result


def expand_defaults(data: dict[str, Any]) -> dict[str, Any]:
    """Expand defaults through suite/scenario hierarchy.

    Args:
        data: Dict with suite/scenario structure and defaults

    Returns:
        Data with defaults expanded into each scenario
    """
    raise NotImplementedError("expand_defaults not yet implemented")


def load_spec(path: str) -> dict[str, Any]:
    """Load and process a spec file.

    Args:
        path: Path to YAML spec file

    Returns:
        Fully processed spec with types transformed, defaults expanded,
        refs resolved, and includes loaded

    Raises:
        FileNotFoundError: If path doesn't exist
    """
    raise NotImplementedError("load_spec not yet implemented")
