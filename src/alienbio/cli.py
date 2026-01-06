"""Bio CLI: Command-line interface for Bio operations.

Usage:
    bio <command> [args...]     Run a command
    bio <job_path>              Shortcut: run a job (same as 'bio run <path>')
    bio --help                  Show help
    bio --version               Show version

Commands:
    run <path>      Run a job (scenario, suite, or report)
    fetch <path>    Fetch and display a spec (hydrated)
    expand <path>   Expand a spec without hydrating

Examples:
    bio run catalog/jobs/hardcoded_test
    bio catalog/jobs/hardcoded_test          # shortcut for 'bio run'
    bio fetch catalog/scenarios/mutualism
    bio expand catalog/scenarios/mutualism
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
        description="Bio CLI: Run scenarios, fetch specs, and more",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  run <path>      Run a job (scenario, suite, or report)
  fetch <path>    Fetch and display a spec (hydrated)
  expand <path>   Expand a spec without hydrating

Examples:
  bio run catalog/jobs/hardcoded_test
  bio catalog/jobs/hardcoded_test          # shortcut for 'bio run'
  bio fetch catalog/scenarios/mutualism
""",
    )
    parser.add_argument(
        "command",
        nargs="?",
        help="Command to run (run, fetch, expand) or job path",
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

    # Otherwise, treat as job path (shortcut for 'bio run <path>')
    # Pass command as first arg to run
    return COMMANDS["run"]([args.command] + args.args, verbose=args.verbose)


if __name__ == "__main__":
    sys.exit(main())
