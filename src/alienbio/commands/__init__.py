"""CLI commands module.

Each subcommand is implemented in its own file.
The main CLI dispatches to these command modules.

Commands:
    report      - Primary command: run scenario, print table, save Excel to temp
    view-report - Open the last generated report in spreadsheet app
    run         - Debug: run entity, print result dict
    expand      - Debug: show processed spec without hydrating
"""

from .report import report_command, view_report_command
from .run import run_command
from .expand import expand_command

# Registry of available commands
COMMANDS = {
    "report": report_command,
    "view-report": view_report_command,
    "run": run_command,
    "expand": expand_command,
}

__all__ = ["COMMANDS", "report_command", "view_report_command", "run_command", "expand_command"]
