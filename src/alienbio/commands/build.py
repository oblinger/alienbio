"""build command: Build/expand a spec without evaluating."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml


def build_command(args: list[str], verbose: bool = False) -> int:
    """Build a spec: resolve includes, refs, defaults without evaluating.

    Shows the fully expanded dict with _type fields, resolved includes,
    refs, and defaults - but placeholders like Evaluable remain as-is.

    This is essentially an alias for `bio expand` with some enhancements.

    Args:
        args: Command arguments [spec_path] [--json]
        verbose: Enable verbose output

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    from alienbio import bio

    if not args:
        print("Error: build command requires a spec path", file=sys.stderr)
        print("Usage: bio build <spec_path> [--json]", file=sys.stderr)
        return 1

    spec_path = args[0]
    json_output = "--json" in args
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
        print(f"Building: {path}")

    try:
        result = bio.expand(str(path))

        if json_output:
            import json
            print(json.dumps(result, indent=2, default=str))
        else:
            print(yaml.dump(result, default_flow_style=False))
        return 0

    except Exception as e:
        print(f"Error building spec: {e}", file=sys.stderr)
        return 1
