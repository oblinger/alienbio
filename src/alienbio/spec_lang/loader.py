"""Spec loading and transformation functions (the suite/scenario defaults
expansion; the ``type.name:`` typed-key convention was retired in M47.6)."""

from __future__ import annotations
from typing import Any
import copy


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Deep merge two dicts, with override taking precedence.

    Args:
        base: Base dict
        override: Dict to merge on top

    Returns:
        Merged dict (new copy, inputs unchanged)

    Rules:
        - Dicts are deep-merged
        - null (~) removes the key — consistently, at *every* nesting level.
          A None value in an override never survives as a literal null: if a
          matching key exists it is removed; if none exists it is simply
          omitted. This holds whether the override dict is merged onto an
          existing dict or placed fresh where the base had a non-dict/absent
          value (previously the "replace" branch copied nested nulls verbatim).
        - All other values replace
    """
    result = copy.deepcopy(base)

    for key, value in override.items():
        if value is None:
            # Explicit null removes the key.
            result.pop(key, None)
        elif isinstance(value, dict):
            if isinstance(result.get(key), dict):
                # Deep merge dicts (nested None removes from the base).
                result[key] = deep_merge(result[key], value)
            else:
                # Fresh dict (no base dict to merge onto). Merge onto an empty
                # base so nested None still means "remove" — i.e. is dropped
                # rather than stored as a literal null.
                result[key] = deep_merge({}, value)
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


