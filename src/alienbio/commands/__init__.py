"""CLI commands module.

Each subcommand is implemented in its own file.
The main CLI dispatches to these command modules.

Commands:
    report  - Primary command: run scenario, create Excel report, open it
    run     - Debug: run entity, print result dict
    expand  - Debug: show processed spec without hydrating
"""

from .report import report_command
from .run import run_command
from .expand import expand_command

# Registry of available commands
COMMANDS = {
    "report": report_command,
    "run": run_command,
    "expand": expand_command,
}

__all__ = ["COMMANDS", "report_command", "run_command", "expand_command"]
