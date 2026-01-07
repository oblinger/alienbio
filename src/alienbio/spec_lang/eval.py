"""Spec evaluation system.

Placeholder classes and evaluation functions for the spec language.
See [[Spec Evaluation]] for full specification.

Tags:
    !_      - Evaluate Python expression immediately (becomes Evaluable)
    !quote  - Preserve expression unchanged (becomes Quoted)
    !ref    - Reference named value (becomes Reference)
    !include - Include file content (handled during hydration)

Pipeline:
    YAML → fetch → dict_tree → hydrate → object_tree → eval → result
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import yaml


# =============================================================================
# Placeholder Classes (M1.8b)
# =============================================================================


@dataclass
class Evaluable:
    """Placeholder for !_ expressions.

    Created during hydration when a !_ tag is encountered.
    Evaluated later by eval_node() to produce a concrete value.

    Example:
        YAML: count: !_ normal(50, 10)
        After hydrate: {"count": Evaluable(source="normal(50, 10)")}
        After eval: {"count": 47.3}  # sampled value
    """

    source: str

    def __repr__(self) -> str:
        return f"Evaluable({self.source!r})"


@dataclass
class Quoted:
    """Placeholder for !quote expressions.

    Created during hydration when a !quote tag is encountered.
    Preserved through evaluation - returns the source string unchanged.
    Used for rate expressions that get compiled at simulator creation time.

    Example:
        YAML: rate: !quote k * S
        After hydrate: {"rate": Quoted(source="k * S")}
        After eval: {"rate": "k * S"}  # preserved as string
    """

    source: str

    def __repr__(self) -> str:
        return f"Quoted({self.source!r})"


@dataclass
class Reference:
    """Placeholder for !ref expressions.

    Created during hydration when a !ref tag is encountered.
    Resolved during evaluation by looking up the name in ctx.bindings.

    Example:
        YAML: permeability: !ref high_permeability
        After hydrate: {"permeability": Reference(name="high_permeability")}
        After eval: {"permeability": 0.8}  # looked up from bindings
    """

    name: str

    def __repr__(self) -> str:
        return f"Reference({self.name!r})"


# =============================================================================
# YAML Constructors
# =============================================================================


def evaluable_constructor(loader: yaml.Loader, node: yaml.Node) -> Evaluable:
    """YAML constructor for !_ tag."""
    value = loader.construct_scalar(node)  # type: ignore
    return Evaluable(source=str(value))


def quoted_constructor(loader: yaml.Loader, node: yaml.Node) -> Quoted:
    """YAML constructor for !quote tag."""
    value = loader.construct_scalar(node)  # type: ignore
    return Quoted(source=str(value))


def reference_constructor(loader: yaml.Loader, node: yaml.Node) -> Reference:
    """YAML constructor for !ref tag (new style)."""
    value = loader.construct_scalar(node)  # type: ignore
    return Reference(name=str(value))


def register_eval_tags() -> None:
    """Register evaluation YAML tags with the loader."""
    yaml.add_constructor("!_", evaluable_constructor, Loader=yaml.SafeLoader)
    yaml.add_constructor("!quote", quoted_constructor, Loader=yaml.SafeLoader)
    # Note: !ref is also registered in tags.py as RefTag
    # We register Reference here for the new evaluation system
    # Both can coexist - the last registration wins for SafeLoader


# Register tags on module import
register_eval_tags()


# =============================================================================
# Hydration (M1.8c)
# =============================================================================


def hydrate(data: Any, base_path: str | None = None) -> Any:
    """Convert dict structure to Python objects with placeholders.

    Transforms:
        {"!_": source} → Evaluable(source)
        {"!quote": source} → Quoted(source)
        {"!ref": name} → Reference(name)
        {"!include": path} → file contents (recursively hydrated)

    Also handles:
        - Recursive descent into dicts and lists
        - YAML tag objects (Evaluable, Quoted, Reference) pass through unchanged
        - EvTag, RefTag, IncludeTag from legacy system are converted

    Args:
        data: The data structure to hydrate
        base_path: Base directory for resolving !include paths

    Returns:
        Hydrated data with placeholders

    Raises:
        FileNotFoundError: If !include file doesn't exist
    """
    return _hydrate_node(data, base_path)


def _hydrate_node(node: Any, base_path: str | None) -> Any:
    """Recursively hydrate a single node."""
    from pathlib import Path

    # Already a placeholder - pass through
    if isinstance(node, (Evaluable, Quoted, Reference)):
        return node

    # Legacy tag objects - convert to new placeholders
    from .tags import EvTag, RefTag, IncludeTag

    if isinstance(node, EvTag):
        return Evaluable(source=node.expr)

    if isinstance(node, RefTag):
        return Reference(name=node.name)

    if isinstance(node, IncludeTag):
        return _hydrate_include(node.path, base_path)

    # Dict - check for special keys or recurse
    if isinstance(node, dict):
        return _hydrate_dict(node, base_path)

    # List - recurse into elements
    if isinstance(node, list):
        return [_hydrate_node(item, base_path) for item in node]

    # Scalar values (int, float, str, bool, None) - pass through
    return node


def _hydrate_dict(d: dict, base_path: str | None) -> Any:
    """Hydrate a dict, checking for special tag keys."""
    # Single-key dicts with special tags
    if len(d) == 1:
        key = next(iter(d))
        value = d[key]

        if key == "!_":
            return Evaluable(source=str(value))

        if key == "!quote":
            return Quoted(source=str(value))

        if key == "!ref":
            return Reference(name=str(value))

        if key == "!include":
            return _hydrate_include(str(value), base_path)

    # Regular dict - recurse into values
    return {k: _hydrate_node(v, base_path) for k, v in d.items()}


def _hydrate_include(path: str, base_path: str | None) -> Any:
    """Load and hydrate an included file."""
    from pathlib import Path

    # Resolve file path
    if Path(path).is_absolute():
        file_path = Path(path)
    elif base_path:
        file_path = Path(base_path) / path
    else:
        file_path = Path(path)

    file_path = file_path.resolve()

    if not file_path.exists():
        raise FileNotFoundError(f"Include file not found: {file_path}")

    # Load based on file extension
    suffix = file_path.suffix.lower()

    if suffix == ".md":
        # Markdown files return as string
        return file_path.read_text()

    elif suffix in (".yaml", ".yml"):
        # YAML files are parsed and recursively hydrated
        content = file_path.read_text()
        data = yaml.safe_load(content)
        return _hydrate_node(data, str(file_path.parent))

    else:
        # Default: return raw text
        return file_path.read_text()


# =============================================================================
# Dehydration (M1.8d)
# =============================================================================


def dehydrate(data: Any) -> Any:
    """Convert Python objects back to serializable dict structure.

    Transforms:
        Evaluable(source) → {"!_": source}
        Quoted(source) → {"!quote": source}
        Reference(name) → {"!ref": name}

    Also handles:
        - Recursive descent into dicts and lists
        - Constants (int, float, str, bool, None) pass through unchanged

    Round-trip property: dehydrate(hydrate(x)) ≈ x

    Args:
        data: The data structure to dehydrate

    Returns:
        Serializable dict structure
    """
    return _dehydrate_node(data)


def _dehydrate_node(node: Any) -> Any:
    """Recursively dehydrate a single node."""
    # Placeholder classes → dict format
    if isinstance(node, Evaluable):
        return {"!_": node.source}

    if isinstance(node, Quoted):
        return {"!quote": node.source}

    if isinstance(node, Reference):
        return {"!ref": node.name}

    # Dict → recurse into values
    if isinstance(node, dict):
        return {k: _dehydrate_node(v) for k, v in node.items()}

    # List → recurse into elements
    if isinstance(node, list):
        return [_dehydrate_node(item) for item in node]

    # Scalar values (int, float, str, bool, None) → pass through
    return node
