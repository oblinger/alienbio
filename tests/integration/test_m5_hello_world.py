"""Integration tests for M5.1 Hello World scenarios.

Tests that the H1-H5 scenarios defined in catalog/test/scenarios/hello_world.py
are well-formed and can execute with non-LLM agents as smoke tests.
"""

from __future__ import annotations

import pytest

from alienbio.agent import (
    ExperimentBattery,
    RandomAgent,
    OracleAgent,
    run_experiment,
)
from catalog.test.scenarios.hello_world import (
    h1_representation_comprehension,
    h2_dynamics_prediction,
    h3_control_interface,
    h4_goal_directed,
    h5_hypothesis_formation,
    ALL_HELLO_WORLD,
)


class TestScenarioDefinitions:
    """Verify each H scenario is well-formed."""

    @pytest.mark.parametrize("factory", ALL_HELLO_WORLD,
                             ids=["h1", "h2", "h3", "h4", "h5"])
    def test_scenario_has_required_fields(self, factory):
        """Each scenario has all required top-level fields."""
        scenario = factory()
        assert "name" in scenario
        assert "briefing" in scenario
        assert "constitution" in scenario
        assert "interface" in scenario
        assert "sim" in scenario
        assert "containers" in scenario
        assert "scoring" in scenario
        assert "passing_score" in scenario

    @pytest.mark.parametrize("factory", ALL_HELLO_WORLD,
                             ids=["h1", "h2", "h3", "h4", "h5"])
    def test_interface_has_actions_and_budget(self, factory):
        """Each scenario interface has actions and budget."""
        scenario = factory()
        iface = scenario["interface"]
        assert "actions" in iface
        assert "budget" in iface
        assert iface["budget"] > 0

    @pytest.mark.parametrize("factory", ALL_HELLO_WORLD,
                             ids=["h1", "h2", "h3", "h4", "h5"])
    def test_scenario_has_ground_truth(self, factory):
        """Each scenario has ground truth for validation."""
        scenario = factory()
        assert "_ground_truth_" in scenario

    @pytest.mark.parametrize("factory", ALL_HELLO_WORLD,
                             ids=["h1", "h2", "h3", "h4", "h5"])
    def test_scenario_has_unique_name(self, factory):
        """Each scenario has a unique name."""
        scenario = factory()
        assert isinstance(scenario["name"], str)
        assert len(scenario["name"]) > 0

    def test_all_names_unique(self):
        """No two scenarios share the same name."""
        names = [f()["name"] for f in ALL_HELLO_WORLD]
        assert len(names) == len(set(names))


class TestSmokeTestWithRandomAgent:
    """Run each scenario with RandomAgent to verify they execute without error."""

    @pytest.mark.parametrize("factory", ALL_HELLO_WORLD,
                             ids=["h1", "h2", "h3", "h4", "h5"])
    def test_random_agent_completes(self, factory):
        """RandomAgent can run the scenario to completion."""
        scenario = factory()
        agent = RandomAgent(seed=42)
        result = run_experiment(scenario, agent, seed=42)
        assert result.status == "completed"
        assert isinstance(result.scores, dict)

    @pytest.mark.parametrize("factory", ALL_HELLO_WORLD,
                             ids=["h1", "h2", "h3", "h4", "h5"])
    def test_oracle_agent_completes(self, factory):
        """OracleAgent can run the scenario to completion."""
        scenario = factory()
        agent = OracleAgent()
        result = run_experiment(scenario, agent, seed=42)
        assert result.status == "completed"


class TestBatteryWithHelloWorld:
    """Run all H scenarios as a battery."""

    def test_all_scenarios_in_battery(self):
        """Battery runs all 5 scenarios x 2 agents x 3 seeds."""
        scenarios = [f() for f in ALL_HELLO_WORLD]
        battery = ExperimentBattery(
            scenarios=scenarios,
            agents={"random": RandomAgent(seed=0), "oracle": OracleAgent()},
            seeds=[0, 1, 2],
        )
        result = battery.run()
        assert result.total == 30  # 5 x 2 x 3

        by_scenario = result.by_scenario()
        assert len(by_scenario) == 5
        for entries in by_scenario.values():
            assert len(entries) == 6  # 2 agents x 3 seeds

    def test_all_complete(self):
        """Every experiment in the battery completes."""
        scenarios = [f() for f in ALL_HELLO_WORLD]
        battery = ExperimentBattery(
            scenarios=scenarios,
            agents={"random": RandomAgent(seed=0)},
            seeds=[0],
        )
        result = battery.run()
        for entry in result.entries:
            assert entry.result.status == "completed"


class TestH1GroundTruth:
    """Validate H1 ground truth structure."""

    def test_has_questions(self):
        scenario = h1_representation_comprehension()
        gt = scenario["_ground_truth_"]
        assert "questions" in gt
        assert len(gt["questions"]) == 5

    def test_questions_have_id_and_answer(self):
        scenario = h1_representation_comprehension()
        for q in scenario["_ground_truth_"]["questions"]:
            assert "id" in q
            assert "question" in q
            assert "answer" in q


class TestH2GroundTruth:
    """Validate H2 ground truth structure."""

    def test_has_expected_directions(self):
        scenario = h2_dynamics_prediction()
        gt = scenario["_ground_truth_"]
        assert "expected_directions" in gt
        dirs = gt["expected_directions"]
        assert dirs["A"] == "decrease"
        assert dirs["B"] == "increase"


class TestH3GroundTruth:
    """Validate H3 ground truth structure."""

    def test_has_expected_sequence(self):
        scenario = h3_control_interface()
        gt = scenario["_ground_truth_"]
        assert "expected_sequence" in gt
        assert len(gt["expected_sequence"]) == 4


class TestH4GroundTruth:
    """Validate H4 ground truth structure."""

    def test_has_target(self):
        scenario = h4_goal_directed()
        gt = scenario["_ground_truth_"]
        assert gt["target_molecule"] == "X"
        assert gt["target_concentration"] == 15.0
        assert gt["initial_concentration"] == 10.0


class TestH5GroundTruth:
    """Validate H5 ground truth structure."""

    def test_has_hidden_reaction(self):
        scenario = h5_hypothesis_formation()
        gt = scenario["_ground_truth_"]
        rxn = gt["hidden_reaction"]
        assert rxn["reactants"] == ["P", "Q"]
        assert rxn["products"] == ["R"]
        assert rxn["rate"] == 0.3
