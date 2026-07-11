"""AST-allowlist safe evaluator for spec-language expressions.

Spec expressions (``!ev`` / ``!_`` tags, ``Evaluable.evaluate``) come from
*untrusted, agent-authored* specs. A bare ``eval`` with an emptied
``__builtins__`` is NOT safe: attribute traversal such as
``().__class__.__base__.__subclasses__()`` reaches arbitrary classes
(subprocess/os gadgets) and yields full remote code execution.

The security boundary here is a strict **allowlist over the AST**:

1. Only a fixed set of node types is permitted (see ``_ALLOWED_NODE_TYPES``).
2. Attribute access is permitted (specs legitimately call methods like
   ``state.get('A', 0)`` and read fields like ``trace.final``), but the
   *attribute name* is filtered: every dunder (``__*__``) is rejected, which
   severs the ``.__class__.__base__.__subclasses__()`` and ``.__globals__`` /
   ``.__builtins__`` escape chains. In addition a denylist of non-dunder
   interpreter internals is rejected — generator/coroutine/frame/traceback/code
   attributes (``gi_frame``, ``f_back``, ``f_globals``, ``f_builtins``,
   ``tb_frame``, ``co_*`` ...) that would otherwise permit walking from a
   generator up to the real builtins, plus ``format`` / ``format_map`` (whose
   format-string field access bypasses AST analysis) and ``mro`` /
   ``subclasses``.
3. Identifiers may not be dunders (``__*__``) and may not name a small set of
   dangerous builtins (``getattr``, ``eval``, ``open``, ``__import__`` ...).
4. Calls may only target a ``Name`` or an ``Attribute`` (a method call) — never
   a subscript / inline lambda / call result — and ``*args`` / ``**kwargs``
   unpacking is rejected.

Only after the tree passes validation is it executed with Python's ``eval``,
using an empty ``__builtins__`` and a caller-supplied allowlist namespace.
Because the tree is already proven to contain no attribute access and no
reference to anything outside the namespace, this execution cannot escape.

Names not present in the namespace fail with the ordinary ``NameError`` and
runtime errors (``ZeroDivisionError`` etc.) propagate unchanged, preserving
the semantics callers expect. Anything structurally forbidden raises
``UnsafeExpressionError``.
"""

from __future__ import annotations

import ast
from typing import Any


class UnsafeExpressionError(Exception):
    """Raised when a spec expression uses a construct outside the allowlist."""


# Names that are never allowed to appear in an expression, even though an
# empty ``__builtins__`` and the allowlist namespace would already keep them
# from resolving. Listing them gives a clear error and defends in depth if a
# binding ever shadows one of them. ``getattr``/``vars``/``type`` are the
# function-shaped equivalents of the attribute access we forbid.
_DENIED_NAMES: frozenset[str] = frozenset({
    "getattr", "setattr", "delattr", "hasattr",
    "globals", "locals", "vars", "dir",
    "eval", "exec", "compile", "open", "__import__", "import",
    "input", "breakpoint", "exit", "quit", "help",
    "memoryview", "bytearray", "object", "type", "super",
    "classmethod", "staticmethod", "property", "format", "vars",
})

# Non-dunder attribute names that expose interpreter internals. Reading these
# off a generator / frame / traceback / code object would let an expression
# walk 'up' to the real builtins (e.g. ``(g).gi_frame.f_back.f_builtins``),
# bypassing the empty ``__builtins__``. ``format`` / ``format_map`` are denied
# because their format-string field access ('{0.__class__}') traverses
# attributes at runtime, invisibly to this AST validator.
_DENIED_ATTR_NAMES: frozenset[str] = frozenset({
    "format", "format_map", "mro", "subclasses",
})

# Attribute-name prefixes that mark interpreter-internal handles.
_DENIED_ATTR_PREFIXES: tuple[str, ...] = (
    "gi_", "cr_", "ag_", "f_", "tb_", "co_", "func_",
)


def _check_attr_name(name: str) -> None:
    if _is_dunder(name):
        raise UnsafeExpressionError(
            f"dunder attribute access {name!r} is not allowed in a spec expression"
        )
    if name in _DENIED_ATTR_NAMES or name.startswith(_DENIED_ATTR_PREFIXES):
        raise UnsafeExpressionError(
            f"attribute {name!r} is not allowed in a spec expression"
        )

