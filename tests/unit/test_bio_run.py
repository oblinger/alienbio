"""Tests for Bio.run() - M3.1 Scenario Execution.

These tests verify that Bio.run() correctly:
- Executes simulation with scenario config
- Initializes simulator state from scenario.containers
- Applies scenario.sim settings (steps, time_step)
- Executes simulation loop for N steps
- Returns trace object with timeline of states
"""

import pytest
from alienbio.spec_lang import Bio, bio, SimulationResult
from alienbio.protocols import Scenario, Region, Organism
from alienbio.bio.chemistry import ChemistryImpl
from alienbio.bio.state import StateImpl


class TestBioRunBasic:
    """Basic Bio.run() functionality tests."""

    def test_run_returns_simulation_result(self):
        """Bio.run() returns a SimulationResult object."""
        # Simple hardcoded scenario with ground truth
        scenario = {
            "molecules": {"A": {}, "B": {}},
            "reactions": {},
            "_ground_truth_": {
                "molecules": {"A": {}, "B": {}},
                "reactions": {},
            },
            "regions": [],
            "_metadata_": {"name": "test_scenario"},
            "_seed": 42,
        }

        result = bio.run(scenario, steps=10)

        assert isinstance(result, SimulationResult)
        assert result.steps == 10
        assert result.scenario_name == "test_scenario"

    def test_run_with_steps_override(self):
        """Bio.run() respects steps parameter override."""
        scenario = {
            "_ground_truth_": {
                "molecules": {"X": {}},
                "reactions": {},
            },
            "_metadata_": {"sim": {"steps": 50}},
        }

        # Default from scenario
        result1 = bio.run(scenario)
        assert result1.steps == 50

        # Override
        result2 = bio.run(scenario, steps=20)
        assert result2.steps == 20

    def test_run_with_dt_override(self):
        """Bio.run() respects dt parameter override."""
        scenario = {
            "_ground_truth_": {
                "molecules": {"X": {}},
                "reactions": {},
            },
            "_metadata_": {"sim": {"dt": 0.5}},
        }

        # Default from scenario
        result1 = bio.run(scenario)
        assert result1.dt == 0.5

        # Override
        result2 = bio.run(scenario, dt=0.1)
        assert result2.dt == 0.1

    def test_run_default_steps_and_dt(self):
        """Bio.run() uses sensible defaults when not specified."""
        scenario = {
            "_ground_truth_": {
                "molecules": {"X": {}},
                "reactions": {},
            },
        }

        result = bio.run(scenario)

        assert result.steps == 100  # Default
        assert result.dt == 1.0  # Default


class TestBioRunTimeline:
    """Tests for timeline generation."""

    def test_timeline_has_correct_length(self):
        """Timeline has steps + 1 states (initial + N steps)."""
        scenario = {
            "_ground_truth_": {
                "molecules": {"A": {}, "B": {}},
                "reactions": {},
            },
        }

        result = bio.run(scenario, steps=10)

        # Timeline should have initial state + 10 steps = 11 states
        assert len(result.timeline) == 11
        assert len(result) == 11  # __len__ method

    def test_final_state_is_last_timeline_state(self):
        """final_state is the last state in timeline."""
        scenario = {
            "_ground_truth_": {
                "molecules": {"X": {}},
                "reactions": {},
            },
        }

        result = bio.run(scenario, steps=5)

        assert result.final_state is result.timeline[-1]

    def test_timeline_states_are_state_impl(self):
        """Timeline states are StateImpl objects."""
        scenario = {
            "_ground_truth_": {
                "molecules": {"A": {}, "B": {}},
                "reactions": {},
            },
        }

        result = bio.run(scenario, steps=5)

        for state in result.timeline:
            assert isinstance(state, StateImpl)


