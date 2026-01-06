"""Fetch command: Load and display a bio spec."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml


def fetch_command(args: list[str], verbose: bool = False) -> int:
    """Fetch and display a bio spec.

    Args:
        args: Command arguments [spec_path]
        verbose: Enable verbose output

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    from alienbio import bio

    if not args:
        print("Error: fetch command requires a spec path", file=sys.stderr)
        print("Usage: bio fetch <spec_path>", file=sys.stderr)
        return 1

    spec_path = args[0]
    path = Path(spec_path)

    # Handle relative paths - look in catalog/ if not found directly
    if not path.exists():
        catalog_path = Path("catalog") / path
        if catalog_path.exists():
            path = catalog_path
        else:
            print(f"Error: Spec path not found: {spec_path}", file=sys.stderr)
            print(f"  Tried: {spec_path}", file=sys.stderr)
            print(f"  Tried: {catalog_path}", file=sys.stderr)
            return 1

    if verbose:
        print(f"Fetching: {path}")

    try:
        result = bio.fetch(str(path))

        # Display the result
        if hasattr(result, '__dict__'):
            # Object with attributes - show as dict
            print(yaml.dump(vars(result), default_flow_style=False))
        elif isinstance(result, dict):
            print(yaml.dump(result, default_flow_style=False))
        else:
            print(result)

        return 0

    except Exception as e:
        print(f"Error fetching spec: {e}", file=sys.stderr)
        return 1
