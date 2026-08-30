"""The ``bio`` CLI entry point (the commands themselves are tested in test_cli_suite / test_config)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_cli_help():
    """Test that bio --help works."""
    result = subprocess.run(
        [sys.executable, "-m", "alienbio.cli", "--help"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "bio" in result.stdout.lower()
    assert "report" in result.stdout.lower()
