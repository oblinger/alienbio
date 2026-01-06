"""Run command: Execute a bio job (scenario, suite, or report)."""

from __future__ import annotations

import sys
from pathlib import Path


def run_command(args: list[str], verbose: bool = False) -> int:
    """Run a bio job from the given path.

    Args:
        args: Command arguments [job_path]
        verbose: Enable verbose output

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    from dvc_dat import Dat

    if not args:
        print("Error: run command requires a job path", file=sys.stderr)
        print("Usage: bio run <job_path>", file=sys.stderr)
        return 1

    job_path = args[0]
    path = Path(job_path)

    # Handle relative paths - look in catalog/jobs if not found directly
    if not path.exists():
        catalog_path = Path("catalog/jobs") / path
        if catalog_path.exists():
            path = catalog_path
        else:
            print(f"Error: Job path not found: {job_path}", file=sys.stderr)
            print(f"  Tried: {job_path}", file=sys.stderr)
            print(f"  Tried: {catalog_path}", file=sys.stderr)
            return 1

    # Check for index.yaml
    index_file = path / "index.yaml"
    if not index_file.exists():
        print(f"Error: No index.yaml found in: {path}", file=sys.stderr)
        return 1

    if verbose:
        print(f"Running job: {path}")

    # Load and run the DAT
    try:
        dat = Dat.load(str(path))
        success, metadata = dat.run()

        if success:
            print("Job completed successfully")
            return 0
        else:
            print("Job failed")
            if "error" in metadata:
                print(f"Error: {metadata['error']}", file=sys.stderr)
            return 1

    except Exception as e:
        print(f"Error running job: {e}", file=sys.stderr)
        return 1
