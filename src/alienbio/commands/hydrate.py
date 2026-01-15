"""hydrate command: Fully evaluate a spec, resolving all placeholders."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml


def hydrate_command(args: list[str], verbose: bool = False) -> int:
    """Hydrate and evaluate a spec: resolve all placeholders to concrete values.

    Takes a spec through the full pipeline:
    1. Load YAML
    2. Resolve includes, refs, defaults (expand)
    3. Hydrate to placeholder objects (Evaluable, Reference, etc.)
    4. Evaluate placeholders to concrete values

    Useful for debugging to see what values will be used at runtime.

    Args:
        args: Command arguments [spec_path] [--seed N] [--json]
        verbose: Enable verbose output

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    from alienbio import bio, hydrate, eval_node, make_context

    if not args:
        print("Error: hydrate command requires a spec path", file=sys.stderr)
        print("Usage: bio hydrate <spec_path> [--seed N] [--json]", file=sys.stderr)
        return 1

    # Parse arguments
    spec_path = args[0]
    json_output = "--json" in args
    seed = None

    for i, arg in enumerate(args):
        if arg == "--seed" and i + 1 < len(args):
            try:
                seed = int(args[i + 1])
            except ValueError:
                print(f"Error: --seed requires an integer, got: {args[i + 1]}", file=sys.stderr)
                return 1

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
        print(f"Hydrating: {path}")
        if seed is not None:
            print(f"  Seed: {seed}")

    try:
        # Step 1-2: Expand the spec (resolve includes, refs, defaults)
        expanded = bio.expand(str(path))

        # Step 3: Hydrate to placeholder objects
        hydrated = hydrate(expanded, str(path.parent))

        # Step 4: Evaluate placeholders to concrete values
        ctx = make_context(seed=seed)
        result = eval_node(hydrated, ctx)

        if json_output:
            import json
            print(json.dumps(result, indent=2, default=str))
        else:
            print(yaml.dump(result, default_flow_style=False))
        return 0

    except Exception as e:
        print(f"Error hydrating spec: {e}", file=sys.stderr)
        return 1
