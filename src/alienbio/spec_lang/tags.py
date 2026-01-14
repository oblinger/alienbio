"""YAML tag implementations for spec language.

Tags:
    !ev <expr>     - Evaluate Python expression (creates Evaluable)
    !ref <name>    - Reference a named constant (creates Reference)
    !include <path> - Include external file content (creates Include)
    !_ <expr>      - Quoted expression for later evaluation (creates Quoted)

Placeholder classes (from eval.py):
    Evaluable - holds expression, resolved at eval time
    Reference - holds name, resolved during hydration
    Quoted    - holds expression string, preserved for later contextual evaluation

Include class (defined here):
    Include   - holds path, resolved during hydration (has load() method)
"""

from __future__ import annotations
from typing import Any
from pathlib import Path
import yaml

# Import placeholder classes from eval module
from .eval import Evaluable, Quoted, Reference


class PyRef:
    """Placeholder for !py tag - local Python reference.

    Resolved during hydration. Looks up Python code relative to the
    source file location.

    Examples:
        !py rate_fn           # loads rate_fn from module in same dir
        !py helpers.compute   # loads helpers.py, gets compute attr
    """

    def __init__(self, path: str):
        self.path = path

    def __repr__(self) -> str:
        return f"PyRef({self.path!r})"

    def resolve(self, base_dir: str) -> Any:
        """Resolve the Python reference relative to base_dir.

        Args:
            base_dir: Directory containing the source file

        Returns:
            The resolved Python object (function, class, value, etc.)

        Raises:
            ImportError: If module not found
            AttributeError: If attribute not found in module
        """
        import importlib.util
        import sys

        parts = self.path.split(".")

        if len(parts) == 1:
            # Simple name like "rate_fn" - look for any .py file with this function
            # First try: same name as the YAML file
            # For now, require explicit module: !py module.attr
            raise ValueError(
                f"!py requires module.attr format, got: {self.path}. "
                f"Use !py filename.function_name"
            )

        # module.attr format
        module_name = parts[0]
        attr_path = parts[1:]

        # Build path to .py file
        py_file = Path(base_dir) / f"{module_name}.py"

        if not py_file.exists():
            raise ImportError(f"Python file not found: {py_file}")

        # Load the module dynamically
        spec = importlib.util.spec_from_file_location(module_name, py_file)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load module from: {py_file}")

        module = importlib.util.module_from_spec(spec)

        # Add to sys.modules temporarily for nested imports
        old_module = sys.modules.get(module_name)
        sys.modules[module_name] = module

        try:
            spec.loader.exec_module(module)

            # Navigate to the attribute
            result = module
            for attr in attr_path:
                result = getattr(result, attr)

            return result
        finally:
            # Restore sys.modules state
            if old_module is None:
                sys.modules.pop(module_name, None)
            else:
                sys.modules[module_name] = old_module


class Include:
    """Placeholder for !include tag - file to include.

    Resolved during hydration (phase 1).
    """

    def __init__(self, path: str):
        self.path = path

    def __repr__(self) -> str:
        return f"Include({self.path!r})"

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
            # Recursively resolve any Includes in the loaded data
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
        """Recursively resolve Includes in loaded data."""
        if isinstance(data, Include):
            return data.load(base_dir, _seen)
        elif isinstance(data, dict):
            return {k: self._resolve_includes(v, base_dir, _seen) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._resolve_includes(item, base_dir, _seen) for item in data]
        else:
            return data


# --- Backward compatibility aliases ---
# Old tag class names that some code may still use

class EvTag(Evaluable):
    """Backward compat alias for Evaluable."""
    def __init__(self, expr: str):
        super().__init__(source=expr)

    @property
    def expr(self) -> str:
        return self.source

    def evaluate(self, namespace: dict[str, Any] | None = None) -> Any:
        """Evaluate the expression in the given namespace."""
        ns = namespace or {}
        blocked = {"open", "exec", "eval", "__import__", "compile", "globals", "locals"}
        safe_builtins = {k: v for k, v in __builtins__.items() if k not in blocked}  # type: ignore
        eval_ns = {"__builtins__": safe_builtins, **ns}
        return eval(self.source, eval_ns)


class RefTag(Reference):
    """Backward compat alias for Reference."""
    def __init__(self, name: str):
        super().__init__(name=name)

    def resolve(self, constants: dict[str, Any]) -> Any:
        """Resolve the reference from constants."""
        parts = self.name.split(".")
        value = constants
        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                raise KeyError(f"Cannot resolve reference: {self.name}")
        return value


# Alias for Include
IncludeTag = Include


# --- YAML constructors ---
# Note: eval.py also registers constructors, but we re-register here
# to ensure Include is used for !include


def include_constructor(loader: yaml.Loader, node: yaml.Node) -> Include:
    """YAML constructor for !include tag."""
    value = loader.construct_scalar(node)  # type: ignore
    return Include(str(value))


def py_constructor(loader: yaml.Loader, node: yaml.Node) -> PyRef:
    """YAML constructor for !py tag."""
    value = loader.construct_scalar(node)  # type: ignore
    return PyRef(str(value))


def register_yaml_tags() -> None:
    """Register custom YAML tags with the loader.

    Note: !ev, !ref, !_, !quote are registered in eval.py
    """
    yaml.add_constructor("!include", include_constructor, Loader=yaml.SafeLoader)
    yaml.add_constructor("!py", py_constructor, Loader=yaml.SafeLoader)


# Register tags on module import
register_yaml_tags()
