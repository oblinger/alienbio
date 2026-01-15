"""Spec evaluation system.

Placeholder classes and evaluation functions for the spec language.
See [[Spec Evaluation]] for full specification.

Tags:
    !_      - Preserve expression as-is (becomes Quoted) - for rate equations, lambdas
    !ev     - Evaluate expression at instantiation time (becomes Evaluable)
    !quote  - Alias for !_ (preserve expression unchanged)
    !ref    - Reference named value (becomes Reference)
    !include - Include file content (handled during hydration)

Design rationale:
    Most expressions in specs are "code" - rate equations, scoring functions -
    that shouldn't run at hydration. They're lambdas waiting to be compiled or
    called later. So !_ (the short form) preserves them as structure.

    The rarer case - "actually compute this now" - gets the more explicit !ev.

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
    """Placeholder for !ev expressions - evaluated at instantiation time.

    Created during hydration when a !ev tag is encountered.
    Evaluated by eval_node() to produce a concrete value.

    Use !ev for values that should be computed when the spec is instantiated,
    such as random samples, computed parameters, etc.

    Example:
        YAML: count: !ev normal(50, 10)
        After hydrate: {"count": Evaluable(source="normal(50, 10)")}
        After eval: {"count": 47.3}  # sampled value
    """

    source: str

    def __repr__(self) -> str:
        return f"Evaluable({self.source!r})"

    @property
    def expr(self) -> str:
        """Alias for source (backward compat with EvTag)."""
        return self.source

    def evaluate(self, namespace: dict[str, Any] | None = None) -> Any:
        """Evaluate the expression in a sandboxed namespace.

        Args:
            namespace: Dict of names available during evaluation

        Returns:
            Result of evaluating the expression
        """
        ns = namespace or {}
        blocked = {"open", "exec", "eval", "__import__", "compile", "globals", "locals"}
        builtins = __builtins__ if isinstance(__builtins__, dict) else vars(__builtins__)
        safe_builtins = {k: v for k, v in builtins.items() if k not in blocked}
        eval_ns = {"__builtins__": safe_builtins, **ns}
        return eval(self.source, eval_ns)


@dataclass
class Quoted:
    """Placeholder for !_ expressions - preserved as expression strings.

    Created during hydration when a !_ or !quote tag is encountered.
    Preserved through evaluation - returns the source string unchanged.
    Used for rate equations, scoring functions, and other "code" that
    gets compiled or called later (not at instantiation time).

    The !_ tag is the common case - most expressions in specs are lambdas.

    Example:
        YAML: rate: !_ k * S
        After hydrate: {"rate": Quoted(source="k * S")}
        After eval: {"rate": "k * S"}  # preserved for later compilation
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

    def resolve(self, constants: dict[str, Any]) -> Any:
        """Resolve the reference from a constants dict.

        Supports dotted paths like "settings.threshold".

        Args:
            constants: Dict of named values to look up in

        Returns:
            The resolved value

        Raises:
            KeyError: If name not found in constants
        """
        parts = self.name.split(".")
        value: Any = constants
        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                raise KeyError(f"Cannot resolve reference: {self.name}")
        return value


# =============================================================================
# YAML Constructors
# =============================================================================


def quoted_constructor(loader: yaml.Loader, node: yaml.Node) -> Quoted:
    """YAML constructor for !_ and !quote tags - preserves expression."""
    value = loader.construct_scalar(node)  # type: ignore
    return Quoted(source=str(value))


def evaluable_constructor(loader: yaml.Loader, node: yaml.Node) -> Evaluable:
    """YAML constructor for !ev tag - evaluates at instantiation."""
    value = loader.construct_scalar(node)  # type: ignore
    return Evaluable(source=str(value))


def reference_constructor(loader: yaml.Loader, node: yaml.Node) -> Reference:
    """YAML constructor for !ref tag."""
    value = loader.construct_scalar(node)  # type: ignore
    return Reference(name=str(value))


def register_eval_tags() -> None:
    """Register evaluation YAML tags with the loader.

    Tags:
        !_     → Quoted (preserve expression for later compilation)
        !quote → Quoted (alias for !_)
        !ev    → Evaluable (evaluate at instantiation time)
        !ref   → Reference (lookup in bindings)
    """
    yaml.add_constructor("!_", quoted_constructor, Loader=yaml.SafeLoader)
    yaml.add_constructor("!quote", quoted_constructor, Loader=yaml.SafeLoader)
    yaml.add_constructor("!ev", evaluable_constructor, Loader=yaml.SafeLoader)
    yaml.add_constructor("!ref", reference_constructor, Loader=yaml.SafeLoader)


