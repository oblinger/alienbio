"""Integration tests for H1-H5 Hello World experiments.

These tests verify that the agent interface works correctly with the
H1-H5 experiment scenarios. They test the complete flow from scenario
loading through agent execution to results.

Unlike test_agent_interface.py which tests individual components,
these tests run complete experiments with the fixtures.
"""

import pytest
from alienbio.agent import (
    AgentSession,
    Action,
    Observation,
    ActionResult,
    run_experiment,
    ScriptedAgent,
    RandomAgent,
)
from tests.fixtures import (
    H1_MINIMAL,
    H1_SMALL,
    H2_SINGLE_REACTION,
    H2_MULTI_REACTION,
    H3_SIMPLE_SEQUENCE,
    H4_DIRECT_INTERVENTION,
    H4_INDIRECT_INTERVENTION,
    H5_HIDDEN_REACTION,
    SIMPLE_SCENARIO,
)


class TestH1RepresentationComprehension:
    """Tests for H1: Representation Comprehension scenarios."""

    def test_h1_minimal_session_creation(self):
        """Can create session from H1 minimal scenario."""
        session = AgentSession(H1_MINIMAL, seed=42)
        assert session is not None
        assert session.scenario["name"] == "h1_minimal"

    def test_h1_minimal_observe_briefing(self):
        """H1 observation includes proper briefing."""
        session = AgentSession(H1_MINIMAL, seed=42)
        obs = session.observe()
        assert "alien biological system" in obs.briefing.lower()

    def test_h1_minimal_has_structural_queries(self):
        """H1 provides structural query measurements."""
        session = AgentSession(H1_MINIMAL, seed=42)
        obs = session.observe()
        assert "list_compartments" in obs.available_measurements
        assert "list_molecules" in obs.available_measurements
        assert "describe_reaction" in obs.available_measurements

    def test_h1_minimal_no_actions(self):
        """H1 scenarios have no actions (observation only)."""
        session = AgentSession(H1_MINIMAL, seed=42)
        obs = session.observe()
        assert len(obs.available_actions) == 0

    def test_h1_minimal_has_ground_truth(self):
        """H1 scenario includes ground truth for evaluation."""
        assert "_ground_truth_" in H1_MINIMAL
        truth = H1_MINIMAL["_ground_truth_"]
        assert truth["compartment_count"] == 2
        assert truth["molecule_count"] == 3
        assert truth["reaction_count"] == 1

    def test_h1_small_more_complex(self):
        """H1 small scenario has more components."""
        assert H1_SMALL["_ground_truth_"]["compartment_count"] == 3
        assert H1_SMALL["_ground_truth_"]["molecule_count"] == 5
        assert H1_SMALL["_ground_truth_"]["reaction_count"] == 3


class TestH2DynamicsPrediction:
    """Tests for H2: Single-Step Dynamics Prediction scenarios."""

    def test_h2_single_reaction_setup(self):
        """H2 single reaction scenario is properly configured."""
        session = AgentSession(H2_SINGLE_REACTION, seed=42)
        obs = session.observe()
        assert "step" in obs.available_actions
        assert "observe" in obs.available_measurements

    def test_h2_single_reaction_ground_truth(self):
        """H2 single reaction has correct ground truth."""
        truth = H2_SINGLE_REACTION["_ground_truth_"]
        assert truth["reaction_that_fired"] == "R1"
        assert truth["a_decreases"] == True
        assert truth["b_increases"] == True

    def test_h2_multi_reaction_has_dominant(self):
        """H2 multi-reaction identifies dominant reaction."""
        truth = H2_MULTI_REACTION["_ground_truth_"]
        assert truth["dominant_reaction"] == "R2"

    def test_h2_can_step_simulation(self):
        """Can execute step action in H2 scenario."""
        session = AgentSession(H2_SINGLE_REACTION, seed=42)
        action = Action(name="step", params={"n": 5})
        result = session.act(action)
        assert result.success == True


class TestH3ControlInterface:
    """Tests for H3: Control Interface Exercise scenarios."""

    def test_h3_simple_sequence_scripted(self):
        """H3 works with scripted agent following protocol."""
        script = [
            Action(name="observe", params={}),
            Action(name="step", params={"n": 10}),
            Action(name="observe", params={}),
            Action(name="done", params={})
        ]
        results = run_experiment(
            H3_SIMPLE_SEQUENCE,
            ScriptedAgent(actions=script),
            seed=42
        )
        assert results.status == "completed"
        assert len(results.trace) == 4

    def test_h3_expected_sequence_in_ground_truth(self):
        """H3 ground truth specifies expected sequence."""
        truth = H3_SIMPLE_SEQUENCE["_ground_truth_"]
        assert truth["expected_sequence"] == ["observe", "step", "observe", "report"]


