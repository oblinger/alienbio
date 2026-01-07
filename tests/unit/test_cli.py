"""Tests for the bio CLI."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_cli_report_hardcoded_test():
    """Test that bio report runs hardcoded_test and produces correct output."""
    # Run the CLI
    result = subprocess.run(
        [sys.executable, "-m", "alienbio.cli", "src/alienbio/catalog/jobs/hardcoded_test"],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent.parent,  # alienbio root
    )

    # Should succeed
    assert result.returncode == 0, f"CLI failed: {result.stderr}"

    output = result.stdout

    # Verify concentrations changed as expected
    assert "A': 0.0" in output or "A': 0" in output, "A should be depleted"
    assert "B': 0.0" in output or "B': 0" in output, "B should be depleted"
    assert "D':" in output and "9.9" in output, "D should have accumulated"

    # Verify scoring
    assert "Score:" in output, "Should show score"
    assert "PASSED" in output, "Should show PASSED"

    # Verify assertions passed
    assert "✓" in output, "Should show checkmarks for passing assertions"


def test_cli_run_hardcoded_test():
    """Test that bio run prints result dict."""
    result = subprocess.run(
        [sys.executable, "-m", "alienbio.cli", "run", "src/alienbio/catalog/jobs/hardcoded_test"],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent.parent,
    )

    assert result.returncode == 0, f"CLI failed: {result.stderr}"

    output = result.stdout

    # Should show YAML-formatted result dict
    assert "--- Result ---" in output, "Should show result header"
    assert "final_state:" in output, "Should show final_state"
    assert "scores:" in output, "Should show scores"
    assert "Success: True" in output, "Should show success"


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
