"""Tests for ExperimentBattery.

M4.1 - Experiment Battery: scenarios × agents × seeds
"""

from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock, call

from alienbio.agent import (
    ExperimentBattery,
    BatteryResult,
    BatteryEntry,
    BatteryProgress,
    ExperimentResults,
    RandomAgent,
    OracleAgent,
)


# Minimal scenarios for testing
SCENARIO_A = {
    "name": "scenario_a",
    "briefing": "Scenario A",
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

SCENARIO_B = {
    "name": "scenario_b",
    "briefing": "Scenario B",
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

SCENARIO_C = {
    "name": "scenario_c",
    "briefing": "Scenario C",
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


def _make_result(scenario_name: str, seed: int, passed: bool = True) -> ExperimentResults:
    """Create a mock ExperimentResults."""
    trace = MagicMock()
    trace.total_cost = 1.0
    return ExperimentResults(
        scenario=scenario_name,
        seed=seed,
        scores={"budget_compliance": 1.0 if passed else 0.0},
        trace=trace,
        passed=passed,
    )


class TestBatteryResult:
    """Tests for BatteryResult aggregation."""

    def test_empty_result(self):
        result = BatteryResult()
        assert result.total == 0
        assert result.passed == 0
        assert result.failed == 0
        assert result.pass_rate == 0.0

    def test_total_and_passed(self):
        result = BatteryResult(entries=[
            BatteryEntry("agent_a", _make_result("s1", 0, passed=True)),
            BatteryEntry("agent_a", _make_result("s1", 1, passed=False)),
            BatteryEntry("agent_b", _make_result("s1", 0, passed=True)),
        ])
        assert result.total == 3
        assert result.passed == 2
        assert result.failed == 1
        assert result.pass_rate == pytest.approx(2 / 3)

    def test_by_scenario(self):
        result = BatteryResult(entries=[
            BatteryEntry("a", _make_result("s1", 0)),
            BatteryEntry("a", _make_result("s2", 0)),
            BatteryEntry("b", _make_result("s1", 0)),
        ])
        groups = result.by_scenario()
        assert set(groups.keys()) == {"s1", "s2"}
        assert len(groups["s1"]) == 2
        assert len(groups["s2"]) == 1

    def test_by_agent(self):
        result = BatteryResult(entries=[
            BatteryEntry("agent_a", _make_result("s1", 0)),
            BatteryEntry("agent_a", _make_result("s2", 0)),
            BatteryEntry("agent_b", _make_result("s1", 0)),
        ])
        groups = result.by_agent()
        assert set(groups.keys()) == {"agent_a", "agent_b"}
        assert len(groups["agent_a"]) == 2
        assert len(groups["agent_b"]) == 1

    def test_summary(self):
        result = BatteryResult(entries=[
            BatteryEntry("a", _make_result("s1", 0, passed=True)),
            BatteryEntry("a", _make_result("s1", 1, passed=False)),
            BatteryEntry("b", _make_result("s1", 0, passed=True)),
        ])
        summary = result.summary()
        assert len(summary) == 2
        a_row = next(r for r in summary if r["agent"] == "a")
        assert a_row["total"] == 2
        assert a_row["passed"] == 1
        assert a_row["pass_rate"] == pytest.approx(0.5)
        assert "budget_compliance" in a_row["mean_scores"]

    def test_summary_mean_scores(self):
        """Summary computes correct mean across entries."""
        trace = MagicMock()
        trace.total_cost = 0.0
        result = BatteryResult(entries=[
            BatteryEntry("a", ExperimentResults(
                scenario="s1", seed=0, scores={"score": 0.2},
                trace=trace, passed=False,
            )),
            BatteryEntry("a", ExperimentResults(
                scenario="s1", seed=1, scores={"score": 0.8},
                trace=trace, passed=True,
            )),
        ])
        summary = result.summary()
        a_row = summary[0]
        assert a_row["mean_scores"]["score"] == pytest.approx(0.5)


class TestExperimentBattery:
    """Tests for ExperimentBattery execution."""

    def test_total_runs(self):
        battery = ExperimentBattery(
            scenarios=[SCENARIO_A, SCENARIO_B, SCENARIO_C],
            agents={"random": RandomAgent(seed=0), "oracle": OracleAgent()},
            seeds=[0, 1, 2, 3, 4],
        )
        assert battery.total_runs == 30  # 3 × 2 × 5

    def test_run_all_combinations(self):
        """Battery runs every scenario × agent × seed combination."""
        battery = ExperimentBattery(
            scenarios=[SCENARIO_A, SCENARIO_B],
            agents={"random": RandomAgent(seed=0)},
            seeds=[0, 1],
        )
        result = battery.run()
        assert result.total == 4  # 2 scenarios × 1 agent × 2 seeds
        # All should complete
        for entry in result.entries:
            assert entry.result.status == "completed"
            assert entry.agent_name == "random"

    def test_run_preserves_scenario_names(self):
        """Results track which scenario each experiment ran."""
        battery = ExperimentBattery(
            scenarios=[SCENARIO_A, SCENARIO_B],
            agents={"random": RandomAgent(seed=0)},
            seeds=[0],
        )
        result = battery.run()
        scenarios = {e.result.scenario for e in result.entries}
        assert scenarios == {"scenario_a", "scenario_b"}

    def test_run_preserves_seeds(self):
        """Results track which seed each experiment used."""
        battery = ExperimentBattery(
            scenarios=[SCENARIO_A],
            agents={"random": RandomAgent(seed=0)},
            seeds=[10, 20, 30],
        )
        result = battery.run()
        seeds = {e.result.seed for e in result.entries}
        assert seeds == {10, 20, 30}

    def test_run_preserves_agent_names(self):
        """Results track which agent ran each experiment."""
        battery = ExperimentBattery(
            scenarios=[SCENARIO_A],
            agents={"random": RandomAgent(seed=0), "oracle": OracleAgent()},
            seeds=[0],
        )
        result = battery.run()
        agents = {e.agent_name for e in result.entries}
        assert agents == {"random", "oracle"}

    def test_progress_callback(self):
        """on_progress is called after each experiment."""
        progress_reports: list[BatteryProgress] = []

        battery = ExperimentBattery(
            scenarios=[SCENARIO_A],
            agents={"random": RandomAgent(seed=0)},
            seeds=[0, 1],
            on_progress=progress_reports.append,
        )
        battery.run()

        assert len(progress_reports) == 2
        assert progress_reports[0].completed == 1
        assert progress_reports[0].total == 2
        assert progress_reports[0].scenario == "scenario_a"
        assert progress_reports[0].agent == "random"
        assert progress_reports[0].seed == 0
        assert progress_reports[1].completed == 2
        assert progress_reports[1].seed == 1

    def test_3x2x5_battery(self):
        """Roadmap test: 3 scenarios × 2 agents × 5 seeds = 30 experiments."""
        battery = ExperimentBattery(
            scenarios=[SCENARIO_A, SCENARIO_B, SCENARIO_C],
            agents={"random": RandomAgent(seed=0), "oracle": OracleAgent()},
            seeds=[0, 1, 2, 3, 4],
        )
        result = battery.run()

        assert result.total == 30
        # All experiments should complete
        for entry in result.entries:
            assert entry.result.status == "completed"
        # Verify grouping
        by_scenario = result.by_scenario()
        assert len(by_scenario) == 3
        for entries in by_scenario.values():
            assert len(entries) == 10  # 2 agents × 5 seeds
        by_agent = result.by_agent()
        assert len(by_agent) == 2
        for entries in by_agent.values():
            assert len(entries) == 15  # 3 scenarios × 5 seeds

    def test_empty_battery(self):
        """Battery with no scenarios runs zero experiments."""
        battery = ExperimentBattery(
            scenarios=[],
            agents={"random": RandomAgent(seed=0)},
            seeds=[0],
        )
        result = battery.run()
        assert result.total == 0

    def test_single_experiment(self):
        """Battery with 1×1×1 runs exactly one experiment."""
        battery = ExperimentBattery(
            scenarios=[SCENARIO_A],
            agents={"oracle": OracleAgent()},
            seeds=[42],
        )
        result = battery.run()
        assert result.total == 1
        assert result.entries[0].agent_name == "oracle"
        assert result.entries[0].result.seed == 42
        assert result.entries[0].result.scenario == "scenario_a"

    def test_deterministic_with_seeds(self):
        """Same battery config produces same results."""
        def run_battery():
            battery = ExperimentBattery(
                scenarios=[SCENARIO_A],
                agents={"random": RandomAgent(seed=0)},
                seeds=[42],
            )
            return battery.run()

        r1 = run_battery()
        r2 = run_battery()
        assert r1.entries[0].result.scores == r2.entries[0].result.scores

    def test_result_aggregation_after_run(self):
        """Summary is available after battery.run()."""
        battery = ExperimentBattery(
            scenarios=[SCENARIO_A, SCENARIO_B],
            agents={"random": RandomAgent(seed=0), "oracle": OracleAgent()},
            seeds=[0, 1],
        )
        result = battery.run()
        summary = result.summary()

        assert len(summary) == 2
        for row in summary:
            assert row["total"] == 4  # 2 scenarios × 2 seeds
            assert "pass_rate" in row
            assert "mean_scores" in row