# Register tags on module import
register_eval_tags()


# =============================================================================
# Hydration (M1.8c)
# =============================================================================


def hydrate(data: Any, base_path: str | None = None) -> Any:
    """Convert dict structure to Python objects with placeholders.

    Transforms:
        {"!_": source} → Quoted(source)       (preserve expression)
        {"!ev": source} → Evaluable(source)   (evaluate at instantiation)
        {"!ref": name} → Reference(name)      (lookup in bindings)
        {"!include": path} → file contents    (recursively hydrated)

    Also handles:
        - Recursive descent into dicts and lists
        - YAML tag objects (Evaluable, Quoted, Reference, Include) pass through
        - Include objects are loaded and their contents hydrated

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
    from .tags import Include

    # Already a placeholder - pass through unchanged
    if isinstance(node, (Evaluable, Quoted, Reference)):
        return node

    # Include placeholder - load and hydrate the file contents
    if isinstance(node, Include):
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
            return Quoted(source=str(value))  # Preserve expression

        if key == "!quote":
            return Quoted(source=str(value))  # Alias for !_

        if key == "!ev":
            return Evaluable(source=str(value))  # Evaluate at instantiation

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

    Inverse of hydrate() - converts placeholder objects back to their
    dict representation for YAML serialization.

    Transforms:
        Evaluable(source) → {"!ev": source}  (evaluate at instantiation)
        Quoted(source) → {"!_": source}      (preserve expression)
        Reference(name) → {"!ref": name}

    Args:
        data: The data structure to dehydrate

    Returns:
        Dehydrated data suitable for YAML serialization
    """
    return _dehydrate_node(data)


def _dehydrate_node(node: Any) -> Any:
    """Recursively dehydrate a single node."""
    # Placeholder objects - convert to dict representation
    if isinstance(node, Evaluable):
        return {"!ev": node.source}

    if isinstance(node, Quoted):
        return {"!_": node.source}

    if isinstance(node, Reference):
        return {"!ref": node.name}

    # Dict - recurse into values
    if isinstance(node, dict):
        return {k: _dehydrate_node(v) for k, v in node.items()}

    # List - recurse into elements
    if isinstance(node, list):
        return [_dehydrate_node(item) for item in node]

    # Scalar values (int, float, str, bool, None) - pass through
    return node


# =============================================================================
# Evaluation Context (M1.8e)
# =============================================================================


# Safe builtins for expression evaluation
SAFE_BUILTINS: dict[str, Any] = {
    "abs": abs,
    "all": all,
    "any": any,
    "bool": bool,
    "dict": dict,
    "float": float,
    "int": int,
    "len": len,
    "list": list,
    "max": max,
    "min": min,
    "pow": pow,
    "range": range,
    "round": round,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "zip": zip,
    "True": True,
    "False": False,
    "None": None,
}


class EvalError(Exception):
    """Error during spec evaluation."""

    def __init__(self, message: str, path: str = ""):
        self.path = path
        super().__init__(f"{path}: {message}" if path else message)


@dataclass
class EvalContext:
    """Evaluation context for spec evaluation.

    Carries state through the recursive evaluation process:
    - rng: Random number generator for reproducible sampling
    - bindings: Named values for !ref resolution
    - functions: Callable functions available to !_ expressions
    - path: Current location in the tree for error messages

    Example:
        ctx = EvalContext(
            rng=np.random.default_rng(42),
            bindings={"k": 0.5, "permeability": 0.8},
            functions={"normal": normal, "uniform": uniform}
        )
        result = eval_node(hydrated_spec, ctx)
    """

    rng: np.random.Generator = field(default_factory=np.random.default_rng)
    bindings: dict[str, Any] = field(default_factory=dict)
    functions: dict[str, Callable[..., Any]] = field(default_factory=dict)
    path: str = ""

    def child(self, key: str | int) -> "EvalContext":
        """Create child context with extended path."""
        new_path = f"{self.path}.{key}" if self.path else str(key)
        return EvalContext(
            rng=self.rng,
            bindings=self.bindings,
            functions=self.functions,
            path=new_path,
        )


# Backward compatibility alias
Context = EvalContext


# =============================================================================
# Evaluation (M1.8f)
# =============================================================================


