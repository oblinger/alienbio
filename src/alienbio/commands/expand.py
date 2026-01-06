"""Expand command: Expand a bio spec without hydrating."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml


def expand_command(args: list[str], verbose: bool = False) -> int:
    """Expand a bio spec without hydrating to typed objects.

    Shows the fully expanded dict with _type fields, resolved includes,
    refs, and defaults - but no hydration to typed objects.

    Args:
        args: Command arguments [spec_path]
        verbose: Enable verbose output

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    from alienbio import bio

    if not args:
        print("Error: expand command requires a spec path", file=sys.stderr)
        print("Usage: bio expand <spec_path>", file=sys.stderr)
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
        print(f"Expanding: {path}")

    try:
        result = bio.expand(str(path))
        print(yaml.dump(result, default_flow_style=False))
        return 0

    except Exception as e:
        print(f"Error expanding spec: {e}", file=sys.stderr)
        return 1
