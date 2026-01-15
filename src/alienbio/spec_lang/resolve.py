"""Path resolution for Bio.fetch() specifiers.

Pure functions for resolving specifier strings to filesystem paths.
Handles source roots, DAT paths, dig operations, and Python module lookups.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass
class SourceRoot:
    """Configuration for a source root directory.

    A source root maps a filesystem path to a Python module prefix,
    enabling fetch() to find both YAML files and Python module globals.
    """

    path: Path
    module: str | None = None

    def __post_init__(self) -> None:
        self.path = Path(self.path).resolve()


@dataclass
class ResolvedPath:
    """Result of resolving a specifier string."""

    path: Path                     # filesystem path to load
    base_dir: str                  # directory for relative includes
    dig_path: list[str]            # keys to dig into after loading
    cache_key: str                 # key for ORM cache (resolved path without dig)


def resolve_specifier(
    specifier: str,
    source_roots: list[SourceRoot],
    current_dat: Path | None,
) -> ResolvedPath:
    """Resolve a specifier string to a filesystem path.

    Routing:
    - Starts with "./" → relative to current_dat
    - Contains "/" with dots before → resolve prefix via source roots
    - Contains "/" → filesystem/DAT path
    - All dots → source root resolution

    Args:
        specifier: Path like "catalog/scenarios/mutualism" or "mute.mol.energy"
        source_roots: List of source roots for dotted resolution
        current_dat: Current working DAT for relative paths

    Returns:
        ResolvedPath with path, base_dir, dig_path, and cache_key

    Raises:
        ValueError: If relative path used without current_dat
        FileNotFoundError: If specifier cannot be resolved
    """
    # Handle relative paths
    if specifier.startswith("./"):
        if current_dat is None:
            raise ValueError("Relative path './...' requires current DAT (use bio.cd() first)")
        specifier = str(current_dat / specifier[2:])

    # Try source root resolution for dotted paths without slashes
    if "/" not in specifier and source_roots:
        result = _resolve_from_source_roots(specifier, source_roots)
        if result is not None:
            return result
        if "." in specifier:
            raise FileNotFoundError(f"'{specifier}' not found in source roots")

    # Check for dots-before-slash pattern
    if "/" in specifier and source_roots:
        first_slash = specifier.index("/")
        prefix = specifier[:first_slash]
        suffix = specifier[first_slash:]

        if "." in prefix:
            resolved_prefix = resolve_source_root_prefix(prefix, source_roots)
            if resolved_prefix is not None:
                specifier = str(resolved_prefix) + suffix

    # Filesystem/DAT path resolution
    path = Path(specifier)
    dig_path: list[str] = []

    if not path.exists():
        path, dig_path = find_dat_with_dig(specifier)
        if path is None:
            raise FileNotFoundError(f"Specifier path not found: {specifier}")

    # Find spec.yaml in directory
    if path.is_dir():
        spec_file = path / "spec.yaml"
        if not spec_file.exists():
            raise FileNotFoundError(f"No spec.yaml found in: {specifier}")
    else:
        spec_file = path

    return ResolvedPath(
        path=spec_file,
        base_dir=str(spec_file.parent),
        dig_path=dig_path,
        cache_key=str(spec_file.resolve()),
    )


def _resolve_from_source_roots(
    dotted_path: str, source_roots: list[SourceRoot]
) -> ResolvedPath | None:
    """Try to resolve a dotted path from source roots.

    Returns ResolvedPath if found, None otherwise.
    """
    for root in source_roots:
        result = resolve_dotted_in_source_root(dotted_path, root)
        if result is not None:
            data, base_dir, yaml_path = result
            return ResolvedPath(
                path=yaml_path,
                base_dir=base_dir,
                dig_path=[],
                cache_key=str(yaml_path.resolve()) if yaml_path else base_dir,
            )
    return None


def resolve_dotted_in_source_root(
    dotted_path: str, root: SourceRoot
) -> tuple[Any, str, Path | None] | None:
    """Try to resolve a dotted path within a source root.

    Checks for YAML file first, then Python module global.

    Args:
        dotted_path: Path like "mute.mol.energy.ME_basic"
        root: Source root to search in

    Returns:
        Tuple of (data, base_dir, yaml_path) if found, None otherwise.
        yaml_path may be None if loaded from Python module.
    """
    parts = dotted_path.split(".") if "." in dotted_path else [dotted_path]

    # Try YAML file resolution (greedy: try longest path first)
    for i in range(len(parts), 0, -1):
        yaml_path = root.path / "/".join(parts[:i])

        # Try as .yaml file
        yaml_file = yaml_path.with_suffix(".yaml")
        if yaml_file.exists():
            content = yaml_file.read_text()
            data = yaml.safe_load(content)
            base_dir = str(yaml_file.parent)

            # Dig into remaining path
            remaining = parts[i:]
            for key in remaining:
                if isinstance(data, dict) and key in data:
                    data = data[key]
                else:
                    break
            else:
                return data, base_dir, yaml_file

        # Try as directory with index.yaml
        index_file = yaml_path / "index.yaml"
        if index_file.exists():
            content = index_file.read_text()
            data = yaml.safe_load(content)
            base_dir = str(index_file.parent)

            remaining = parts[i:]
            for key in remaining:
                if isinstance(data, dict) and key in data:
                    data = data[key]
                else:
                    break
            else:
                return data, base_dir, index_file

    # Try Python module global
    if root.module is not None:
        module_parts = parts[:-1]
        global_name = parts[-1]

        if root.module:
            full_module = f"{root.module}.{'.'.join(module_parts)}" if module_parts else root.module
        else:
            full_module = ".".join(module_parts) if module_parts else None

        if full_module:
            result = load_from_python_global(full_module, global_name)
            if result is not None:
                data, base_dir = result
                return data, base_dir, None

    return None


def load_from_python_global(
    module_path: str, global_name: str
) -> tuple[Any, str] | None:
    """Load data from a Python module global.

    Args:
        module_path: Full module path like "myproject.catalog.mute.mol"
        global_name: Global variable name like "ME_BASIC"

    Returns:
        Tuple of (data, base_dir) if found, None otherwise.
    """
    import importlib

    try:
        module = importlib.import_module(module_path)
    except ImportError:
        return None

    # Try exact name, then uppercase
    if hasattr(module, global_name):
        value = getattr(module, global_name)
    elif hasattr(module, global_name.upper()):
        value = getattr(module, global_name.upper())
    else:
        return None

    # Get base directory from module file
    module_file = getattr(module, "__file__", None)
    base_dir = str(Path(module_file).parent) if module_file else "."

    # Handle "yaml: " string format
    if isinstance(value, str) and value.startswith("yaml:"):
        yaml_content = value[5:].lstrip()
        data = yaml.safe_load(yaml_content)
        return data, base_dir

    if isinstance(value, dict):
        return value, base_dir

    return None


def find_dat_with_dig(specifier: str) -> tuple[Path | None, list[str]]:
    """Find DAT path by splitting specifier at dots.

    For "path/to/dat.dig.path", tries to find the longest valid path,
    treating remaining dots as the dig path.

    Args:
        specifier: Full specifier like "catalog/scenarios/mutualism.baseline"

    Returns:
        Tuple of (path, dig_path). Returns (None, []) if not found.
    """
    if "/" in specifier:
        last_slash = specifier.rfind("/")
        base = specifier[:last_slash + 1]
        remainder = specifier[last_slash + 1:]
    else:
        base = ""
        remainder = specifier

    parts = remainder.split(".")
    for i in range(len(parts), 0, -1):
        path_str = base + ".".join(parts[:i])
        path = Path(path_str)
        if path.exists():
            return path, parts[i:]

    return None, []


def dig_into(data: Any, dig_path: list[str]) -> Any:
    """Navigate into data structure using key path.

    Args:
        data: Dict or object to dig into
        dig_path: List of keys/attributes to traverse

    Returns:
        Value at the dig path

    Raises:
        KeyError: If key not found in dict
        AttributeError: If attribute not found on object
    """
    result = data
    for key in dig_path:
        if isinstance(result, dict):
            if key not in result:
                raise KeyError(f"Key '{key}' not found in dict")
            result = result[key]
        else:
            if not hasattr(result, key):
                raise AttributeError(f"Attribute '{key}' not found on {type(result).__name__}")
            result = getattr(result, key)
    return result


def resolve_source_root_prefix(
    dotted_prefix: str, source_roots: list[SourceRoot]
) -> Path | None:
    """Resolve a dotted prefix through source roots to a directory path.

    For dots-before-slash patterns like "catalog.scenarios/mutualism",
    this resolves "catalog.scenarios" to its filesystem path.

    Args:
        dotted_prefix: Dotted path like "catalog.scenarios"
        source_roots: List of source roots to search

    Returns:
        Resolved Path if found, None otherwise
    """
    parts = dotted_prefix.split(".")

    for root in source_roots:
        candidate = root.path / "/".join(parts)
        if candidate.is_dir():
            return candidate

    return None
