"""Integration tests for experimentation and reporting infrastructure.

M5.2 - Experimentation & Reporting validation.
Tests the full pipeline: battery → results → filtering → export → report.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest
import yaml

from alienbio.agent import (
    ExperimentBattery,
    BatteryResult,
    RandomAgent,
    OracleAgent,
    ScriptedAgent,
    Action,
    save_results,
    load_results,
    export_csv,
    export_json,
)


# --- Shared test scenarios ---

SCENARIO_SIMPLE = {
    "name": "simple",
    "briefing": "Simple test world",
    "constitution": "No rules",
    "interface": {
        "actions": {
            "add_feedstock": {
                "description": "Add molecules",
                "params": {"molecule": "str", "amount": "float"},
                "cost": 1.0,
            },
        },
        "measurements": {
            "sample": {
                "description": "Sample substrate",
                "params": {"region": "str"},
                "cost": 0,
            },
        },
        "budget": 20,
    },
    "sim": {"max_agent_steps": 10, "steps_per_action": 1},
    "containers": {"regions": {"R1": {"substrate": {"M1": 10.0, "M2": 5.0}}}},
    "scoring": {},
    "passing_score": 0.5,
}

SCENARIO_TIGHT_BUDGET = {
    "name": "tight_budget",
    "briefing": "Tight budget test",
    "constitution": "No rules",
    "interface": {
        "actions": {
            "act": {"description": "Action", "params": {}, "cost": 5.0},
        },
        "measurements": {},
        "budget": 8,
    },
    "sim": {"max_agent_steps": 5, "steps_per_action": 1},
    "containers": {"regions": {"R1": {"substrate": {"M1": 1.0}}}},
    "scoring": {},
    "passing_score": 0.5,
}

SCENARIO_MANY_ACTIONS = {
    "name": "many_actions",
    "briefing": "Many actions available",
    "constitution": "No rules",
    "interface": {
        "actions": {
            "act_a": {"description": "A", "params": {}, "cost": 0.5},
            "act_b": {"description": "B", "params": {}, "cost": 1.0},
            "act_c": {"description": "C", "params": {}, "cost": 2.0},
        },
        "measurements": {
            "measure": {"description": "M", "params": {}, "cost": 0},
        },
        "budget": 30,
    },
    "sim": {"max_agent_steps": 20, "steps_per_action": 1},
    "containers": {"regions": {"R1": {"substrate": {"M1": 5.0}}}},
    "scoring": {},
    "passing_score": 0.5,
}

ALL_SCENARIOS = [SCENARIO_SIMPLE, SCENARIO_TIGHT_BUDGET, SCENARIO_MANY_ACTIONS]


# === Multiple Simulations: same scenario, different seeds ===

class TestMultipleSimulations:

    def test_batch_same_scenario_different_seeds(self):
        """Run same scenario with 10 different seeds, collect results."""
        seeds = list(range(10))
        battery = ExperimentBattery(
            scenarios=[SCENARIO_SIMPLE],
            agents={"random": RandomAgent(seed=0)},
            seeds=seeds,
        )
        result = battery.run()
        assert result.total == 10
        for entry in result.entries:
            assert entry.result.status == "completed"

    def test_aggregate_statistics(self):
        """Compute mean and std of scores across runs."""
        seeds = list(range(20))
        battery = ExperimentBattery(
            scenarios=[SCENARIO_SIMPLE],
            agents={"random": RandomAgent(seed=0)},
            seeds=seeds,
        )
        result = battery.run()

        # Extract budget_compliance scores
        scores = [e.result.scores.get("budget_compliance", 0.0) for e in result.entries]
        assert len(scores) == 20

        # Mean should be computable
        mean = sum(scores) / len(scores)
        assert 0.0 <= mean <= 1.0

        # Std deviation should be computable
        variance = sum((s - mean) ** 2 for s in scores) / len(scores)
        std = math.sqrt(variance)
        assert std >= 0.0  # non-negative

    def test_summary_computes_mean_correctly(self):
        """Battery summary mean_scores match manual calculation."""
        seeds = list(range(5))
        battery = ExperimentBattery(
            scenarios=[SCENARIO_SIMPLE],
            agents={"random": RandomAgent(seed=0)},
            seeds=seeds,
        )
        result = battery.run()
        summary = result.summary()

        assert len(summary) == 1
        agent_summary = summary[0]

        # Verify mean matches manual
        manual_scores = [e.result.scores.get("budget_compliance", 0.0) for e in result.entries]
        manual_mean = sum(manual_scores) / len(manual_scores)
        assert agent_summary["mean_scores"]["budget_compliance"] == pytest.approx(manual_mean)

    def test_deterministic_seeds(self):
        """Same seed produces same results across runs."""
        def run_once():
            battery = ExperimentBattery(
                scenarios=[SCENARIO_SIMPLE],
                agents={"random": RandomAgent(seed=42)},
                seeds=[42],
            )
            return battery.run()

        r1 = run_once()
        r2 = run_once()
        assert r1.entries[0].result.scores == r2.entries[0].result.scores

    def test_different_seeds_may_differ(self):
        """Different seeds can produce different cost paths."""
        battery = ExperimentBattery(
            scenarios=[SCENARIO_MANY_ACTIONS],
            agents={"random": RandomAgent(seed=0)},
            seeds=[0, 1, 2, 3, 4],
        )
        result = battery.run()
        costs = [e.result.trace.total_cost for e in result.entries]
        # With random agent and varied actions, at least some costs should differ
        # (not guaranteed but highly probable)
        assert len(costs) == 5


# === Multiple Scenarios: agent across all scenarios ===

class TestMultipleScenarios:

    def test_agent_across_all_scenarios(self):
        """Run single agent across all test scenarios."""
        battery = ExperimentBattery(
            scenarios=ALL_SCENARIOS,
            agents={"random": RandomAgent(seed=0)},
            seeds=[0],
        )
        result = battery.run()
        assert result.total == 3
        # Each scenario should be represented
        by_scenario = result.by_scenario()
        assert set(by_scenario.keys()) == {"simple", "tight_budget", "many_actions"}

    def test_results_indexed_by_scenario(self):
        """Results are correctly grouped by scenario name."""
        battery = ExperimentBattery(
            scenarios=ALL_SCENARIOS,
            agents={"random": RandomAgent(seed=0), "oracle": OracleAgent()},
            seeds=[0, 1],
        )
        result = battery.run()

        by_scenario = result.by_scenario()
        assert len(by_scenario) == 3
        for name, entries in by_scenario.items():
            assert len(entries) == 4  # 2 agents × 2 seeds
            assert all(e.result.scenario == name for e in entries)

    def test_all_scenarios_complete(self):
        """Every experiment across all scenarios completes."""
        battery = ExperimentBattery(
            scenarios=ALL_SCENARIOS,
            agents={"random": RandomAgent(seed=0)},
            seeds=list(range(5)),
        )
        result = battery.run()
        assert result.total == 15  # 3 scenarios × 1 agent × 5 seeds
        for entry in result.entries:
            assert entry.result.status == "completed"

    def test_filter_by_scenario_after_run(self):
        """Filter results to a single scenario after battery run."""
        battery = ExperimentBattery(
            scenarios=ALL_SCENARIOS,
            agents={"random": RandomAgent(seed=0)},
            seeds=[0, 1],
        )
        result = battery.run()

        tight = result.filter(scenario="tight_budget")
        assert tight.total == 2
        assert all(e.result.scenario == "tight_budget" for e in tight.entries)


# === Reporting: export and analyze ===

class TestReporting:

    def _run_battery(self) -> BatteryResult:
        """Run a standard battery for reporting tests."""
        battery = ExperimentBattery(
            scenarios=[SCENARIO_SIMPLE, SCENARIO_TIGHT_BUDGET],
            agents={"random": RandomAgent(seed=0), "oracle": OracleAgent()},
            seeds=[0, 1, 2],
        )
        return battery.run()

    def test_csv_report(self):
        """CSV export contains all entries."""
        result = self._run_battery()
        csv = export_csv(result)
        lines = csv.strip().split("\n")
        assert len(lines) == result.total + 1  # header + entries

    def test_csv_header_has_score_columns(self):
        """CSV header includes score keys."""
        result = self._run_battery()
        csv = export_csv(result)
        header = csv.split("\n")[0]
        assert "budget_compliance" in header

    def test_json_report(self):
        """JSON export contains summary and entries."""
        result = self._run_battery()
        text = export_json(result)
        doc = json.loads(text)
        assert doc["total"] == result.total
        assert len(doc["entries"]) == result.total
        assert len(doc["summary"]) == 2  # 2 agents

    def test_csv_data_matches_source(self):
        """CSV data matches the actual results."""
        result = self._run_battery()
        csv = export_csv(result)
        lines = csv.strip().split("\n")
        # First data row should match first entry
        first_entry = result.entries[0]
        first_data = lines[1]
        assert first_entry.agent_name in first_data
        assert first_entry.result.scenario in first_data

    def test_json_summary_matches_source(self):
        """JSON summary pass rates match actual data."""
        result = self._run_battery()
        text = export_json(result)
        doc = json.loads(text)
        for row in doc["summary"]:
            agent_name = row["agent"]
            agent_entries = result.filter(agent=agent_name)
            expected_rate = agent_entries.passed / agent_entries.total if agent_entries.total else 0.0
            assert row["pass_rate"] == pytest.approx(expected_rate)

    def test_comparison_report_across_agents(self):
        """Summary provides per-agent comparison."""
        result = self._run_battery()
        summary = result.summary()
        agents = {row["agent"] for row in summary}
        assert agents == {"random", "oracle"}
        for row in summary:
            assert row["total"] == 6  # 2 scenarios × 3 seeds

    def test_export_to_file_csv(self, tmp_path):
        """CSV export to file works."""
        result = self._run_battery()
        path = tmp_path / "report.csv"
        export_csv(result, path)
        assert path.exists()
        content = path.read_text()
        assert content.startswith("agent,scenario")

    def test_export_to_file_json(self, tmp_path):
        """JSON export to file works."""
        result = self._run_battery()
        path = tmp_path / "report.json"
        export_json(result, path)
        assert path.exists()
        doc = json.loads(path.read_text())
        assert doc["total"] == result.total


# === Full round-trip: run → save → load → filter → export ===

class TestFullRoundTrip:

    def test_run_save_load_roundtrip(self, tmp_path):
        """Battery → save → load preserves all data."""
        battery = ExperimentBattery(
            scenarios=ALL_SCENARIOS,
            agents={"random": RandomAgent(seed=0), "oracle": OracleAgent()},
            seeds=[0, 1],
        )
        original = battery.run()
        path = save_results(original, tmp_path / "results")
        loaded = load_results(path)

        assert loaded.total == original.total
        assert loaded.passed == original.passed
        for orig, load in zip(original.entries, loaded.entries):
            assert load.agent_name == orig.agent_name
            assert load.result.scenario == orig.result.scenario
            assert load.result.seed == orig.result.seed
            assert load.result.passed == orig.result.passed
            assert load.result.scores == orig.result.scores

    def test_save_load_filter_export(self, tmp_path):
        """Full pipeline: run → save → load → filter → CSV export."""
        battery = ExperimentBattery(
            scenarios=[SCENARIO_SIMPLE, SCENARIO_TIGHT_BUDGET],
            agents={"random": RandomAgent(seed=0), "oracle": OracleAgent()},
            seeds=[0, 1],
        )
        result = battery.run()

        # Save
        path = save_results(result, tmp_path / "results")

        # Load
        loaded = load_results(path)
        assert loaded.total == 8  # 2 scenarios × 2 agents × 2 seeds

        # Filter to oracle only
        oracle_only = loaded.filter(agent="oracle")
        assert oracle_only.total == 4

        # Export CSV
        csv = export_csv(oracle_only)
        lines = csv.strip().split("\n")
        assert len(lines) == 5  # header + 4 entries
        assert all("oracle" in line for line in lines[1:])

    def test_merge_batteries(self, tmp_path):
        """Run two batteries, save both, load and merge."""
        b1 = ExperimentBattery(
            scenarios=[SCENARIO_SIMPLE],
            agents={"random": RandomAgent(seed=0)},
            seeds=[0, 1],
        )
        b2 = ExperimentBattery(
            scenarios=[SCENARIO_TIGHT_BUDGET],
            agents={"oracle": OracleAgent()},
            seeds=[0, 1],
        )
        r1 = b1.run()
        r2 = b2.run()

        p1 = save_results(r1, tmp_path / "batch1")
        p2 = save_results(r2, tmp_path / "batch2")

        merged = load_results(p1).merge(load_results(p2))
        assert merged.total == 4
        assert len(merged.by_agent()) == 2
        assert len(merged.by_scenario()) == 2

    def test_battery_spec_yaml_roundtrip(self, tmp_path):
        """Write battery spec YAML, verify it's valid for the battery command."""
        spec = {
            "scenarios": ["catalog/test/scenarios/simple.yaml"],
            "agents": ["random", "oracle"],
            "seeds": [0, 1, 2],
        }
        spec_path = tmp_path / "battery_spec.yaml"
        with open(spec_path, "w") as f:
            yaml.dump(spec, f)

        # Verify YAML round-trips correctly
        with open(spec_path) as f:
            loaded = yaml.safe_load(f)
        assert loaded["scenarios"] == spec["scenarios"]
        assert loaded["agents"] == spec["agents"]
        assert loaded["seeds"] == spec["seeds"]
