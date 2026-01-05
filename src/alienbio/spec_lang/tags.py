"""YAML tag implementations for spec language.

Tags:
    !ev <expr>     - Evaluate Python expression
    !ref <name>    - Reference a named constant
    !include <path> - Include external file content
"""

from __future__ import annotations
from typing import Any
from pathlib import Path
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

    # Track files being loaded to detect circular includes
    _loading_files: set[str] = set()

    def __init__(self, path: str):
        self.path = path

    def __repr__(self) -> str:
        return f"IncludeTag({self.path!r})"

    def load(self, base_dir: str | None = None, _seen: set[str] | None = None) -> Any:
        """Load the included file.

        Args:
            base_dir: Base directory for relative paths
            _seen: Internal set tracking files in current include chain

        Returns:
            File contents (string for .md, parsed for .yaml, executed for .py)

        Raises:
            FileNotFoundError: If file doesn't exist
            RecursionError: If circular include detected
        """
        # Resolve file path
        if Path(self.path).is_absolute():
            file_path = Path(self.path)
        elif base_dir:
            file_path = Path(base_dir) / self.path
        else:
            file_path = Path(self.path)

        file_path = file_path.resolve()

        if not file_path.exists():
            raise FileNotFoundError(f"Include file not found: {file_path}")

        # Check for circular includes
        file_key = str(file_path)
        if _seen is None:
            _seen = set()

        if file_key in _seen:
            raise RecursionError(f"Circular include detected: {file_key}")

        _seen = _seen | {file_key}  # Create new set to avoid cross-branch pollution

        # Load based on file extension
        suffix = file_path.suffix.lower()

        if suffix == ".md":
            return file_path.read_text()

        elif suffix in (".yaml", ".yml"):
            content = file_path.read_text()
            data = yaml.safe_load(content)
            # Recursively resolve any IncludeTags in the loaded data
            return self._resolve_includes(data, str(file_path.parent), _seen)

        elif suffix == ".py":
            # Execute Python file to register decorators
            code = file_path.read_text()
            exec(compile(code, str(file_path), "exec"), {"__name__": "__main__"})
            return None

        else:
            # Default: return raw text
            return file_path.read_text()

    def _resolve_includes(
        self, data: Any, base_dir: str, _seen: set[str]
    ) -> Any:
        """Recursively resolve IncludeTags in loaded data."""
        if isinstance(data, IncludeTag):
            return data.load(base_dir, _seen)
        elif isinstance(data, dict):
            return {k: self._resolve_includes(v, base_dir, _seen) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._resolve_includes(item, base_dir, _seen) for item in data]
        else:
            return data


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
