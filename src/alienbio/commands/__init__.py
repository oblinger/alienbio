"""The ``bio`` CLI commands.

Commands:
    suite      - run / resume / aggregate / report a declared experiment
    config     - show / set the framework configuration (keys, model)
"""

from __future__ import annotations

from .config_cmd import config_command
from .suite_cmd import suite_command

COMMANDS = {
    "config": config_command,
    "suite": suite_command,
}

__all__ = ["COMMANDS", "config_command", "suite_command"]
