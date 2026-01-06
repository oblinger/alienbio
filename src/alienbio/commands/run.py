"""Run command: Execute an entity's run() method and print results.

This is a debugging tool - it runs the entity and prints the result dict
(like a REPL). For production use, use `bio report` instead.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml


def run_command(args: list[str], verbose: bool = False) -> int:
    """Run an entity and print the result dict.

    This is for debugging - runs the entity's run() method and
    prints whatever dict it returns.

    Args:
        args: Command arguments [path]
        verbose: Enable verbose output

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    from dvc_dat import Dat

    if not args:
        print("Error: run command requires a path", file=sys.stderr)
        print("Usage: bio run <path>", file=sys.stderr)
        return 1

    job_path = args[0]
    path = Path(job_path)

    # Handle relative paths - look in catalog/jobs if not found directly
    if not path.exists():
        catalog_path = Path("catalog/jobs") / path
        if catalog_path.exists():
            path = catalog_path
        else:
            print(f"Error: Path not found: {job_path}", file=sys.stderr)
            return 1

    # Check for index.yaml
    index_file = path / "index.yaml"
    if not index_file.exists():
        print(f"Error: No index.yaml found in: {path}", file=sys.stderr)
        return 1

    if verbose:
        print(f"Running: {path}")

    # Load and run the DAT
    try:
        dat = Dat.load(str(path))
        success, result = dat.run()

        # Print the result dict (debug output)
        print("--- Result ---")
        print(yaml.dump(result, default_flow_style=False))
        print(f"--- Success: {success} ---")

        return 0 if success else 1

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
