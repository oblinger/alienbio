"""Tests for battery CLI commands.

M4.3 - CLI Commands: bio battery and bio battery-report
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import yaml

from alienbio import bio as bio_singleton
from alienbio.commands.battery_cmd import battery_command, battery_report_command


# --- Battery spec helpers ---

def _write_spec(tmp_path: Path, scenarios: list[str], agents: list[str], seeds: list[int]) -> Path:
    """Write a battery spec YAML file."""
    spec = {
        "scenarios": scenarios,
        "agents": agents,
        "seeds": seeds,
    }
    spec_file = tmp_path / "battery_spec.yaml"
    with open(spec_file, "w") as f:
        yaml.dump(spec, f)
    return spec_file


def _write_scenario(tmp_path: Path, name: str = "test_scenario") -> Path:
    """Write a minimal scenario YAML file."""
    scenario = {
        "name": name,
        "briefing": f"Test scenario {name}",
        "constitution": "Rules",
        "interface": {
            "actions": {
                "act1": {"description": "Action 1", "params": {}, "cost": 1.0},
            },
            "measurements": {},
            "budget": 10,
        },
        "sim": {"max_agent_steps": 3, "steps_per_action": 1},
        "containers": {"regions": {"R1": {"substrate": {"M1": 5.0}}}},
        "scoring": {},
        "passing_score": 0.5,
    }
    path = tmp_path / f"{name}.yaml"
    with open(path, "w") as f:
        yaml.dump(scenario, f)
    return path


def _mock_bio_expand(scenario_path: str):
    """Mock bio.expand to load YAML directly."""
    with open(scenario_path) as f:
        return yaml.safe_load(f)


# === battery_command tests ===

class TestBatteryCommandArgs:

    def test_no_args_returns_error(self, capsys):
        result = battery_command([])
        assert result == 1
        assert "requires a spec file" in capsys.readouterr().err

    def test_nonexistent_spec_returns_error(self, capsys):
        result = battery_command(["nonexistent.yaml"])
        assert result == 1
        assert "not found" in capsys.readouterr().err

    def test_invalid_yaml_returns_error(self, tmp_path, capsys):
        bad = tmp_path / "bad.yaml"
        bad.write_text(": : invalid")
        result = battery_command([str(bad)])
        assert result == 1

    def test_non_mapping_spec_returns_error(self, tmp_path, capsys):
        bad = tmp_path / "list.yaml"
        bad.write_text("- item1\n- item2\n")
        result = battery_command([str(bad)])
        assert result == 1
        assert "must be a YAML mapping" in capsys.readouterr().err

    def test_no_scenarios_returns_error(self, tmp_path, capsys):
        spec = tmp_path / "empty.yaml"
        spec.write_text("agents:\n  - random\n")
        result = battery_command([str(spec)])
        assert result == 1
        assert "No scenarios" in capsys.readouterr().err


class TestBatteryCommandExecution:

    def test_runs_battery(self, tmp_path, capsys):
        """Battery runs and prints summary."""
        s1 = _write_scenario(tmp_path, "scenario_1")
        spec = _write_spec(tmp_path, [str(s1)], ["random"], [0])

        with patch("alienbio.commands.battery_cmd.battery_command.__module__"):
            pass  # no-op, just need the import

        # Mock bio.expand to load YAML directly
        with patch.object(bio_singleton, "expand", side_effect=_mock_bio_expand):
            result = battery_command([str(spec)])

        assert result == 0
        output = capsys.readouterr().out
        assert "BATTERY RESULTS" in output

    def test_runs_multiple_scenarios(self, tmp_path, capsys):
        s1 = _write_scenario(tmp_path, "s1")
        s2 = _write_scenario(tmp_path, "s2")
        spec = _write_spec(tmp_path, [str(s1), str(s2)], ["random"], [0])

        with patch.object(bio_singleton, "expand", side_effect=_mock_bio_expand):
            result = battery_command([str(spec)])

        assert result == 0
        output = capsys.readouterr().out
        assert "Total: 2" in output

    def test_runs_multiple_agents(self, tmp_path, capsys):
        s1 = _write_scenario(tmp_path)
        spec = _write_spec(tmp_path, [str(s1)], ["random", "oracle"], [0])

        with patch.object(bio_singleton, "expand", side_effect=_mock_bio_expand):
            result = battery_command([str(spec)])

        assert result == 0
        output = capsys.readouterr().out
        assert "random" in output
        assert "oracle" in output

    def test_runs_multiple_seeds(self, tmp_path, capsys):
        s1 = _write_scenario(tmp_path)
        spec = _write_spec(tmp_path, [str(s1)], ["random"], [0, 1, 2])

        with patch.object(bio_singleton, "expand", side_effect=_mock_bio_expand):
            result = battery_command([str(spec)])

        assert result == 0
        output = capsys.readouterr().out
        assert "Total: 3" in output

    def test_csv_output(self, tmp_path, capsys):
        s1 = _write_scenario(tmp_path)
        spec = _write_spec(tmp_path, [str(s1)], ["random"], [0])

        with patch.object(bio_singleton, "expand", side_effect=_mock_bio_expand):
            result = battery_command([str(spec), "--csv"])

        assert result == 0
        output = capsys.readouterr().out
        assert output.startswith("agent,scenario,seed,passed")

    def test_json_output(self, tmp_path, capsys):
        s1 = _write_scenario(tmp_path)
        spec = _write_spec(tmp_path, [str(s1)], ["random"], [0])

        with patch.object(bio_singleton, "expand", side_effect=_mock_bio_expand):
            result = battery_command([str(spec), "--json"])

        assert result == 0
        doc = json.loads(capsys.readouterr().out)
        assert doc["total"] == 1
        assert "entries" in doc

    def test_save_results(self, tmp_path, capsys):
        s1 = _write_scenario(tmp_path)
        spec = _write_spec(tmp_path, [str(s1)], ["random"], [0])
        save_path = tmp_path / "output"

        with patch.object(bio_singleton, "expand", side_effect=_mock_bio_expand):
            result = battery_command([str(spec), "--save", str(save_path)])

        assert result == 0
        assert (tmp_path / "output.yaml").exists()

    def test_verbose_progress(self, tmp_path, capsys):
        s1 = _write_scenario(tmp_path)
        spec = _write_spec(tmp_path, [str(s1)], ["random"], [0])

        with patch.object(bio_singleton, "expand", side_effect=_mock_bio_expand):
            result = battery_command([str(spec)], verbose=True)

        assert result == 0
        output = capsys.readouterr().out
        assert "[1/1]" in output

    def test_unknown_agent_returns_error(self, tmp_path, capsys):
        s1 = _write_scenario(tmp_path)
        spec = _write_spec(tmp_path, [str(s1)], ["nonexistent_agent"], [0])

        with patch.object(bio_singleton, "expand", side_effect=_mock_bio_expand):
            result = battery_command([str(spec)])

        assert result == 1
        assert "Unknown agent type" in capsys.readouterr().err

    def test_bad_scenario_path_returns_error(self, tmp_path, capsys):
        spec = _write_spec(tmp_path, ["nonexistent.yaml"], ["random"], [0])

        with patch.object(bio_singleton, "expand", side_effect=FileNotFoundError("not found")):
            result = battery_command([str(spec)])

        assert result == 1


# === battery_report_command tests ===

class TestBatteryReportCommand:

    def _save_battery(self, tmp_path: Path) -> Path:
        """Run a battery and save results for report tests."""
        from alienbio.agent import (
            ExperimentBattery, RandomAgent, OracleAgent,
        )
        from alienbio.agent.results_store import save_results

        scenarios = [
            {
                "name": "s1",
                "briefing": "Test",
                "constitution": "Rules",
                "interface": {
                    "actions": {"act": {"description": "A", "params": {}, "cost": 1.0}},
                    "measurements": {},
                    "budget": 10,
                },
                "sim": {"max_agent_steps": 3, "steps_per_action": 1},
                "containers": {"regions": {"R": {"substrate": {"M": 5.0}}}},
                "scoring": {},
                "passing_score": 0.5,
            },
        ]
        battery = ExperimentBattery(
            scenarios=scenarios,
            agents={"random": RandomAgent(seed=0), "oracle": OracleAgent()},
            seeds=[0, 1],
        )
        result = battery.run()
        return save_results(result, tmp_path / "saved_results")

    def test_no_args_returns_error(self, capsys):
        result = battery_report_command([])
        assert result == 1
        assert "requires a results file" in capsys.readouterr().err

    def test_nonexistent_returns_error(self, capsys):
        result = battery_report_command(["nonexistent.yaml"])
        assert result == 1
        assert "not found" in capsys.readouterr().err

    def test_report_console(self, tmp_path, capsys):
        path = self._save_battery(tmp_path)
        result = battery_report_command([str(path)])
        assert result == 0
        output = capsys.readouterr().out
        assert "BATTERY RESULTS" in output
        assert "random" in output
        assert "oracle" in output

    def test_report_csv(self, tmp_path, capsys):
        path = self._save_battery(tmp_path)
        result = battery_report_command([str(path), "--csv"])
        assert result == 0
        output = capsys.readouterr().out
        assert output.startswith("agent,scenario")
        lines = output.strip().split("\n")
        assert len(lines) == 5  # header + 4 entries (2 agents × 2 seeds)

    def test_report_json(self, tmp_path, capsys):
        path = self._save_battery(tmp_path)
        result = battery_report_command([str(path), "--json"])
        assert result == 0
        doc = json.loads(capsys.readouterr().out)
        assert doc["total"] == 4

    def test_report_filter_agent(self, tmp_path, capsys):
        path = self._save_battery(tmp_path)
        result = battery_report_command([str(path), "--agent", "random"])
        assert result == 0
        output = capsys.readouterr().out
        assert "Total: 2" in output

    def test_report_filter_scenario(self, tmp_path, capsys):
        path = self._save_battery(tmp_path)
        result = battery_report_command([str(path), "--scenario", "s1"])
        assert result == 0
        output = capsys.readouterr().out
        assert "Total: 4" in output

    def test_report_filter_no_match(self, tmp_path, capsys):
        path = self._save_battery(tmp_path)
        result = battery_report_command([str(path), "--agent", "nonexistent"])
        assert result == 1
        assert "No results match" in capsys.readouterr().err


# === Battery spec format tests ===

class TestBatterySpecFormat:

    def test_minimal_spec(self, tmp_path, capsys):
        """Spec with just scenarios works (defaults to random agent, seed 0)."""
        s1 = _write_scenario(tmp_path)
        spec_file = tmp_path / "spec.yaml"
        with open(spec_file, "w") as f:
            yaml.dump({"scenarios": [str(s1)]}, f)

        with patch.object(bio_singleton, "expand", side_effect=_mock_bio_expand):
            result = battery_command([str(spec_file)])

        assert result == 0
        output = capsys.readouterr().out
        assert "Total: 1" in output

    def test_full_spec(self, tmp_path, capsys):
        """Full spec with all fields works."""
        s1 = _write_scenario(tmp_path, "s1")
        s2 = _write_scenario(tmp_path, "s2")
        spec_file = tmp_path / "spec.yaml"
        with open(spec_file, "w") as f:
            yaml.dump({
                "scenarios": [str(s1), str(s2)],
                "agents": ["random", "oracle"],
                "seeds": [0, 1, 2],
            }, f)

        with patch.object(bio_singleton, "expand", side_effect=_mock_bio_expand):
            result = battery_command([str(spec_file)])

        assert result == 0
        output = capsys.readouterr().out
        # 2 scenarios × 2 agents × 3 seeds = 12
        assert "Total: 12" in output


# === End-to-end: battery → save → report ===

class TestEndToEnd:

    def test_battery_save_then_report(self, tmp_path, capsys):
        """Run battery, save results, load and report."""
        s1 = _write_scenario(tmp_path)
        spec = _write_spec(tmp_path, [str(s1)], ["random", "oracle"], [0, 1])
        save_path = tmp_path / "results"

        with patch.object(bio_singleton, "expand", side_effect=_mock_bio_expand):
            rc = battery_command([str(spec), "--save", str(save_path)])
        assert rc == 0

        # Now report from saved results
        capsys.readouterr()  # clear
        rc = battery_report_command([str(tmp_path / "results.yaml")])
        assert rc == 0
        output = capsys.readouterr().out
        assert "Total: 4" in output
        assert "random" in output
        assert "oracle" in output

    def test_battery_save_then_filter_report(self, tmp_path, capsys):
        """Save battery, then report with filter."""
        s1 = _write_scenario(tmp_path)
        spec = _write_spec(tmp_path, [str(s1)], ["random", "oracle"], [0, 1])
        save_path = tmp_path / "results"

        with patch.object(bio_singleton, "expand", side_effect=_mock_bio_expand):
            battery_command([str(spec), "--save", str(save_path)])

        capsys.readouterr()
        rc = battery_report_command([
            str(tmp_path / "results.yaml"), "--agent", "oracle", "--csv",
        ])
        assert rc == 0
        output = capsys.readouterr().out
        lines = output.strip().split("\n")
        assert len(lines) == 3  # header + 2 oracle entries
        assert all("oracle" in line for line in lines[1:])
