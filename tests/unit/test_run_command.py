"""Tests for the run command."""

from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from alienbio.commands.run import (
    _is_dat,
    _parse_args,
    _create_agent,
    run_command,
)


class TestIsDat:
    """Tests for the _is_dat function."""

    def test_not_a_directory(self, tmp_path):
        """Test that non-directories return False."""
        file_path = tmp_path / "test.yaml"
        file_path.write_text("name: test")
        assert _is_dat(file_path) is False

    def test_directory_without_spec(self, tmp_path):
        """Test that directories without _spec_.yaml return False."""
        assert _is_dat(tmp_path) is False

    def test_directory_with_spec(self, tmp_path):
        """Test that directories with _spec_.yaml return True."""
        spec_file = tmp_path / "_spec_.yaml"
        spec_file.write_text("kind: test")
        assert _is_dat(tmp_path) is True


class TestParseArgs:
    """Tests for the _parse_args function."""

    def test_path_only(self):
        """Test parsing path only."""
        path, options = _parse_args(["scenario.yaml"])
        assert path == "scenario.yaml"
        assert options == {}

    def test_path_with_seed(self):
        """Test parsing path with --seed."""
        path, options = _parse_args(["scenario.yaml", "--seed", "42"])
        assert path == "scenario.yaml"
        assert options == {"seed": "42"}

    def test_path_with_agent(self):
        """Test parsing path with --agent."""
        path, options = _parse_args(["scenario.yaml", "--agent", "anthropic"])
        assert path == "scenario.yaml"
        assert options == {"agent": "anthropic"}

    def test_path_with_multiple_options(self):
        """Test parsing path with multiple options."""
        path, options = _parse_args([
            "scenario.yaml",
            "--seed", "42",
            "--agent", "random",
            "--model", "claude-3-5-sonnet"
        ])
        assert path == "scenario.yaml"
        assert options == {
            "seed": "42",
            "agent": "random",
            "model": "claude-3-5-sonnet"
        }

    def test_no_args(self):
        """Test parsing no arguments."""
        path, options = _parse_args([])
        assert path is None
        assert options == {}


class TestCreateAgent:
    """Tests for the _create_agent function."""

    def test_create_random_agent(self):
        """Test creating a random agent."""
        from alienbio.agent import RandomAgent
        agent = _create_agent("random", seed=42)
        assert isinstance(agent, RandomAgent)

    def test_create_oracle_agent(self):
        """Test creating an oracle agent."""
        from alienbio.agent import OracleAgent
        agent = _create_agent("oracle")
        assert isinstance(agent, OracleAgent)

    def test_create_human_agent(self):
        """Test creating a human agent."""
        from alienbio.agent import HumanAgent
        agent = _create_agent("human")
        assert isinstance(agent, HumanAgent)

    def test_unknown_agent_raises(self):
        """Test that unknown agent type raises ValueError."""
        with pytest.raises(ValueError, match="Unknown agent type"):
            _create_agent("unknown")


class TestRunCommand:
    """Tests for the run_command function."""

    def test_no_args_returns_error(self, capsys):
        """Test error when no arguments provided."""
        result = run_command([])
        assert result == 1

        captured = capsys.readouterr()
        assert "Error" in captured.err
        assert "requires a scenario path" in captured.err

    def test_nonexistent_path_returns_error(self, capsys):
        """Test error when path doesn't exist."""
        result = run_command(["nonexistent_scenario.yaml"])
        assert result == 1

        captured = capsys.readouterr()
        assert "Path not found" in captured.err


class TestDatExecution:
    """Tests for DAT execution sandboxing."""

    def test_dat_execution_creates_sandbox(self, tmp_path):
        """Test that DAT execution creates a sandboxed Bio."""
        # Create a DAT folder
        dat_path = tmp_path / "test_dat"
        dat_path.mkdir()
        (dat_path / "_spec_.yaml").write_text("kind: bio_dat\ndo: alienbio.do_bio")
        (dat_path / "index.yaml").write_text("""
name: test_scenario
briefing: Test scenario
interface:
  actions: {}
  measurements: {}
  budget: 10.0
sim:
  max_agent_steps: 5
""")

        # Verify it's detected as DAT
        assert _is_dat(dat_path) is True

        # Mock run_experiment to avoid actual execution
        mock_results = MagicMock()
        mock_results.scenario = "test_scenario"
        mock_results.status = "completed"
        mock_results.passed = True
        mock_results.seed = None
        mock_results.scores = {"budget_compliance": 1.0}
        mock_results.trace.total_cost = 0.0
        mock_results.incomplete_reason = None

        with patch("alienbio.agent.run_experiment") as mock_run:
            mock_run.return_value = mock_results

            # Mock Dat.load and save to avoid dvc_dat complexity
            with patch("dvc_dat.Dat") as mock_dat_class:
                mock_dat = MagicMock()
                mock_dat_class.load.return_value = mock_dat

                result = run_command([str(dat_path)], verbose=True)

                # Should succeed
                assert result == 0

                # Dat.load should have been called with the DAT path
                mock_dat_class.load.assert_called_once_with(dat_path)

                # Results should have been saved
                mock_dat.save.assert_called_once()

    def test_non_dat_uses_global_bio(self, tmp_path, capsys):
        """Test that non-DAT execution doesn't create sandbox."""
        # Create a regular scenario file (not a DAT)
        scenario_path = tmp_path / "scenario.yaml"
        scenario_path.write_text("""
name: test_scenario
briefing: Test scenario
interface:
  actions: {}
  measurements: {}
  budget: 10.0
sim:
  max_agent_steps: 5
""")

        # Verify it's not detected as DAT
        assert _is_dat(scenario_path) is False

        # Mock run_experiment
        mock_results = MagicMock()
        mock_results.scenario = "test_scenario"
        mock_results.status = "completed"
        mock_results.passed = True
        mock_results.seed = None
        mock_results.scores = {"budget_compliance": 1.0}
        mock_results.trace.total_cost = 0.0
        mock_results.incomplete_reason = None

        with patch("alienbio.agent.run_experiment") as mock_run:
            mock_run.return_value = mock_results

            result = run_command([str(scenario_path)])

            # Should succeed
            assert result == 0

            # run_experiment should have been called
            mock_run.assert_called_once()

        # Check output doesn't mention DAT
        captured = capsys.readouterr()
        assert "DAT" not in captured.out or "DAT:" not in captured.out
