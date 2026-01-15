"""fetch command: Fetch and display a spec."""

from __future__ import annotations

import sys
import json

import yaml


def fetch_command(args: list[str], verbose: bool = False) -> int:
    """Fetch a spec and display it.

    Args:
        args: Command arguments [specifier] [--raw] [--json]
        verbose: Enable verbose output

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    from alienbio import bio

    if not args:
        print("Error: fetch command requires a specifier", file=sys.stderr)
        print("Usage: bio fetch <specifier> [--raw] [--json]", file=sys.stderr)
        return 1

    specifier = args[0]
    raw = "--raw" in args
    as_json = "--json" in args

    if verbose:
        print(f"Fetching: {specifier}")
        if raw:
            print("  (raw mode - no processing)")

    try:
        result = bio.fetch(specifier, raw=raw)

        if result is None:
            print("(empty)", file=sys.stderr)
            return 0

        # Output format
        if as_json:
            print(json.dumps(result, indent=2, default=str))
        else:
            print(yaml.dump(result, default_flow_style=False, sort_keys=False))

        return 0

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error fetching spec: {e}", file=sys.stderr)
        return 1