# Fixed allowlist of AST node types the expression language legitimately uses.
# Everything else (Attribute, Import, Starred, JoinedStr/FormattedValue,
# NamedExpr/walrus, Await/Yield, statements, ...) is rejected.
_ALLOWED_NODE_TYPES: tuple[type, ...] = (
    ast.Expression,
    # literals
    ast.Constant,
    ast.List, ast.Tuple, ast.Dict, ast.Set,
    # names and load/store contexts
    ast.Name, ast.Load, ast.Store,
    # operators
    ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.Compare,
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow,
    ast.UAdd, ast.USub, ast.Not,
    ast.And, ast.Or,
    ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
    ast.In, ast.NotIn, ast.Is, ast.IsNot,
    # conditional expression
    ast.IfExp,
    # f-strings — embedded expressions are still walked and validated, so
    # f'{().__class__}' is rejected via the dunder-attribute rule, while
    # f'Molecule {i}' is permitted.
    ast.JoinedStr, ast.FormattedValue,
    # comprehensions
    ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp, ast.comprehension,
    # attribute access (attribute *name* filtered in _validate_node)
    ast.Attribute,
    # subscripting / slicing
    ast.Subscript, ast.Slice,
    # calls (constrained further in _validate_node)
    ast.Call, ast.keyword,
    # lambdas
    ast.Lambda, ast.arguments, ast.arg,
)


def _is_dunder(name: str) -> bool:
    return name.startswith("__") and name.endswith("__")


def _check_identifier(name: str) -> None:
    if _is_dunder(name):
        raise UnsafeExpressionError(
            f"dunder identifier {name!r} is not allowed in a spec expression"
        )
    if name in _DENIED_NAMES:
        raise UnsafeExpressionError(
            f"name {name!r} is not allowed in a spec expression"
        )


def _validate_node(node: ast.AST) -> None:
    """Validate a single node against the allowlist."""
    if not isinstance(node, _ALLOWED_NODE_TYPES):
        raise UnsafeExpressionError(
            f"disallowed syntax in spec expression: {type(node).__name__}"
        )

    if isinstance(node, ast.Name):
        _check_identifier(node.id)

    elif isinstance(node, ast.Attribute):
        # Attribute access is allowed, but the attribute *name* is filtered so
        # that dunders and interpreter internals cannot be reached.
        _check_attr_name(node.attr)

    elif isinstance(node, ast.arg):
        _check_identifier(node.arg)

    elif isinstance(node, ast.keyword):
        # keyword.arg is None for '**mapping' unpacking — forbid that form.
        if node.arg is None:
            raise UnsafeExpressionError(
                "dictionary unpacking (**) is not allowed in a spec expression"
            )
        _check_identifier(node.arg)

    elif isinstance(node, ast.Call):
        # Calls may target a named function or a method (attribute); never a
        # subscript / inline lambda / call-result. Attribute names are already
        # filtered by the Attribute rule above.
        if not isinstance(node.func, (ast.Name, ast.Attribute)):
            raise UnsafeExpressionError(
                "only calls of a named function or method are allowed in a "
                "spec expression"
            )
        for arg in node.args:
            if isinstance(arg, ast.Starred):
                raise UnsafeExpressionError(
                    "argument unpacking (*) is not allowed in a spec expression"
                )


def validate_expression(source: str) -> ast.Expression:
    """Parse ``source`` and validate every node against the allowlist.

    Returns the parsed ``ast.Expression`` (for reuse in compilation).

    Raises:
        SyntaxError: If ``source`` is not a valid Python expression.
        UnsafeExpressionError: If any node is outside the allowlist.
    """
    tree = ast.parse(source, mode="eval")
    for node in ast.walk(tree):
        _validate_node(node)
    return tree


def safe_eval(source: str, namespace: dict[str, Any]) -> Any:
    """Safely evaluate a spec expression.

    The expression is validated against the AST allowlist, then executed with
    an empty ``__builtins__`` and ``namespace`` as the only available names.

    Args:
        source: Python expression string from an (untrusted) spec.
        namespace: Allowlisted names available to the expression.

    Returns:
        The result of evaluating the expression.

    Raises:
        SyntaxError: Invalid expression syntax.
        UnsafeExpressionError: Expression uses a forbidden construct.
        Exception: Ordinary runtime errors (NameError, ZeroDivisionError, ...)
            propagate unchanged.
    """
    tree = validate_expression(source)
    code = compile(tree, "<spec>", "eval")
    return eval(code, {"__builtins__": {}}, namespace)
