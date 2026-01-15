"""Bio CLI: Command-line interface for Bio operations.

Usage:
    bio <path>              Run scenario and create report (default)
    bio build <path>        Build spec (resolve includes, refs, defaults)
    bio cd                  Print current DAT path
    bio cd <path>           Set current DAT path
    bio expand <path>       Show processed spec (same as build)
    bio fetch <specifier>   Fetch and display a spec
    bio hydrate <path>      Fully evaluate spec (resolve all placeholders)
    bio report <path>       Run scenario and create Excel report
    bio run <path>          Debug: run entity, print result dict
    bio store <specifier>   Store data from stdin to spec path
    bio --help              Show help
    bio --version           Show version

Examples:
    bio catalog/jobs/hardcoded_test       # Create and open Excel report
    bio cd data/experiments/run1          # Set current DAT
    bio fetch catalog/scenarios/mutualism # Display spec as YAML
    bio hydrate catalog/jobs/test --seed 42  # Evaluate with seed
    echo '{name: test}' | bio store ./test   # Store data to relative path
"""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    """Main entry point for bio CLI.

    Args:
        argv: Command line arguments (defaults to sys.argv[1:])

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    from alienbio import __version__
    from alienbio.commands import COMMANDS

    parser = argparse.ArgumentParser(
        prog="bio",
        description="Bio CLI: Run scenarios and create reports",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  build <path>    Build spec (resolve includes, refs, defaults)
  cd              Print current DAT path
  cd <path>       Set current DAT path
  expand <path>   Show processed spec (same as build)
  fetch <spec>    Fetch and display a spec (--raw, --json)
  hydrate <path>  Fully evaluate spec (resolve all placeholders)
  report <path>   Run scenario and create Excel report (default)
  run <path>      Debug: run entity, print result dict
  store <spec>    Store data from stdin to spec path (--raw)

Examples:
  bio cd data/experiments/run1          # Set current DAT
  bio fetch catalog/scenarios/mutualism # Display spec as YAML
  bio hydrate catalog/jobs/test --seed 42  # Evaluate with seed
  echo '{key: val}' | bio store ./test  # Store to relative path
  bio catalog/jobs/hardcoded_test       # Create and open Excel report
""",
    )
    parser.add_argument(
        "command",
        nargs="?",
        help="Command (report, run, expand) or path to run as report",
    )
    parser.add_argument(
        "args",
        nargs="*",
        help="Command arguments",
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

    if not args.command:
        parser.print_help()
        return 1

    # Check if command is a registered command
    if args.command in COMMANDS:
        return COMMANDS[args.command](args.args, verbose=args.verbose)

    # Otherwise, treat as path and run report (default behavior)
    return COMMANDS["report"]([args.command] + args.args, verbose=args.verbose)


if __name__ == "__main__":
    sys.exit(main())
