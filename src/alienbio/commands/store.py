"""store command: Store data to a spec path."""

from __future__ import annotations

import sys

import yaml


def store_command(args: list[str], verbose: bool = False) -> int:
    """Store data to a spec path.

    Reads YAML from stdin and stores it to the specified path.

    Args:
        args: Command arguments [specifier] [--raw]
        verbose: Enable verbose output

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    from alienbio import bio

    if not args:
        print("Error: store command requires a specifier", file=sys.stderr)
        print("Usage: bio store <specifier> [--raw] < data.yaml", file=sys.stderr)
        print("       echo '{key: value}' | bio store <specifier>", file=sys.stderr)
        return 1

    specifier = args[0]
    raw = "--raw" in args

    if verbose:
        print(f"Storing to: {specifier}")
        if raw:
            print("  (raw mode - no dehydration)")

    # Check if stdin has data
    if sys.stdin.isatty():
        print("Error: No input data. Pipe YAML data to stdin.", file=sys.stderr)
        print("Usage: echo '{key: value}' | bio store <specifier>", file=sys.stderr)
        return 1

    try:
        # Read YAML from stdin
        content = sys.stdin.read()
        data = yaml.safe_load(content)

        if data is None:
            print("Error: Empty or invalid YAML input", file=sys.stderr)
            return 1

        # Store the data
        bio.store(specifier, data, raw=raw)

        if verbose:
            print(f"Stored to: {specifier}/index.yaml")
        else:
            print(specifier)

        return 0

    except yaml.YAMLError as e:
        print(f"Error parsing YAML: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error storing spec: {e}", file=sys.stderr)
        return 1
