"""Generator context and spec loading for template-based generation.

Provides:
- GeneratorContext: Evaluation context for generator expressions
- eval_expr: Evaluate expression string in generator context
- load_generator_spec: Parse generator spec with guards and instantiations
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from ..spec_lang.eval import (
    Evaluable,
    eval_node,
    make_context,
    EvalContext,
)


class GeneratorContext:
    """Evaluation context for generator expressions.

    Wraps EvalContext with generator-specific function overrides
    (e.g., discrete with labeled choices, choice with varargs).
    """

    def __init__(self, seed: int = 0, bindings: dict[str, Any] | None = None):
        self._ctx = make_context(seed=seed, bindings=bindings)
        # Override functions with generator-specific versions
        self._ctx.functions["discrete"] = self._discrete
        self._ctx.functions["choice"] = self._choice

    @property
    def rng(self) -> np.random.Generator:
        return self._ctx.rng

    def _discrete(self, items: list, weights: list[float] | None = None, *, ctx: EvalContext) -> Any:
        """Discrete choice with optional labels.

        discrete(['a', 'b', 'c'], [0.5, 0.3, 0.2]) → one of 'a', 'b', 'c'
        discrete([0.5, 0.3, 0.2]) → index 0, 1, or 2
        """
        if weights is None:
            # Original behavior: items are weights, return index
            probs = np.array(items, dtype=float)
            probs = probs / probs.sum()
            return int(ctx.rng.choice(len(items), p=probs))
        else:
            # Extended behavior: items are labels, weights are probabilities
            probs = np.array(weights, dtype=float)
            probs = probs / probs.sum()
            idx = int(ctx.rng.choice(len(items), p=probs))
            return items[idx]

    def _choice(self, *options: Any, ctx: EvalContext) -> Any:
        """Choose uniformly from options (varargs or single list)."""
        if len(options) == 1 and isinstance(options[0], list):
            items = options[0]
        else:
            items = list(options)
        idx = ctx.rng.integers(0, len(items))
        return items[idx]


def eval_expr(source: str, ctx: GeneratorContext) -> Any:
    """Evaluate an expression string in a generator context.

    Args:
        source: Python expression string
        ctx: GeneratorContext with seed and functions

    Returns:
        Result of evaluating the expression
    """
    node = Evaluable(source=source)
    return eval_node(node, ctx._ctx)


@dataclass
class GeneratorSpec:
    """Parsed generator specification."""

    guards: list[Any] = field(default_factory=list)
    instantiate: dict[str, Any] = field(default_factory=dict)
    params: dict[str, Any] = field(default_factory=dict)
    visibility: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


def load_generator_spec(data: dict[str, Any]) -> GeneratorSpec:
    """Parse a generator spec dict (from YAML) into a GeneratorSpec.

    Handles the _guards_ section with multiple syntaxes:
    - Simple name: "no_new_cycles"
    - Name with params: {"max_pathway_length": {"max_length": 4}}
    - Full config: {"name": "no_new_cycles", "mode": "retry", "max_attempts": 10}

    Args:
        data: Raw dict from YAML, may have "scenario_generator_spec" wrapper

    Returns:
        Parsed GeneratorSpec
    """
    # Unwrap if nested under scenario_generator_spec
    if "scenario_generator_spec" in data:
        data = data["scenario_generator_spec"]

    guards_raw = data.get("_guards_", [])
    guards: list[Any] = []

    for item in guards_raw:
        if isinstance(item, str):
            # Simple guard name
            guards.append(item)
        elif isinstance(item, dict):
            if "name" in item:
                # Full config: {"name": ..., "mode": ..., "max_attempts": ...}
                guards.append(dict(item))
            else:
                # Name-with-params: {"max_pathway_length": {"max_length": 4}}
                for name, params in item.items():
                    guards.append({"name": name, "params": params})

    return GeneratorSpec(
        guards=guards,
        instantiate=data.get("_instantiate_", {}),
        params=data.get("_params_", {}),
        visibility=data.get("_visibility_", {}),
        metadata=data.get("_metadata_", {}),
    )
