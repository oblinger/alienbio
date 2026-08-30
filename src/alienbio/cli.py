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
        description="bio — the Alien Biology framework CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  suite run <spec.yaml> [--out DIR] [--dry]   run a declared experiment (catalog/experiments/*.yaml)
  suite resume|aggregate|report <DIR>         continue / rebuild / print a run directory
  config [show | set KEY VALUE]               the framework configuration (keys, model)
  test-matrix [--markdown] [--check]          the capability matrix (roadmap M48.1)
  report [--open] [--no-examples]             run the suite; write what it tested + whether it passed (reports/)

Examples:
  bio suite run catalog/experiments/exp04-zero.yaml --dry
  bio suite run catalog/examples/ecosystem/ecosystem.yaml
  bio test-matrix --check
""",
    )
    parser.add_argument(
        "command",
        nargs="?",
        help="Command (report, run, expand) or path to run as report",
    )
    parser.add_argument(
        "args",
        nargs=argparse.REMAINDER,
        help="Command arguments (everything after the command, flags included, "
        "is handed to the subcommand verbatim; put -v/--version BEFORE the command)",
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

    print(f"bio: unknown command {args.command!r}; one of {sorted(COMMANDS)}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
