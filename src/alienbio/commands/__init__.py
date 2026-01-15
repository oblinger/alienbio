"""CLI commands module.

Each subcommand is implemented in its own file.
The main CLI dispatches to these command modules.

Commands:
    cd          - Get or set current DAT context
    expand      - Debug: show processed spec without hydrating
    fetch       - Fetch and display a spec
    report      - Primary command: run scenario, print table, save Excel to temp
    run         - Debug: run entity, print result dict
    store       - Store data to a spec path
    view-report - Open the last generated report in spreadsheet app
"""

from .cd import cd_command
from .expand import expand_command
from .fetch import fetch_command
from .report import report_command, view_report_command
from .run import run_command
from .store import store_command

# Registry of available commands
COMMANDS = {
    "cd": cd_command,
    "expand": expand_command,
    "fetch": fetch_command,
    "report": report_command,
    "run": run_command,
    "store": store_command,
    "view-report": view_report_command,
}

__all__ = [
    "COMMANDS",
    "cd_command",
    "expand_command",
    "fetch_command",
    "report_command",
    "run_command",
    "store_command",
    "view_report_command",
]
