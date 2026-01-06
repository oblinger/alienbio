"""CLI commands module.

Each subcommand is implemented in its own file (run.py, fetch.py, etc.).
The main CLI dispatches to these command modules.
"""

from .run import run_command
from .fetch import fetch_command
from .expand import expand_command

# Registry of available commands
COMMANDS = {
    "run": run_command,
    "fetch": fetch_command,
    "expand": expand_command,
}

__all__ = ["COMMANDS", "run_command", "fetch_command", "expand_command"]
