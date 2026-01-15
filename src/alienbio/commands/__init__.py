"""CLI commands module.

Each subcommand is implemented in its own file.
The main CLI dispatches to these command modules.

Commands:
    report      - Primary command: run scenario, print table, save Excel to temp
    view-report - Open the last generated report in spreadsheet app
    run         - Debug: run entity, print result dict
    expand      - Debug: show processed spec without hydrating
    cd          - Get or set current DAT context
"""

from .cd import cd_command
from .expand import expand_command
from .report import report_command, view_report_command
from .run import run_command

# Registry of available commands
COMMANDS = {
    "cd": cd_command,
    "expand": expand_command,
    "report": report_command,
    "run": run_command,
    "view-report": view_report_command,
}

__all__ = [
    "COMMANDS",
    "cd_command",
    "expand_command",
    "report_command",
    "run_command",
    "view_report_command",
]
