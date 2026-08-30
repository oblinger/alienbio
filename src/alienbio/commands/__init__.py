"""The ``bio`` CLI commands.

Commands:
    suite        - run / resume / aggregate / report a declared experiment
    config       - show / set the framework configuration (keys, model)
    test-matrix  - the capability matrix: dimensions and the tests that prove them
"""

from __future__ import annotations

from .config_cmd import config_command
from .suite_cmd import suite_command
from .test_matrix_cmd import test_matrix_command

COMMANDS = {
    "config": config_command,
    "suite": suite_command,
    "test-matrix": test_matrix_command,
}

__all__ = ["COMMANDS", "config_command", "suite_command", "test_matrix_command"]
