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

from dataclasses import dataclass, field
from typing import Any, Callable

import yaml
import numpy as np


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


# =============================================================================
# Context (M1.8e)
# =============================================================================


# Safe builtins allowed in expressions
SAFE_BUILTINS: dict[str, Any] = {
    # Math functions
    "min": min,
    "max": max,
    "abs": abs,
    "round": round,
    "sum": sum,
    "len": len,
    "pow": pow,
    # Type conversions
    "int": int,
    "float": float,
    "str": str,
    "bool": bool,
    # Collections
    "list": list,
    "dict": dict,
    "tuple": tuple,
    "set": set,
    # Iterators
    "range": range,
    "zip": zip,
    "enumerate": enumerate,
    "sorted": sorted,
    "reversed": reversed,
    "map": map,
    "filter": filter,
    # Constants
    "True": True,
    "False": False,
    "None": None,
}


@dataclass
class Context:
    """Evaluation context with rng, bindings, functions, path.

    Carries all state needed during spec evaluation:
    - rng: seeded numpy RNG for reproducibility
    - bindings: dict of variable name → value
    - functions: dict of registered @function handlers
    - path: list of keys for error messages (e.g., ["scenario", "molecules", "count"])

    Example:
        ctx = Context(rng=np.random.default_rng(42))
        ctx = ctx.child(bindings={"pi": 3.14159})
        result = eval_node(spec, ctx)
    """

    rng: np.random.Generator = field(default_factory=lambda: np.random.default_rng(42))
    bindings: dict[str, Any] = field(default_factory=dict)
    functions: dict[str, Callable] = field(default_factory=dict)
    path: list[str] = field(default_factory=list)

    def child(self, **kwargs) -> "Context":
        """Create child context with additional/overridden attributes.

        Child context inherits from parent but can shadow bindings.
        RNG is shared (not copied) for consistent random sequences.

        Args:
            **kwargs: Attributes to override. Special handling for 'bindings'
                      which merges with parent bindings.

        Returns:
            New Context with merged bindings and other attributes.
        """
        # Merge bindings (child shadows parent)
        new_bindings = {**self.bindings, **kwargs.pop("bindings", {})}

        # Copy other attributes, using kwargs overrides
        return Context(
            rng=kwargs.get("rng", self.rng),
            bindings=new_bindings,
            functions=kwargs.get("functions", self.functions),
            path=kwargs.get("path", self.path),
        )

    def with_path(self, key: str) -> "Context":
        """Create child context with extended path for error messages.

        Args:
            key: Key to append to path.

        Returns:
            New Context with extended path.
        """
        return Context(
            rng=self.rng,
            bindings=self.bindings,
            functions=self.functions,
            path=[*self.path, key],
        )


# =============================================================================
# Evaluation (M1.8f)
# =============================================================================


class EvalError(Exception):
    """Error during spec evaluation."""

    def __init__(self, message: str, path: list[str] | None = None):
        self.path = path or []
        path_str = ".".join(self.path) if self.path else "<root>"
        super().__init__(f"{message} (at {path_str})")


def eval_node(node: Any, ctx: Context, strict: bool = True) -> Any:
    """Evaluate a hydrated node.

    Transforms:
        Constants (str, int, float, bool, None) → return as-is
        Evaluable(source) → Python eval(source, namespace)
        Quoted(source) → return source string unchanged
        Reference(name) → lookup in ctx.bindings
        dict → recursively eval values
        list → recursively eval elements

    Args:
        node: The hydrated data structure to evaluate
        ctx: Evaluation context with rng, bindings, functions
        strict: If True, raise error for missing references.
                If False, return Reference unchanged.

    Returns:
        Evaluated data structure with all placeholders resolved.

    Raises:
        EvalError: If evaluation fails (e.g., missing reference in strict mode)
    """
    return _eval_node(node, ctx, strict)


def _eval_node(node: Any, ctx: Context, strict: bool) -> Any:
    """Recursively evaluate a single node."""
    # Quoted → return source string unchanged
    if isinstance(node, Quoted):
        return node.source

    # Evaluable → evaluate Python expression
    if isinstance(node, Evaluable):
        return _eval_expression(node.source, ctx)

    # Reference → lookup in bindings
    if isinstance(node, Reference):
        return _eval_reference(node, ctx, strict)

    # Dict → recursively eval values
    if isinstance(node, dict):
        return {k: _eval_node(v, ctx.with_path(k), strict) for k, v in node.items()}

    # List → recursively eval elements
    if isinstance(node, list):
        return [_eval_node(item, ctx.with_path(str(i)), strict) for i, item in enumerate(node)]

    # Constants (int, float, str, bool, None) → return as-is
    return node


def _eval_expression(source: str, ctx: Context) -> Any:
    """Evaluate a Python expression string.

    Builds namespace from:
    - SAFE_BUILTINS (min, max, abs, etc.)
    - ctx.bindings (user variables)
    - ctx.functions (registered @function handlers)

    Args:
        source: Python expression to evaluate
        ctx: Evaluation context

    Returns:
        Result of evaluating the expression

    Raises:
        EvalError: If expression fails to evaluate
    """
    # Build evaluation namespace
    namespace = {
        **SAFE_BUILTINS,
        **ctx.bindings,
        **ctx.functions,
    }

    try:
        return eval(source, {"__builtins__": {}}, namespace)
    except NameError as e:
        raise EvalError(f"Undefined variable in expression '{source}': {e}", ctx.path) from e
    except SyntaxError as e:
        raise EvalError(f"Syntax error in expression '{source}': {e}", ctx.path) from e
    except Exception as e:
        raise EvalError(f"Error evaluating expression '{source}': {e}", ctx.path) from e


def _eval_reference(ref: Reference, ctx: Context, strict: bool) -> Any:
    """Resolve a reference from bindings.

    Args:
        ref: Reference to resolve
        ctx: Evaluation context with bindings
        strict: If True, raise error for missing reference

    Returns:
        The referenced value, or the Reference unchanged if non-strict

    Raises:
        EvalError: If reference not found and strict=True
    """
    if ref.name in ctx.bindings:
        return ctx.bindings[ref.name]

    if strict:
        raise EvalError(f"Reference '{ref.name}' not found in bindings", ctx.path)

    # Non-strict mode: return Reference unchanged
    return ref
