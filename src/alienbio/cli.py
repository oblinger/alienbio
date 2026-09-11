"""Bio CLI — the ``bio`` front door.

``bio <command> [args...]`` hands everything after the command to that
command's own parser (each has ``--help``). The commands are the
:data:`alienbio.commands.COMMANDS` registry; ``bio --help`` lists them from
it, so this page cannot drift from what runs (T051 box 4 found it
documenting eight verbs that no longer existed).
"""

from __future__ import annotations

import argparse
import sys


def _summary(fn: object) -> str:
    """The first line of a command module's docstring — its one-line usage."""
    doc = (sys.modules[fn.__module__].__doc__ or "").strip()  # type: ignore[attr-defined]
    return doc.splitlines()[0].strip() if doc else ""


def main(argv: list[str] | None = None) -> int:
    """Main entry point for bio CLI.

    Args:
        argv: Command line arguments (defaults to sys.argv[1:])

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    from alienbio import __version__
    from alienbio.commands import COMMANDS

    commands = "\n".join(f"  {name:<12} {_summary(fn)}" for name, fn in sorted(COMMANDS.items()))
    parser = argparse.ArgumentParser(
        prog="bio",
        description="bio — the Alien Biology framework CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Commands (each takes --help):
{commands}

Examples:
  bio suite run catalog/experiments/exp04-zero.yaml --dry
  bio suite run catalog/examples/ecosystem/ecosystem.yaml
  bio test-matrix --check
""",
    )
    parser.add_argument(
        "command",
        nargs="?",
        help=f"one of {', '.join(sorted(COMMANDS))}",
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