def eval_node(node: Any, ctx: EvalContext) -> Any:
    """Recursively evaluate a hydrated spec node.

    Processes placeholder objects:
        Evaluable → execute expression and return result
        Quoted → return source string unchanged
        Reference → look up in ctx.bindings

    Recursively evaluates:
        dict → evaluate all values
        list → evaluate all elements

    Passes through:
        Scalar values (int, float, str, bool, None)

    Args:
        node: The hydrated node to evaluate
        ctx: Evaluation context

    Returns:
        Fully evaluated value

    Raises:
        EvalError: If evaluation fails (undefined reference, syntax error, etc.)
    """
    # Evaluable - execute the expression
    if isinstance(node, Evaluable):
        return _eval_expression(node.source, ctx)

    # Quoted - return the source string unchanged
    if isinstance(node, Quoted):
        return node.source

    # Reference - look up in bindings
    if isinstance(node, Reference):
        if node.name not in ctx.bindings:
            raise EvalError(f"Undefined reference: {node.name!r}", ctx.path)
        return ctx.bindings[node.name]

    # Dict - recurse into values
    if isinstance(node, dict):
        return {k: eval_node(v, ctx.child(k)) for k, v in node.items()}

    # List - recurse into elements
    if isinstance(node, list):
        return [eval_node(item, ctx.child(i)) for i, item in enumerate(node)]

    # Scalar values - pass through
    return node


def _eval_expression(source: str, ctx: EvalContext) -> Any:
    """Evaluate a Python expression in a sandboxed environment.

    The expression has access to:
    - SAFE_BUILTINS (abs, min, max, etc.)
    - ctx.bindings (named values)
    - ctx.functions (wrapped with auto-injected ctx)

    Args:
        source: Python expression string
        ctx: Evaluation context

    Returns:
        Result of evaluating the expression

    Raises:
        EvalError: If expression is invalid or evaluation fails
    """
    # Build namespace with safe builtins
    namespace: dict[str, Any] = dict(SAFE_BUILTINS)

    # Add bindings
    namespace.update(ctx.bindings)

    # Add functions with auto-injected ctx
    for name, func in ctx.functions.items():
        namespace[name] = _wrap_function(func, ctx)

    try:
        # Compile to detect syntax errors early
        code = compile(source, "<spec>", "eval")
        return eval(code, {"__builtins__": {}}, namespace)
    except SyntaxError as e:
        raise EvalError(f"Syntax error in expression {source!r}: {e}", ctx.path)
    except NameError as e:
        raise EvalError(f"Name error in expression {source!r}: {e}", ctx.path)
    except Exception as e:
        raise EvalError(f"Error evaluating {source!r}: {e}", ctx.path)


# =============================================================================
# Function Injection (M1.8g)
# =============================================================================


def _wrap_function(func: Callable[..., Any], ctx: EvalContext) -> Callable[..., Any]:
    """Wrap a function to auto-inject ctx as keyword argument.

    Allows spec functions to receive the evaluation context without
    the expression author having to pass it explicitly.

    Example:
        def normal(mean, std, *, ctx):
            return ctx.rng.normal(mean, std)

        wrapped = _wrap_function(normal, ctx)
        wrapped(10, 2)  # ctx is auto-injected
    """
    import functools
    import inspect

    # Check if function accepts ctx keyword argument
    sig = inspect.signature(func)
    params = sig.parameters
    has_ctx = "ctx" in params and params["ctx"].kind in (
        inspect.Parameter.KEYWORD_ONLY,
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
    )

    if not has_ctx:
        # Function doesn't want ctx, return as-is
        return func

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        kwargs["ctx"] = ctx
        return func(*args, **kwargs)

    return wrapper


# =============================================================================
# Built-in Functions (M1.8h) - imported from builtins module
# =============================================================================

from .builtins import (
    normal,
    uniform,
    lognormal,
    poisson,
    exponential,
    choice,
    discrete,
    DEFAULT_FUNCTIONS,
)


def make_context(
    seed: int | None = None,
    bindings: dict[str, Any] | None = None,
    functions: dict[str, Callable[..., Any]] | None = None,
) -> EvalContext:
    """Create an evaluation context with default functions.

    Convenience function that sets up a Context with:
    - Seeded RNG for reproducibility
    - Optional custom bindings
    - DEFAULT_FUNCTIONS plus any custom functions

    Args:
        seed: Random seed for reproducibility (None for random)
        bindings: Named values for !ref resolution
        functions: Additional functions (merged with defaults)

    Returns:
        Configured EvalContext ready for evaluation
    """
    rng = np.random.default_rng(seed)

    all_functions = dict(DEFAULT_FUNCTIONS)
    if functions:
        all_functions.update(functions)

    return EvalContext(
        rng=rng,
        bindings=bindings or {},
        functions=all_functions,
    )
