"""YAML tag implementations for spec language.

Tags:
    !ev <expr>     - Evaluate Python expression
    !ref <name>    - Reference a named constant
    !include <path> - Include external file content
"""

from __future__ import annotations
from typing import Any
import yaml


class EvTag:
    """Represents an !ev tag value before evaluation."""

    def __init__(self, expr: str):
        self.expr = expr

    def __repr__(self) -> str:
        return f"EvTag({self.expr!r})"

    def evaluate(self, namespace: dict[str, Any] | None = None) -> Any:
        """Evaluate the expression in the given namespace.

        Args:
            namespace: Dict of names available during evaluation

        Returns:
            Result of evaluating the expression

        Raises:
            NameError: If expression references undefined name
            SyntaxError: If expression has invalid syntax
            Exception: Any exception raised during evaluation
        """
        ns = namespace or {}

        # Security: block dangerous builtins
        blocked = {"open", "exec", "eval", "__import__", "compile", "globals", "locals"}
        safe_builtins = {k: v for k, v in __builtins__.items() if k not in blocked}  # type: ignore

        eval_ns = {"__builtins__": safe_builtins, **ns}

        return eval(self.expr, eval_ns)


class RefTag:
    """Represents a !ref tag value before resolution."""

    def __init__(self, name: str):
        self.name = name

    def __repr__(self) -> str:
        return f"RefTag({self.name!r})"

    def resolve(self, constants: dict[str, Any]) -> Any:
        """Resolve the reference from constants.

        Supports dotted paths: "nested.path.value"

        Args:
            constants: Dict of available constants

        Returns:
            The referenced value

        Raises:
            KeyError: If reference cannot be resolved
        """
        parts = self.name.split(".")
        value = constants

        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                raise KeyError(f"Cannot resolve reference: {self.name}")

        return value


class IncludeTag:
    """Represents an !include tag value before loading."""

    def __init__(self, path: str):
        self.path = path

    def __repr__(self) -> str:
        return f"IncludeTag({self.path!r})"

    def load(self, base_dir: str | None = None) -> Any:
        """Load the included file.

        Args:
            base_dir: Base directory for relative paths

        Returns:
            File contents (string for .md, parsed for .yaml, executed for .py)

        Raises:
            FileNotFoundError: If file doesn't exist
        """
        raise NotImplementedError("IncludeTag.load not yet implemented")


# --- YAML constructors ---


def ev_constructor(loader: yaml.Loader, node: yaml.Node) -> EvTag:
    """YAML constructor for !ev tag."""
    value = loader.construct_scalar(node)  # type: ignore
    return EvTag(str(value))


def ref_constructor(loader: yaml.Loader, node: yaml.Node) -> RefTag:
    """YAML constructor for !ref tag."""
    value = loader.construct_scalar(node)  # type: ignore
    return RefTag(str(value))


def include_constructor(loader: yaml.Loader, node: yaml.Node) -> IncludeTag:
    """YAML constructor for !include tag."""
    value = loader.construct_scalar(node)  # type: ignore
    return IncludeTag(str(value))


def register_yaml_tags() -> None:
    """Register all custom YAML tags with the loader."""
    yaml.add_constructor("!ev", ev_constructor, Loader=yaml.SafeLoader)
    yaml.add_constructor("!ref", ref_constructor, Loader=yaml.SafeLoader)
    yaml.add_constructor("!include", include_constructor, Loader=yaml.SafeLoader)


# Register tags on module import
register_yaml_tags()