class TestBioRunWithReactions:
    """Tests with actual reactions to verify simulation execution."""

    def test_run_with_simple_reaction(self):
        """Simulation correctly executes a simple A -> B reaction."""
        scenario = {
            "_ground_truth_": {
                "molecules": {
                    "A": {},
                    "B": {},
                },
                "reactions": {
                    "r1": {
                        "reactants": ["A"],
                        "products": ["B"],
                        "rate": 0.1,
                    },
                },
            },
            "regions": [
                Region(
                    id="r0",
                    substrates={"A": 10.0},
                    organisms=[],
                ),
            ],
        }

        result = bio.run(scenario, steps=100, dt=1.0)

        # A should decrease, B should increase
        initial_state = result.timeline[0]
        final_state = result.final_state

        assert final_state["A"] < initial_state["A"]
        assert final_state["B"] > initial_state["B"]

    def test_run_produces_expected_trajectory(self):
        """Hardcoded scenario produces expected trajectory pattern."""
        # A + B -> C with known initial concentrations
        scenario = {
            "_ground_truth_": {
                "molecules": {
                    "A": {},
                    "B": {},
                    "C": {},
                },
                "reactions": {
                    "synthesis": {
                        "reactants": ["A", "B"],
                        "products": ["C"],
                        "rate": 0.01,  # Slow rate for predictable behavior
                    },
                },
            },
            "regions": [
                Region(
                    id="r0",
                    substrates={"A": 10.0, "B": 10.0, "C": 0.0},
                    organisms=[],
                ),
            ],
        }

        result = bio.run(scenario, steps=50, dt=1.0)

        # Verify trajectory pattern:
        # - A and B should monotonically decrease
        # - C should monotonically increase
        for i in range(len(result.timeline) - 1):
            state = result.timeline[i]
            next_state = result.timeline[i + 1]

            # A and B decrease (or stay same if depleted)
            assert next_state["A"] <= state["A"]
            assert next_state["B"] <= state["B"]
            # C increases (or stays same)
            assert next_state["C"] >= state["C"]

        # Final C should be positive
        assert result.final_state["C"] > 0


class TestBioRunWithScenarioDataclass:
    """Tests using Scenario dataclass (from build pipeline)."""

    def test_run_with_scenario_object(self):
        """Bio.run() works with Scenario dataclass."""
        scenario = Scenario(
            molecules={"A": {}, "B": {}},
            reactions={"r1": {"reactants": ["A"], "products": ["B"], "rate": 0.1}},
            regions=[Region(id="r0", substrates={"A": 5.0}, organisms=[])],
            _ground_truth_={
                "molecules": {"A": {}, "B": {}},
                "reactions": {"r1": {"reactants": ["A"], "products": ["B"], "rate": 0.1}},
            },
            _visibility_mapping_={},
            _seed=42,
            _metadata_={"name": "test", "sim": {"steps": 20}},
        )

        result = bio.run(scenario)

        assert isinstance(result, SimulationResult)
        assert result.steps == 20
        assert result.seed == 42

    def test_run_preserves_scenario_seed(self):
        """Bio.run() uses seed from Scenario."""
        scenario = Scenario(
            molecules={},
            reactions={},
            regions=[],
            _ground_truth_={"molecules": {"X": {}}, "reactions": {}},
            _visibility_mapping_={},
            _seed=12345,
            _metadata_={},
        )

        result = bio.run(scenario)

        assert result.seed == 12345


class TestSimulationResultInterface:
    """Tests for SimulationResult convenience methods."""

    def test_final_property_returns_dict(self):
        """SimulationResult.final returns concentrations as dict."""
        scenario = {
            "_ground_truth_": {
                "molecules": {"A": {}, "B": {}},
                "reactions": {},
            },
        }

        result = bio.run(scenario, steps=5)

        final = result.final
        assert isinstance(final, dict)
        assert "A" in final
        assert "B" in final

    def test_empty_result_final_returns_empty_dict(self):
        """SimulationResult.final returns {} when no states."""
        result = SimulationResult()

        assert result.final == {}

    def test_len_returns_timeline_length(self):
        """len(result) returns number of states in timeline."""
        result = SimulationResult(timeline=[1, 2, 3, 4, 5])

        assert len(result) == 5


class TestBioRunReproducibility:
    """Tests for simulation reproducibility."""

    def test_same_seed_same_result(self):
        """Same seed produces identical results."""
        scenario = {
            "_ground_truth_": {
                "molecules": {"A": {}, "B": {}},
                "reactions": {"r1": {"reactants": ["A"], "products": ["B"], "rate": 0.1}},
            },
            "regions": [Region(id="r0", substrates={"A": 10.0}, organisms=[])],
        }

        result1 = bio.run(scenario, seed=42, steps=50)
        result2 = bio.run(scenario, seed=42, steps=50)

        # Final states should be identical
        for mol in result1.final:
            assert result1.final[mol] == result2.final[mol]

    def test_different_seeds_different_if_stochastic(self):
        """Different seeds would produce different results for stochastic sims.

        Note: The reference simulator is deterministic, so this test verifies
        the seed is recorded correctly for future stochastic simulators.
        """
        scenario = {
            "_ground_truth_": {
                "molecules": {"X": {}},
                "reactions": {},
            },
        }

        result1 = bio.run(scenario, seed=1)
        result2 = bio.run(scenario, seed=2)

        # Seeds should be recorded
        assert result1.seed != result2.seed
