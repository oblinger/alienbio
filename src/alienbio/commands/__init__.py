"""CLI commands module.

Each subcommand is implemented in its own file.
The main CLI dispatches to these command modules.

Commands:
    build       - Build/expand a spec (resolve includes, refs, defaults)
    cd          - Get or set current DAT context
    compare     - Compare multiple agents on the same scenario
    expand      - Debug: show processed spec without hydrating
    fetch       - Fetch and display a spec
    hydrate     - Fully evaluate a spec (resolve all placeholders)
    report      - Primary command: run scenario, print table, save Excel to temp
    run         - Debug: run entity, print result dict
    store       - Store data to a spec path
    view-report - Open the last generated report in spreadsheet app
"""

from .build import build_command
from .cd import cd_command
from .compare import compare_command
from .config_cmd import config_command
from .expand import expand_command
from .fetch import fetch_command
from .hydrate import hydrate_command
from .report import report_command, view_report_command
from .run import run_command
from .store import store_command

# Registry of available commands
COMMANDS = {
    "build": build_command,
    "cd": cd_command,
    "compare": compare_command,
    "config": config_command,
    "expand": expand_command,
    "fetch": fetch_command,
    "hydrate": hydrate_command,
    "report": report_command,
    "run": run_command,
    "store": store_command,
    "view-report": view_report_command,
}

__all__ = [
    "COMMANDS",
    "build_command",
    "cd_command",
    "compare_command",
    "expand_command",
    "fetch_command",
    "hydrate_command",
    "report_command",
    "run_command",
    "store_command",
    "view_report_command",
]