class TestH4GoalDirected:
    """Tests for H4: Goal-Directed Single Intervention scenarios."""

    def test_h4_direct_has_goal(self):
        """H4 direct intervention has clear goal."""
        assert "goal" in H4_DIRECT_INTERVENTION
        goal = H4_DIRECT_INTERVENTION["goal"]
        assert goal["molecule"] == "X"
        assert goal["target"] == 15.0

    def test_h4_direct_has_intervention_actions(self):
        """H4 provides intervention actions."""
        session = AgentSession(H4_DIRECT_INTERVENTION, seed=42)
        obs = session.observe()
        assert "add_molecule" in obs.available_actions
        assert "remove_molecule" in obs.available_actions

    def test_h4_indirect_requires_reasoning(self):
        """H4 indirect requires understanding reaction pathways."""
        session = AgentSession(H4_INDIRECT_INTERVENTION, seed=42)
        obs = session.observe()
        # Has both direct and rate manipulation options
        assert "add_molecule" in obs.available_actions
        assert "adjust_rate" in obs.available_actions

    def test_h4_direct_scripted_intervention(self):
        """Can run H4 with scripted intervention."""
        script = [
            Action(name="observe", params={}),
            Action(name="add_molecule", params={"molecule": "X", "amount": 10.0}),
            Action(name="done", params={})
        ]
        results = run_experiment(
            H4_DIRECT_INTERVENTION,
            ScriptedAgent(actions=script),
            seed=42
        )
        assert results.status == "completed"


class TestH5HypothesisFormation:
    """Tests for H5: Hypothesis Formation scenarios."""

    def test_h5_has_hidden_reaction(self):
        """H5 scenario has hidden reactions."""
        assert "hidden_reactions" in H5_HIDDEN_REACTION
        assert "R?" in H5_HIDDEN_REACTION["hidden_reactions"]

    def test_h5_ground_truth_reveals_hidden(self):
        """H5 ground truth contains hidden reaction details."""
        truth = H5_HIDDEN_REACTION["_ground_truth_"]
        assert truth["hidden_reaction_reactants"] == ["Q", "R"]
        assert truth["hidden_reaction_products"] == ["S"]

    def test_h5_provides_experimental_tools(self):
        """H5 provides tools for designing experiments."""
        session = AgentSession(H5_HIDDEN_REACTION, seed=42)
        obs = session.observe()
        assert "set_concentration" in obs.available_actions
        assert "step" in obs.available_actions
        assert "submit_hypothesis" in obs.available_actions

    def test_h5_limited_budget(self):
        """H5 has limited budget for experiments."""
        session = AgentSession(H5_HIDDEN_REACTION, seed=42)
        obs = session.observe()
        assert obs.budget == 15


class TestEndToEndExperiments:
    """End-to-end tests running complete experiments."""

    def test_simple_scenario_with_random_agent(self):
        """Random agent completes simple scenario."""
        results = run_experiment(
            SIMPLE_SCENARIO,
            RandomAgent(seed=42),
            seed=42
        )
        assert results.status == "completed"
        assert results.scenario == "test_scenario"

    def test_h1_minimal_complete_flow(self):
        """Complete H1 flow with scripted measurements."""
        script = [
            Action(name="list_compartments", params={}),
            Action(name="list_molecules", params={"compartment": "Alpha"}),
            Action(name="describe_reaction", params={"reaction": "R1"}),
            Action(name="done", params={})
        ]
        results = run_experiment(
            H1_MINIMAL,
            ScriptedAgent(actions=script),
            seed=42
        )
        assert results.status == "completed"
        assert len(results.trace) == 4

    def test_action_result_is_observation(self):
        """ActionResult is a subclass of Observation."""
        session = AgentSession(SIMPLE_SCENARIO, seed=42)
        result = session.act(Action(name="add_feedstock", params={"molecule": "M1", "amount": 5.0}))

        # ActionResult should be an Observation
        assert isinstance(result, Observation)
        assert isinstance(result, ActionResult)

        # Should have both Observation and ActionResult fields
        assert hasattr(result, "briefing")  # Observation field
        assert hasattr(result, "success")   # ActionResult field
        assert hasattr(result, "action_name")  # ActionResult field

    def test_trace_records_observations(self):
        """Trace records action→observation pairs."""
        script = [
            Action(name="add_feedstock", params={"molecule": "M1", "amount": 5.0}),
            Action(name="done", params={})
        ]
        results = run_experiment(
            SIMPLE_SCENARIO,
            ScriptedAgent(actions=script),
            seed=42
        )

        # Check trace has records
        assert len(results.trace) == 2

        # Each record has action and observation
        record = results.trace[0]
        assert hasattr(record, "action")
        assert hasattr(record, "observation")
        assert isinstance(record.observation, Observation)
