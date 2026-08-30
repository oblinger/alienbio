"""The ``bio`` CLI commands.

Commands:
    suite        - run / resume / aggregate / report a declared experiment
    config       - show / set the framework configuration (keys, model)
    test-matrix  - the capability matrix: dimensions and the tests that prove them
    report       - run the suite and write what it tested, and whether it passed, as one page
"""

from __future__ import annotations

from .config_cmd import config_command
from .report_cmd import report_command
from .suite_cmd import suite_command
from .test_matrix_cmd import test_matrix_command

COMMANDS = {
    "config": config_command,
    "report": report_command,
    "suite": suite_command,
    "test-matrix": test_matrix_command,
}

__all__ = ["COMMANDS", "config_command", "report_command", "suite_command", "test_matrix_command"]
