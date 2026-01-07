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
