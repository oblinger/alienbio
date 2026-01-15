"""cd command: Get or set current DAT context."""

from __future__ import annotations

import sys
from pathlib import Path


STATE_FILE = Path.home() / ".bio" / "current_dat"


def cd_command(args: list[str], verbose: bool = False) -> int:
    """Get or set the current DAT context.

    With no arguments, prints the current DAT path.
    With a path argument, sets the current DAT and prints it.

    Args:
        args: Command arguments [path] (optional)
        verbose: Enable verbose output

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    if not args:
        return _print_current_dat(verbose)                # no args — print current
    return _set_current_dat(args[0], verbose)             # with path — set current


def _print_current_dat(verbose: bool) -> int:
    """Print the current DAT path."""
    if not STATE_FILE.exists():
        print("(no current DAT set)", file=sys.stderr)
        return 0

    path = STATE_FILE.read_text().strip()
    if verbose:
        print(f"Current DAT: {path}")
    else:
        print(path)
    return 0


def _set_current_dat(path_str: str, verbose: bool) -> int:
    """Set the current DAT path."""
    path = Path(path_str).expanduser().resolve()

    if not path.exists():
        print(f"Error: Path does not exist: {path}", file=sys.stderr)
        return 1

    if not path.is_dir():
        print(f"Error: Path is not a directory: {path}", file=sys.stderr)
        return 1

    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)  # ensure ~/.bio exists
    STATE_FILE.write_text(str(path))

    if verbose:
        print(f"Current DAT set to: {path}")
    else:
        print(path)
    return 0


def get_current_dat() -> Path | None:
    """Get the current DAT path from state file.

    Used by other commands to access the current DAT context.

    Returns:
        Path to current DAT, or None if not set
    """
    if not STATE_FILE.exists():
        return None
    path_str = STATE_FILE.read_text().strip()
    if not path_str:
        return None
    return Path(path_str)
