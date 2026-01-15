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


# -----------------------------------------------------------------------------
# cd command tests
# -----------------------------------------------------------------------------


class TestCdCommand:
    """Tests for the bio cd CLI command."""

    def test_cd_no_current_dat(self, monkeypatch, tmp_path, capsys):
        """Test cd with no current DAT set."""
        from alienbio.commands import cd

        state_file = tmp_path / "state" / "current_dat"       # non-existent
        monkeypatch.setattr(cd, "STATE_FILE", state_file)

        result = cd.cd_command([])

        assert result == 0
        captured = capsys.readouterr()
        assert "no current DAT" in captured.err

    def test_cd_prints_current_dat(self, monkeypatch, tmp_path, capsys):
        """Test cd prints current DAT when set."""
        from alienbio.commands import cd

        state_file = tmp_path / "current_dat"
        state_file.write_text("/some/path/to/dat")
        monkeypatch.setattr(cd, "STATE_FILE", state_file)

        result = cd.cd_command([])

        assert result == 0
        captured = capsys.readouterr()
        assert "/some/path/to/dat" in captured.out

    def test_cd_sets_current_dat(self, monkeypatch, tmp_path, capsys):
        """Test cd <path> sets current DAT."""
        from alienbio.commands import cd

        state_file = tmp_path / "state" / "current_dat"       # will be created
        monkeypatch.setattr(cd, "STATE_FILE", state_file)

        dat_dir = tmp_path / "mydat"
        dat_dir.mkdir()

        result = cd.cd_command([str(dat_dir)])

        assert result == 0
        assert state_file.exists()
        assert str(dat_dir) in state_file.read_text()
        captured = capsys.readouterr()
        assert str(dat_dir) in captured.out

    def test_cd_rejects_nonexistent_path(self, monkeypatch, tmp_path, capsys):
        """Test cd <path> fails for non-existent path."""
        from alienbio.commands import cd

        state_file = tmp_path / "current_dat"
        monkeypatch.setattr(cd, "STATE_FILE", state_file)

        result = cd.cd_command(["/nonexistent/path"])

        assert result == 1
        captured = capsys.readouterr()
        assert "does not exist" in captured.err

    def test_cd_rejects_file_path(self, monkeypatch, tmp_path, capsys):
        """Test cd <path> fails for file (not directory)."""
        from alienbio.commands import cd

        state_file = tmp_path / "current_dat"
        monkeypatch.setattr(cd, "STATE_FILE", state_file)

        file_path = tmp_path / "somefile.txt"
        file_path.write_text("content")

        result = cd.cd_command([str(file_path)])

        assert result == 1
        captured = capsys.readouterr()
        assert "not a directory" in captured.err

    def test_get_current_dat_helper(self, monkeypatch, tmp_path):
        """Test get_current_dat() helper function."""
        from alienbio.commands import cd

        state_file = tmp_path / "current_dat"
        monkeypatch.setattr(cd, "STATE_FILE", state_file)

        assert cd.get_current_dat() is None                   # no state file

        state_file.write_text("/data/experiments/run1")
        path = cd.get_current_dat()
        assert path == Path("/data/experiments/run1")
