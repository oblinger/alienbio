"""Tests for the compare command."""

from __future__ import annotations

import pytest

from alienbio.commands.compare import compare_command


class TestCompareCommand:
    """Tests for the compare_command function."""

    def test_no_args_returns_error(self, capsys):
        """Test error when no arguments provided."""
        result = compare_command([])
        assert result == 1

        captured = capsys.readouterr()
        assert "Error" in captured.err
        assert "compare command requires" in captured.err

    def test_nonexistent_scenario_returns_error(self, capsys):
        """Test error when scenario doesn't exist."""
        result = compare_command(["nonexistent_scenario.yaml"])
        assert result == 1

        captured = capsys.readouterr()
        assert "Scenario not found" in captured.err

    def test_parse_agents_flag(self):
        """Test parsing --agents flag."""
        # We can't easily test the full flow without a real scenario,
        # but we can verify the command doesn't crash with valid args structure
        result = compare_command(["nonexistent.yaml", "--agents", "random,oracle"])
        assert result == 1  # Fails due to missing file, but parsing worked

    def test_parse_runs_flag(self):
        """Test parsing --runs flag."""
        result = compare_command(["nonexistent.yaml", "--runs", "5"])
        assert result == 1  # Fails due to missing file

    def test_parse_output_format_flags(self):
        """Test parsing --csv and --json flags."""
        result = compare_command(["nonexistent.yaml", "--csv"])
        assert result == 1

        result = compare_command(["nonexistent.yaml", "--json"])
        assert result == 1
