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
        type_registry = {"suite", "scenario"}

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


def expand_defaults(data: dict[str, Any], inherited_defaults: dict[str, Any] | None = None) -> dict[str, Any]:
    """Expand defaults through suite/scenario hierarchy.

    Args:
        data: Dict with suite/scenario structure and defaults
        inherited_defaults: Defaults inherited from parent suites

    Returns:
        Data with defaults expanded into each scenario
    """
    result = copy.deepcopy(data)
    inherited = inherited_defaults or {}

    def process_node(node: dict[str, Any], parent_defaults: dict[str, Any]) -> dict[str, Any]:
        """Process a single node, applying defaults to scenarios."""
        if not isinstance(node, dict):
            return node

        node_type = node.get("_type")

        if node_type == "suite":
            # Get this suite's defaults, merged with inherited
            suite_defaults = node.get("defaults", {})
            combined_defaults = deep_merge(parent_defaults, suite_defaults)

            # Process all children
            new_node = {}
            for key, value in node.items():
                if key in ("_type", "defaults"):
                    new_node[key] = value
                elif isinstance(value, dict):
                    new_node[key] = process_node(value, combined_defaults)
                else:
                    new_node[key] = value
            return new_node

        elif node_type == "scenario":
            # Apply defaults to scenario (defaults first, then scenario values)
            scenario_values = {k: v for k, v in node.items() if k != "_type"}
            merged = deep_merge(parent_defaults, scenario_values)
            merged["_type"] = "scenario"
            return merged

        else:
            # Not a suite or scenario - recurse into children
            new_node = {}
            for key, value in node.items():
                if isinstance(value, dict):
                    new_node[key] = process_node(value, parent_defaults)
                else:
                    new_node[key] = value
            return new_node

    # Process top-level items
    for key, value in result.items():
        if isinstance(value, dict):
            result[key] = process_node(value, inherited)

    return result


