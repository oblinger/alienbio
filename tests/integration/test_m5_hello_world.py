"""Integration tests for M5.1 Hello World scenarios.

Tests that the H1-H5 YAML scenarios in catalog/test/scenarios/ are
well-formed and can execute with non-LLM agents as smoke tests.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from alienbio.agent import (
    ExperimentBattery,
    RandomAgent,
    OracleAgent,
    run_experiment,
)


SCENARIOS_DIR = Path(__file__).resolve().parents[2] / "catalog" / "test" / "scenarios"

H_SCENARIO_FILES = [
    "h1_representation.yaml",
    "h2_dynamics.yaml",
    "h3_control.yaml",
    "h4_goal.yaml",
    "h5_hypothesis.yaml",
]


def _load(filename: str) -> dict:
    """Load a scenario YAML file."""
    with open(SCENARIOS_DIR / filename) as f:
        return yaml.safe_load(f)


def _load_all() -> list[dict]:
    """Load all H scenarios."""
    return [_load(f) for f in H_SCENARIO_FILES]


class TestScenarioDefinitions:
    """Verify each H scenario YAML is well-formed."""

    @pytest.mark.parametrize("filename", H_SCENARIO_FILES,
                             ids=["h1", "h2", "h3", "h4", "h5"])
    def test_scenario_has_required_fields(self, filename):
        scenario = _load(filename)
        assert "name" in scenario
        assert "briefing" in scenario
        assert "constitution" in scenario
        assert "interface" in scenario
        assert "sim" in scenario
        assert "containers" in scenario
        assert "scoring" in scenario
        assert "passing_score" in scenario

    @pytest.mark.parametrize("filename", H_SCENARIO_FILES,
                             ids=["h1", "h2", "h3", "h4", "h5"])
    def test_interface_has_actions_and_budget(self, filename):
        scenario = _load(filename)
        iface = scenario["interface"]
        assert "actions" in iface
        assert "budget" in iface
        assert iface["budget"] > 0

    @pytest.mark.parametrize("filename", H_SCENARIO_FILES,
                             ids=["h1", "h2", "h3", "h4", "h5"])
    def test_scenario_has_ground_truth(self, filename):
        scenario = _load(filename)
        assert "_ground_truth_" in scenario

    @pytest.mark.parametrize("filename", H_SCENARIO_FILES,
                             ids=["h1", "h2", "h3", "h4", "h5"])
    def test_scenario_has_unique_name(self, filename):
        scenario = _load(filename)
        assert isinstance(scenario["name"], str)
        assert len(scenario["name"]) > 0

    def test_all_names_unique(self):
        scenarios = _load_all()
        names = [s["name"] for s in scenarios]
        assert len(names) == len(set(names))


class TestSmokeTestWithRandomAgent:
    """Run each scenario with RandomAgent to verify they execute without error."""

    @pytest.mark.parametrize("filename", H_SCENARIO_FILES,
                             ids=["h1", "h2", "h3", "h4", "h5"])
    def test_random_agent_completes(self, filename):
        scenario = _load(filename)
        result = run_experiment(scenario, RandomAgent(seed=42), seed=42)
        assert result.status == "completed"
        assert isinstance(result.scores, dict)

    @pytest.mark.parametrize("filename", H_SCENARIO_FILES,
                             ids=["h1", "h2", "h3", "h4", "h5"])
    def test_oracle_agent_completes(self, filename):
        scenario = _load(filename)
        result = run_experiment(scenario, OracleAgent(), seed=42)
        assert result.status == "completed"


class TestBatteryWithHelloWorld:
    """Run all H scenarios as a battery."""

    def test_all_scenarios_in_battery(self):
        """Battery runs all 5 scenarios x 2 agents x 3 seeds."""
        battery = ExperimentBattery(
            scenarios=_load_all(),
            agents={"random": RandomAgent(seed=0), "oracle": OracleAgent()},
            seeds=[0, 1, 2],
        )
        result = battery.run()
        assert result.total == 30

        by_scenario = result.by_scenario()
        assert len(by_scenario) == 5
        for entries in by_scenario.values():
            assert len(entries) == 6

    def test_all_complete(self):
        battery = ExperimentBattery(
            scenarios=_load_all(),
            agents={"random": RandomAgent(seed=0)},
            seeds=[0],
        )
        result = battery.run()
        for entry in result.entries:
            assert entry.result.status == "completed"


class TestH1GroundTruth:

    def test_has_questions(self):
        gt = _load("h1_representation.yaml")["_ground_truth_"]
        assert "questions" in gt
        assert len(gt["questions"]) == 5

    def test_questions_have_id_and_answer(self):
        for q in _load("h1_representation.yaml")["_ground_truth_"]["questions"]:
            assert "id" in q
            assert "question" in q
            assert "answer" in q


class TestH2GroundTruth:

    def test_has_expected_directions(self):
        dirs = _load("h2_dynamics.yaml")["_ground_truth_"]["expected_directions"]
        assert dirs["A"] == "decrease"
        assert dirs["B"] == "increase"


class TestH3GroundTruth:

    def test_has_expected_sequence(self):
        gt = _load("h3_control.yaml")["_ground_truth_"]
        assert "expected_sequence" in gt
        assert len(gt["expected_sequence"]) == 4


class TestH4GroundTruth:

    def test_has_target(self):
        gt = _load("h4_goal.yaml")["_ground_truth_"]
        assert gt["target_molecule"] == "X"
        assert gt["target_concentration"] == 15.0
        assert gt["initial_concentration"] == 10.0


class TestH5GroundTruth:

    def test_has_hidden_reaction(self):
        rxn = _load("h5_hypothesis.yaml")["_ground_truth_"]["hidden_reaction"]
        assert rxn["reactants"] == ["P", "Q"]
        assert rxn["products"] == ["R"]
        assert rxn["rate"] == 0.3
