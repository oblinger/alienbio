"""Bio CLI: Command-line interface for running Bio scenarios.

Usage:
    bio <job_path>           Run a job (scenario, suite, or report)
    bio --help              Show help
    bio --version           Show version

Examples:
    bio catalog/jobs/hardcoded_test
    bio my_project/scenarios/mutualism
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    """Main entry point for bio CLI.

    Args:
        argv: Command line arguments (defaults to sys.argv[1:])

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    from alienbio import __version__

    parser = argparse.ArgumentParser(
        prog="bio",
        description="Run Bio scenarios, suites, and reports",
    )
    parser.add_argument(
        "job_path",
        nargs="?",
        help="Path to job folder (must contain index.yaml)",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output",
    )

    args = parser.parse_args(argv)

    if not args.job_path:
        parser.print_help()
        return 1

    return run_job(args.job_path, verbose=args.verbose)


def run_job(job_path: str, verbose: bool = False) -> int:
    """Run a bio job from the given path.

    Args:
        job_path: Path to job folder containing index.yaml
        verbose: Enable verbose output

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    from dvc_dat import Dat

    path = Path(job_path)

    # Handle relative paths - look in catalog/jobs if not found directly
    if not path.exists():
        # Try catalog/jobs prefix
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
            print(f"Job completed successfully")
            return 0
        else:
            print(f"Job failed")
            if "error" in metadata:
                print(f"Error: {metadata['error']}", file=sys.stderr)
            return 1

    except Exception as e:
        print(f"Error running job: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
