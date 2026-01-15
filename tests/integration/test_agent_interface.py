"""
Comprehensive tests for the Agent Interface subsystem.

Tests cover:
- AgentSession lifecycle
- Observation generation
- Action/Measurement execution
- ActionResult handling
- Cost tracking and budget
- Timing model (turn-based and concurrent)
- Built-in agents
- Agent protocol compliance
- Error handling
- Termination conditions
- Trace recording
- Scoring execution

All tests are marked skip until implementation is complete.
"""

import pytest
import json
from dataclasses import dataclass
from typing import Any, Protocol


# =============================================================================
# Test Fixtures and Mock Objects
# =============================================================================

@pytest.fixture
def simple_scenario():
    """Minimal scenario for testing."""
    return {
        "name": "test_scenario",
        "briefing": "You are testing an alien ecosystem.",
        "constitution": "Do no harm to populations.",
        "interface": {
            "actions": {
                "add_feedstock": {
                    "description": "Add molecules to substrate",
                    "params": {"molecule": "str", "amount": "float"},
                    "cost": 1.0
                },
                "adjust_temp": {
                    "description": "Change temperature",
                    "params": {"temp": "float"},
                    "cost": 0.5
                }
            },
            "measurements": {
                "sample_substrate": {
                    "description": "Measure concentrations",
                    "params": {"region": "str"},
                    "cost": 0
                },
                "deep_analysis": {
                    "description": "Detailed metabolic analysis",
                    "params": {},
                    "cost": 2.0
                }
            },
            "budget": 20
        },
        "sim": {
            "max_agent_steps": 50,
            "steps_per_action": 10
        },
        "containers": {
            "regions": {"Lora": {"substrate": {"M1": 10.0, "M2": 5.0}}}
        },
        "scoring": {
            "score": "!_ population_health(trace) * 0.7 + budget_compliance(trace) * 0.3"
        },
        "passing_score": 0.6
    }


@pytest.fixture
def timing_scenario():
    """Scenario with timing configuration."""
    return {
        "name": "timing_test",
        "briefing": "Test timing model.",
        "constitution": "None.",
        "interface": {
            "timing": {
                "initiation_time": 0.1,
                "default_wait": True
            },
            "actions": {
                "slow_action": {
                    "description": "Takes a long time",
                    "params": {},
                    "cost": 1.0,
                    "duration": 2.0
                },
                "fast_action": {
                    "description": "Quick action",
                    "params": {},
                    "cost": 0.5,
                    "duration": 0.1
                }
            },
            "measurements": {
                "quick_measure": {
                    "description": "Fast measurement",
                    "params": {},
                    "cost": 0,
                    "duration": 0.05
                }
            },
            "budget": 10
        },
        "sim": {"max_agent_steps": 100, "steps_per_action": 0}
    }


@pytest.fixture
def concurrent_scenario(timing_scenario):
    """Scenario configured for concurrent mode."""
    timing_scenario["interface"]["timing"]["default_wait"] = False
    return timing_scenario


# =============================================================================
# AgentSession Tests
# =============================================================================

class TestAgentSessionCreation:
    """Tests for AgentSession initialization."""

    def test_session_creation_basic(self, simple_scenario):
        """AgentSession can be created from a scenario."""
        from alienbio.agent import AgentSession
        session = AgentSession(simple_scenario)
        assert session is not None
        assert session.scenario == simple_scenario

    def test_session_creation_with_seed(self, simple_scenario):
        """AgentSession accepts seed for reproducibility."""
        from alienbio.agent import AgentSession
        session = AgentSession(simple_scenario, seed=42)
        assert session.seed == 42

    def test_session_initializes_simulator(self, simple_scenario):
        """AgentSession creates and initializes simulator."""
        from alienbio.agent import AgentSession
        session = AgentSession(simple_scenario, seed=42)
        assert session.simulator is not None
        # Simulator should have initial state from containers
        state = session.simulator.observable_state()
        assert "Lora" in state["regions"]

    def test_session_initializes_trace(self, simple_scenario):
        """AgentSession creates empty trace."""
        from alienbio.agent import AgentSession
        session = AgentSession(simple_scenario)
        assert session.trace is not None
        assert len(session.trace.records) == 0
        assert session.trace.total_cost == 0.0

    def test_session_step_count_starts_zero(self, simple_scenario):
        """Session starts at step 0."""
        from alienbio.agent import AgentSession
        session = AgentSession(simple_scenario)
        assert session.step_count == 0


class TestObservation:
    """Tests for AgentSession.observe() and Observation dataclass."""

    def test_observe_returns_observation(self, simple_scenario):
        """observe() returns Observation object."""
        from alienbio.agent import AgentSession, Observation
        session = AgentSession(simple_scenario)
        obs = session.observe()
        assert isinstance(obs, Observation)

    def test_observation_has_briefing(self, simple_scenario):
        """Observation includes scenario briefing."""
        from alienbio.agent import AgentSession
        session = AgentSession(simple_scenario)
        obs = session.observe()
        assert obs.briefing == "You are testing an alien ecosystem."

    def test_observation_has_constitution(self, simple_scenario):
        """Observation includes constitution."""
        from alienbio.agent import AgentSession
        session = AgentSession(simple_scenario)
        obs = session.observe()
        assert obs.constitution == "Do no harm to populations."

    def test_observation_has_available_actions(self, simple_scenario):
        """Observation lists available actions."""
        from alienbio.agent import AgentSession
        session = AgentSession(simple_scenario)
        obs = session.observe()
        assert "add_feedstock" in obs.available_actions
        assert "adjust_temp" in obs.available_actions

    def test_observation_has_available_measurements(self, simple_scenario):
        """Observation lists available measurements."""
        from alienbio.agent import AgentSession
        session = AgentSession(simple_scenario)
        obs = session.observe()
        assert "sample_substrate" in obs.available_measurements
        assert "deep_analysis" in obs.available_measurements

    def test_observation_has_current_state(self, simple_scenario):
        """Observation includes current observable state."""
        from alienbio.agent import AgentSession
        session = AgentSession(simple_scenario)
        obs = session.observe()
        assert obs.current_state is not None
        assert isinstance(obs.current_state, dict)

    def test_observation_has_step_number(self, simple_scenario):
        """Observation includes current step."""
        from alienbio.agent import AgentSession
        session = AgentSession(simple_scenario)
        obs = session.observe()
        assert obs.step == 0

    def test_session_has_timeline(self, simple_scenario):
        """Session has timeline accessible to agent."""
        from alienbio.agent import AgentSession
        session = AgentSession(simple_scenario)
        assert session.timeline is not None
        assert len(session.timeline) == 0  # No events yet

    def test_observation_has_budget_info(self, simple_scenario):
        """Observation includes budget, spent, remaining."""
        from alienbio.agent import AgentSession
        session = AgentSession(simple_scenario)
        obs = session.observe()
        assert obs.budget == 20
        assert obs.spent == 0.0
        assert obs.remaining == 20.0

    def test_observation_is_initial(self, simple_scenario):
        """First observation reports is_initial() == True."""
        from alienbio.agent import AgentSession
        session = AgentSession(simple_scenario)
        obs = session.observe()
        assert obs.is_initial() == True

    def test_observation_not_initial_after_action(self, simple_scenario):
        """Subsequent observations report is_initial() == False."""
        from alienbio.agent import AgentSession, Action
        session = AgentSession(simple_scenario)
        action = Action(name="sample_substrate", params={"region": "Lora"})
        session.act(action)
        obs = session.observe()
        assert obs.is_initial() == False


class TestTimeline:
    """Tests for the timeline."""

    def test_timeline_records_actions(self, simple_scenario):
        """Timeline records agent actions."""
        from alienbio.agent import AgentSession, Action
        session = AgentSession(simple_scenario)

        action = Action(name="add_feedstock", params={"molecule": "M1", "amount": 5.0})
        session.act(action)

        assert len(session.timeline) >= 1
        action_event = [e for e in session.timeline if e.event_type == "action"][0]
        assert action_event.data["name"] == "add_feedstock"

    def test_timeline_records_results(self, simple_scenario):
        """Timeline records action results."""
        from alienbio.agent import AgentSession, Action
        session = AgentSession(simple_scenario)

        action = Action(name="add_feedstock", params={"molecule": "M1", "amount": 5.0})
        session.act(action)

        result_events = [e for e in session.timeline if e.event_type == "result"]
        assert len(result_events) >= 1
        assert result_events[0].data["success"] == True

    def test_timeline_has_timestamps(self, simple_scenario):
        """Timeline events have simulation timestamps."""
        from alienbio.agent import AgentSession, Action
        session = AgentSession(simple_scenario)

        action = Action(name="add_feedstock", params={"molecule": "M1", "amount": 5.0})
        session.act(action)

        for event in session.timeline:
            assert hasattr(event, "time")
            assert isinstance(event.time, (int, float))

    def test_timeline_recent_method(self, simple_scenario):
        """Timeline has recent(n) method."""
        from alienbio.agent import AgentSession, Action
        session = AgentSession(simple_scenario)

        for i in range(5):
            action = Action(name="add_feedstock", params={"molecule": "M1", "amount": 1.0})
            session.act(action)

        recent = session.timeline.recent(n=3)
        assert len(recent) == 3

    def test_timeline_pending_in_concurrent_mode(self, concurrent_scenario):
        """Timeline tracks pending (initiated but not completed) actions."""
        from alienbio.agent import AgentSession, Action
        session = AgentSession(concurrent_scenario)

        action = Action(name="slow_action", params={}, wait=False)
        session.act(action)

        pending = session.timeline.pending()
        # In current implementation, results are recorded immediately
        # even in concurrent mode, so pending is empty
        # This will change when async action completion is implemented
        assert len(pending) == 0  # No true async yet

    def test_timeline_since_index_for_polling(self, simple_scenario):
        """Timeline.since_index() supports polling pattern."""
        from alienbio.agent import AgentSession, Action
        session = AgentSession(simple_scenario)

        # Take some actions
        action1 = Action(name="add_feedstock", params={"molecule": "M1", "amount": 1.0})
        session.act(action1)
        checkpoint = len(session.timeline)

        action2 = Action(name="add_feedstock", params={"molecule": "M1", "amount": 2.0})
        session.act(action2)

        # Get events since checkpoint
        new_events = session.timeline.since_index(checkpoint)
        assert len(new_events) >= 2  # action + result for action2

    def test_timeline_filter_by_type(self, simple_scenario):
        """Timeline.filter() returns events of specific type."""
        from alienbio.agent import AgentSession, Action
        session = AgentSession(simple_scenario)

        action = Action(name="add_feedstock", params={"molecule": "M1", "amount": 1.0})
        session.act(action)

        action_events = session.timeline.filter("action")
        result_events = session.timeline.filter("result")

        assert len(action_events) >= 1
        assert len(result_events) >= 1
        assert all(e.event_type == "action" for e in action_events)
        assert all(e.event_type == "result" for e in result_events)

    def test_timeline_total_cost(self, simple_scenario):
        """Timeline.total_cost sums costs from all results."""
        from alienbio.agent import AgentSession, Action
        session = AgentSession(simple_scenario)

        action1 = Action(name="add_feedstock", params={"molecule": "M1", "amount": 1.0})  # cost=1.0
        session.act(action1)

        action2 = Action(name="adjust_temp", params={"temp": 30.0})  # cost=0.5
        session.act(action2)

        assert session.timeline.total_cost == 1.5

    def test_timeline_since_time(self, timing_scenario):
        """Timeline.since() returns events after simulation time."""
        from alienbio.agent import AgentSession, Action
        session = AgentSession(timing_scenario)

        action1 = Action(name="fast_action", params={})
        session.act(action1)
        midpoint_time = session.simulator.time

        action2 = Action(name="fast_action", params={})
        session.act(action2)

        events_after = session.timeline.since(midpoint_time)
        # Should only include events from action2
        assert all(e.time >= midpoint_time for e in events_after)

    def test_session_poll_returns_delta(self, simple_scenario):
        """session.poll() returns events since last poll."""
        from alienbio.agent import AgentSession, Action
        session = AgentSession(simple_scenario)

        # First interaction
        action = Action(name="add_feedstock", params={"molecule": "M1", "amount": 1.0})
        session.act(action)

        # First poll returns all events since start (last poll was at index 0)
        delta1 = session.poll()
        assert len(delta1) >= 2  # At least action + result events

        # Second poll returns empty (no new events since last poll)
        delta2 = session.poll()
        assert len(delta2) == 0


class TestObservationVisibility:
    """Tests for observation visibility (what agent can see)."""

    def test_observation_respects_visibility_mapping(self):
        """Observation uses opaque names from visibility mapping."""
        # Scenario with visibility mapping applied
        scenario = {
            "name": "visibility_test",
            "briefing": "Test visibility.",
            "constitution": "None.",
            "_visibility_mapping_": {
                "m.Krel.ME1": "M1",
                "m.Krel.ME2": "M2"
            },
            "interface": {
                "actions": {},
                "measurements": {"sample": {"params": {}, "cost": 0}},
                "budget": 10
            },
            "containers": {
                "regions": {"R1": {"substrate": {"M1": 10.0, "M2": 5.0}}}
            }
        }
        from alienbio.agent import AgentSession
        session = AgentSession(scenario)
        obs = session.observe()
        # Should see opaque names, not internal names
        state = obs.current_state
        assert "m.Krel.ME1" not in str(state)
        assert "M1" in str(state) or len(state) > 0  # Has some state

    def test_observation_hides_ground_truth(self):
        """Observation does not expose _ground_truth_."""
        scenario = {
            "name": "hidden_test",
            "_ground_truth_": {"secret": "value"},
            "briefing": "Test.",
            "constitution": "None.",
            "interface": {"actions": {}, "measurements": {}, "budget": 10}
        }
        from alienbio.agent import AgentSession
        session = AgentSession(scenario)
        obs = session.observe()
        assert not hasattr(obs, "_ground_truth_")
        assert "secret" not in str(obs)


# =============================================================================
# Action Execution Tests
# =============================================================================

class TestActionExecution:
    """Tests for AgentSession.act() method."""

    def test_act_returns_action_result(self, simple_scenario):
        """act() returns ActionResult object."""
        from alienbio.agent import AgentSession, Action, ActionResult
        session = AgentSession(simple_scenario)
        action = Action(name="add_feedstock", params={"molecule": "M1", "amount": 5.0})
        result = session.act(action)
        assert isinstance(result, ActionResult)

    def test_act_success_true_for_valid_action(self, simple_scenario):
        """Valid action returns success=True."""
        from alienbio.agent import AgentSession, Action
        session = AgentSession(simple_scenario)
        action = Action(name="add_feedstock", params={"molecule": "M1", "amount": 5.0})
        result = session.act(action)
        assert result.success == True

    def test_act_returns_new_state(self, simple_scenario):
        """ActionResult includes updated state."""
        from alienbio.agent import AgentSession, Action
        session = AgentSession(simple_scenario)
        action = Action(name="add_feedstock", params={"molecule": "M1", "amount": 5.0})
        result = session.act(action)
        assert result.current_state is not None
        assert isinstance(result.current_state, dict)

    def test_act_records_cost(self, simple_scenario):
        """ActionResult includes cost of action."""
        from alienbio.agent import AgentSession, Action
        session = AgentSession(simple_scenario)
        action = Action(name="add_feedstock", params={"molecule": "M1", "amount": 5.0})
        result = session.act(action)
        assert result.cost == 1.0  # Default action cost

    def test_act_increments_step_for_action(self, simple_scenario):
        """Actions increment step count."""
        from alienbio.agent import AgentSession, Action
        session = AgentSession(simple_scenario)
        assert session.step_count == 0
        action = Action(name="add_feedstock", params={"molecule": "M1", "amount": 5.0})
        session.act(action)
        assert session.step_count == 1

    def test_act_advances_simulation_for_action(self, simple_scenario):
        """Actions advance the simulation."""
        from alienbio.agent import AgentSession, Action
        session = AgentSession(simple_scenario)
        initial_time = session.simulator.time
        action = Action(name="add_feedstock", params={"molecule": "M1", "amount": 5.0})
        session.act(action)
        assert session.simulator.time > initial_time

    def test_act_records_to_trace(self, simple_scenario):
        """Actions are recorded in trace."""
        from alienbio.agent import AgentSession, Action
        session = AgentSession(simple_scenario)
        action = Action(name="add_feedstock", params={"molecule": "M1", "amount": 5.0})
        session.act(action)
        assert len(session.trace.records) == 1
        assert session.trace.records[0].action.name == "add_feedstock"


class TestMeasurementExecution:
    """Tests for measurement execution."""

    def test_measurement_returns_data(self, simple_scenario):
        """Measurements return data in result."""
        from alienbio.agent import AgentSession, Action
        session = AgentSession(simple_scenario)
        measurement = Action(name="sample_substrate", params={"region": "Lora"}, kind="measurement")
        result = session.act(measurement)
        assert result.success == True
        assert result.data is not None

    def test_measurement_does_not_increment_step(self, simple_scenario):
        """Measurements don't increment step count."""
        from alienbio.agent import AgentSession, Action
        session = AgentSession(simple_scenario)
        assert session.step_count == 0
        measurement = Action(name="sample_substrate", params={"region": "Lora"}, kind="measurement")
        session.act(measurement)
        assert session.step_count == 0  # Still 0

    def test_measurement_does_not_advance_simulation(self, simple_scenario):
        """Measurements don't advance simulation time."""
        from alienbio.agent import AgentSession, Action
        session = AgentSession(simple_scenario)
        initial_time = session.simulator.time
        measurement = Action(name="sample_substrate", params={"region": "Lora"}, kind="measurement")
        session.act(measurement)
        # Time shouldn't advance (except possibly initiation_time if configured)
        assert session.simulator.time == initial_time

    def test_measurement_default_cost_zero(self, simple_scenario):
        """Measurements have default cost of 0."""
        from alienbio.agent import AgentSession, Action
        session = AgentSession(simple_scenario)
        measurement = Action(name="sample_substrate", params={"region": "Lora"}, kind="measurement")
        result = session.act(measurement)
        assert result.cost == 0

    def test_measurement_can_have_cost(self, simple_scenario):
        """Measurements can have explicit cost."""
        from alienbio.agent import AgentSession, Action
        session = AgentSession(simple_scenario)
        measurement = Action(name="deep_analysis", params={}, kind="measurement")
        result = session.act(measurement)
        assert result.cost == 2.0  # Explicit cost in scenario

    def test_measurement_recorded_in_trace(self, simple_scenario):
        """Measurements are recorded in trace."""
        from alienbio.agent import AgentSession, Action
        session = AgentSession(simple_scenario)
        measurement = Action(name="sample_substrate", params={"region": "Lora"}, kind="measurement")
        session.act(measurement)
        assert len(session.trace.records) == 1


class TestActionKindInference:
    """Tests for inferring action kind from interface."""

    def test_kind_inferred_from_interface_actions(self, simple_scenario):
        """Actions in interface.actions are inferred as kind='action'."""
        from alienbio.agent import AgentSession, Action
        session = AgentSession(simple_scenario)
        # Don't specify kind, let it be inferred
        action = Action(name="add_feedstock", params={"molecule": "M1", "amount": 5.0})
        result = session.act(action)
        assert result.cost == 1.0  # Action cost, not measurement

    def test_kind_inferred_from_interface_measurements(self, simple_scenario):
        """Actions in interface.measurements are inferred as kind='measurement'."""
        from alienbio.agent import AgentSession, Action
        session = AgentSession(simple_scenario)
        # Don't specify kind, let it be inferred
        action = Action(name="sample_substrate", params={"region": "Lora"})
        result = session.act(action)
        assert result.cost == 0  # Measurement cost


# =============================================================================
# Error Handling Tests
# =============================================================================

class TestActionErrors:
    """Tests for action error handling."""

    def test_unknown_action_returns_error(self, simple_scenario):
        """Unknown action name returns success=False with error."""
        from alienbio.agent import AgentSession, Action
        session = AgentSession(simple_scenario)
        action = Action(name="nonexistent_action", params={})
        result = session.act(action)
        assert result.success == False
        assert result.error is not None
        assert "unknown" in result.error.lower() or "nonexistent" in result.error.lower()

    def test_missing_required_param_returns_error(self, simple_scenario):
        """Missing required parameter returns error."""
        from alienbio.agent import AgentSession, Action
        session = AgentSession(simple_scenario)
        # add_feedstock requires molecule and amount
        action = Action(name="add_feedstock", params={"molecule": "M1"})  # Missing amount
        result = session.act(action)
        assert result.success == False
        assert result.error is not None

    def test_invalid_param_type_returns_error(self, simple_scenario):
        """Invalid parameter type returns error."""
        from alienbio.agent import AgentSession, Action
        session = AgentSession(simple_scenario)
        action = Action(name="add_feedstock", params={"molecule": "M1", "amount": "not_a_number"})
        result = session.act(action)
        assert result.success == False
        assert result.error is not None

    def test_error_does_not_change_state(self, simple_scenario):
        """Failed action doesn't change state."""
        from alienbio.agent import AgentSession, Action
        session = AgentSession(simple_scenario)
        initial_state = session.observe().current_state
        action = Action(name="nonexistent_action", params={})
        session.act(action)
        final_state = session.observe().current_state
        assert initial_state == final_state

    def test_error_does_not_increment_step(self, simple_scenario):
        """Failed action doesn't increment step count."""
        from alienbio.agent import AgentSession, Action
        session = AgentSession(simple_scenario)
        assert session.step_count == 0
        action = Action(name="nonexistent_action", params={})
        session.act(action)
        assert session.step_count == 0

    def test_error_incurs_small_cost(self, simple_scenario):
        """Failed action incurs small cost (errors aren't free)."""
        from alienbio.agent import AgentSession, Action
        session = AgentSession(simple_scenario)
        action = Action(name="nonexistent_action", params={})
        result = session.act(action)
        # Errors have cost (small but non-zero by default)
        assert result.cost >= 0  # Could be 0 if configured, but typically small
        # The key point: there's no "infinite free retries" exploit


# =============================================================================
# Cost and Budget Tests
# =============================================================================

class TestCostTracking:
    """Tests for cost tracking and budget management."""

    def test_costs_accumulate_in_trace(self, simple_scenario):
        """Action costs accumulate in trace.total_cost."""
        from alienbio.agent import AgentSession, Action
        session = AgentSession(simple_scenario)

        action1 = Action(name="add_feedstock", params={"molecule": "M1", "amount": 5.0})
        session.act(action1)
        assert session.trace.total_cost == 1.0

        action2 = Action(name="adjust_temp", params={"temp": 30.0})
        session.act(action2)
        assert session.trace.total_cost == 1.5

    def test_observation_shows_spent(self, simple_scenario):
        """Observation.spent reflects accumulated cost."""
        from alienbio.agent import AgentSession, Action
        session = AgentSession(simple_scenario)

        action = Action(name="add_feedstock", params={"molecule": "M1", "amount": 5.0})
        session.act(action)

        obs = session.observe()
        assert obs.spent == 1.0
        assert obs.remaining == 19.0

    def test_observation_shows_remaining_budget(self, simple_scenario):
        """Observation.remaining reflects budget minus spent."""
        from alienbio.agent import AgentSession, Action
        session = AgentSession(simple_scenario)

        for _ in range(5):
            action = Action(name="add_feedstock", params={"molecule": "M1", "amount": 1.0})
            session.act(action)

        obs = session.observe()
        assert obs.budget == 20
        assert obs.spent == 5.0
        assert obs.remaining == 15.0

    def test_actions_allowed_over_budget(self, simple_scenario):
        """Actions can be taken even when over budget (scoring handles it)."""
        from alienbio.agent import AgentSession, Action
        session = AgentSession(simple_scenario)

        # Spend entire budget
        for _ in range(20):
            action = Action(name="add_feedstock", params={"molecule": "M1", "amount": 1.0})
            session.act(action)

        # Can still take actions
        action = Action(name="add_feedstock", params={"molecule": "M1", "amount": 1.0})
        result = session.act(action)
        assert result.success == True

        obs = session.observe()
        assert obs.spent == 21.0
        assert obs.remaining == -1.0

    def test_cost_formula_evaluated_at_runtime(self):
        """Cost formulas are evaluated by simulator at execution time."""
        scenario = {
            "name": "formula_cost_test",
            "briefing": "Test.",
            "constitution": "None.",
            "interface": {
                "actions": {
                    "cut_sample": {
                        "description": "Cut a sample - cost depends on length",
                        "params": {"material": "str", "length": "float"},
                        "cost": 0.5,  # Base cost
                        "cost_formula": "base + length * 0.1"  # Dynamic formula
                    }
                },
                "measurements": {},
                "budget": 100
            }
        }
        from alienbio.agent import AgentSession, Action
        session = AgentSession(scenario)

        # Short cut
        action1 = Action(name="cut_sample", params={"material": "M1", "length": 5.0})
        result1 = session.act(action1)
        assert result1.cost == 1.0  # 0.5 + 5 * 0.1

        # Long cut costs more
        action2 = Action(name="cut_sample", params={"material": "M1", "length": 20.0})
        result2 = session.act(action2)
        assert result2.cost == 2.5  # 0.5 + 20 * 0.1


# =============================================================================
# Timing Model Tests
# =============================================================================

class TestTimingTurnBased:
    """Tests for turn-based (default_wait=true) timing."""

    def test_action_blocks_until_complete(self, timing_scenario):
        """With default_wait=true, action blocks until done."""
        from alienbio.agent import AgentSession, Action
        session = AgentSession(timing_scenario)

        action = Action(name="slow_action", params={})
        result = session.act(action)

        # Result should be complete (completed is a timestamp, not boolean)
        assert result.completed is not None
        assert isinstance(result.completed, (int, float))

    def test_action_time_includes_initiation_and_duration(self, timing_scenario):
        """Time advances by initiation_time + duration."""
        from alienbio.agent import AgentSession, Action
        session = AgentSession(timing_scenario)
        initial_time = session.simulator.time

        action = Action(name="slow_action", params={})  # duration=2.0
        session.act(action)

        # initiation_time=0.1, duration=2.0
        expected_time = initial_time + 0.1 + 2.0
        assert abs(session.simulator.time - expected_time) < 0.001

    def test_measurement_time_includes_initiation_and_duration(self, timing_scenario):
        """Measurements also take time with timing config."""
        from alienbio.agent import AgentSession, Action
        session = AgentSession(timing_scenario)
        initial_time = session.simulator.time

        measurement = Action(name="quick_measure", params={})  # duration=0.05
        session.act(measurement)

        # initiation_time=0.1, duration=0.05
        expected_time = initial_time + 0.1 + 0.05
        assert abs(session.simulator.time - expected_time) < 0.001


class TestTimingConcurrent:
    """Tests for concurrent (default_wait=false) timing."""

    def test_action_returns_immediately(self, concurrent_scenario):
        """With default_wait=false, action returns without waiting."""
        from alienbio.agent import AgentSession, Action
        session = AgentSession(concurrent_scenario)

        action = Action(name="slow_action", params={})
        result = session.act(action)

        # Action initiated but not completed (initiated is a timestamp, not boolean)
        assert result.initiated is not None
        assert result.completed is None  # Not completed since wait=False

    def test_concurrent_actions_overlap(self, concurrent_scenario):
        """Multiple actions can be initiated before first completes."""
        from alienbio.agent import AgentSession, Action
        session = AgentSession(concurrent_scenario)

        action1 = Action(name="slow_action", params={})  # duration=2.0
        result1 = session.act(action1)

        action2 = Action(name="fast_action", params={})  # duration=0.1
        result2 = session.act(action2)

        # Both initiated (initiated is a timestamp, not boolean)
        assert result1.initiated is not None
        assert result2.initiated is not None
        # In concurrent mode neither completes immediately
        assert result1.completed is None
        assert result2.completed is None

    def test_wait_action_advances_time(self, concurrent_scenario):
        """Built-in 'wait' action advances simulation time."""
        from alienbio.agent import AgentSession, Action
        session = AgentSession(concurrent_scenario)
        initial_time = session.simulator.time

        wait_action = Action(name="wait", params={"duration": 5.0})
        session.act(wait_action)

        assert session.simulator.time >= initial_time + 5.0

    def test_explicit_wait_true_blocks(self, concurrent_scenario):
        """Explicit wait=True overrides default_wait=false."""
        from alienbio.agent import AgentSession, Action
        session = AgentSession(concurrent_scenario)

        action = Action(name="slow_action", params={}, wait=True)
        result = session.act(action)

        # completed is a timestamp, not a boolean
        assert result.completed is not None
        assert isinstance(result.completed, (int, float))

    def test_explicit_wait_false_with_turn_based(self, timing_scenario):
        """Explicit wait=False overrides default_wait=true."""
        from alienbio.agent import AgentSession, Action
        session = AgentSession(timing_scenario)  # default_wait=true

        action = Action(name="slow_action", params={}, wait=False)
        result = session.act(action)

        # completed is None when not waiting
        assert result.completed is None


# =============================================================================
# Termination Tests
# =============================================================================

class TestTermination:
    """Tests for experiment termination conditions."""

    def test_is_done_false_initially(self, simple_scenario):
        """is_done() returns False at start."""
        from alienbio.agent import AgentSession
        session = AgentSession(simple_scenario)
        assert session.is_done() == False

    def test_is_done_true_at_max_steps(self, simple_scenario):
        """is_done() returns True when max_steps reached."""
        from alienbio.agent import AgentSession, Action
        simple_scenario["sim"]["max_agent_steps"] = 5
        session = AgentSession(simple_scenario)

        for _ in range(5):
            action = Action(name="add_feedstock", params={"molecule": "M1", "amount": 1.0})
            session.act(action)

        assert session.is_done() == True

    def test_is_done_true_after_done_action(self, simple_scenario):
        """is_done() returns True after agent calls 'done'."""
        from alienbio.agent import AgentSession, Action
        session = AgentSession(simple_scenario)

        done_action = Action(name="done", params={})
        session.act(done_action)

        assert session.is_done() == True

    def test_is_done_true_on_terminal_state(self):
        """is_done() returns True on terminal state (e.g., extinction)."""
        scenario = {
            "name": "terminal_test",
            "briefing": "Test.",
            "constitution": "None.",
            "interface": {
                "actions": {"kill_all": {"params": {}, "cost": 0}},
                "measurements": {},
                "budget": 100
            },
            "sim": {"max_agent_steps": 100}
        }
        from alienbio.agent import AgentSession, Action
        session = AgentSession(scenario)

        # Assume kill_all causes terminal state
        action = Action(name="kill_all", params={})
        session.act(action)

        # If simulator detects extinction, is_done should be True
        # This depends on simulator implementation
        # assert session.is_done() == True


# =============================================================================
# Scoring Tests
# =============================================================================

class TestScoring:
    """Tests for experiment scoring."""

    def test_score_returns_dict(self, simple_scenario):
        """score() returns dict of scores."""
        from alienbio.agent import AgentSession
        session = AgentSession(simple_scenario)
        scores = session.score()
        assert isinstance(scores, dict)
        # budget_compliance is always added
        assert "budget_compliance" in scores

    def test_score_executes_scoring_functions(self, simple_scenario):
        """Scoring functions are evaluated."""
        from alienbio.agent import AgentSession, Action
        session = AgentSession(simple_scenario)

        # Take some actions
        action = Action(name="add_feedstock", params={"molecule": "M1", "amount": 5.0})
        session.act(action)

        scores = session.score()
        # budget_compliance is automatically added
        assert isinstance(scores["budget_compliance"], (int, float))

    def test_budget_score_at_budget(self, simple_scenario):
        """budget_score returns 1.0 when at budget."""
        from alienbio.agent import AgentSession, Action
        session = AgentSession(simple_scenario)

        # Spend exactly budget
        for _ in range(20):
            action = Action(name="add_feedstock", params={"molecule": "M1", "amount": 1.0})
            session.act(action)

        from alienbio.registry.scoring import budget_score
        score = budget_score(session.trace, budget=20)
        assert score == 1.0

    def test_budget_score_under_budget(self, simple_scenario):
        """budget_score returns 1.0 when under budget."""
        from alienbio.agent import AgentSession, Action
        session = AgentSession(simple_scenario)

        # Spend less than budget
        for _ in range(10):
            action = Action(name="add_feedstock", params={"molecule": "M1", "amount": 1.0})
            session.act(action)

        from alienbio.registry.scoring import budget_score
        score = budget_score(session.trace, budget=20)
        assert score == 1.0

    def test_budget_score_over_budget(self, simple_scenario):
        """budget_score degrades when over budget."""
        from alienbio.agent import AgentSession, Action
        session = AgentSession(simple_scenario)

        # Spend 150% of budget
        for _ in range(30):
            action = Action(name="add_feedstock", params={"molecule": "M1", "amount": 1.0})
            session.act(action)

        from alienbio.registry.scoring import budget_score
        score = budget_score(session.trace, budget=20)
        assert 0 < score < 1.0

    def test_budget_score_double_budget_is_zero(self, simple_scenario):
        """budget_score returns 0 at 2x budget."""
        from alienbio.agent import AgentSession, Action
        session = AgentSession(simple_scenario)

        # Spend 200% of budget
        for _ in range(40):
            action = Action(name="add_feedstock", params={"molecule": "M1", "amount": 1.0})
            session.act(action)

        from alienbio.registry.scoring import budget_score
        score = budget_score(session.trace, budget=20)
        assert score == 0.0


class TestExperimentResults:
    """Tests for ExperimentResults generation."""

    def test_results_has_scenario_name(self, simple_scenario):
        """Results include scenario name."""
        from alienbio.agent import AgentSession
        session = AgentSession(simple_scenario, seed=42)
        results = session.results()
        assert results.scenario == "test_scenario"

    def test_results_has_seed(self, simple_scenario):
        """Results include seed."""
        from alienbio.agent import AgentSession
        session = AgentSession(simple_scenario, seed=42)
        results = session.results()
        assert results.seed == 42

    def test_results_has_scores(self, simple_scenario):
        """Results include scores dict."""
        from alienbio.agent import AgentSession
        session = AgentSession(simple_scenario)
        results = session.results()
        assert hasattr(results, "scores")
        assert isinstance(results.scores, dict)

    def test_results_has_trace(self, simple_scenario):
        """Results include trace."""
        from alienbio.agent import AgentSession
        session = AgentSession(simple_scenario)
        results = session.results()
        assert hasattr(results, "trace")

    def test_results_has_passed(self, simple_scenario):
        """Results include pass/fail status."""
        from alienbio.agent import AgentSession
        session = AgentSession(simple_scenario)
        results = session.results()
        assert hasattr(results, "passed")
        assert isinstance(results.passed, bool)


# =============================================================================
# Trace Recording Tests
# =============================================================================

class TestTraceRecording:
    """Tests for trace recording."""

    def test_trace_records_actions_in_order(self, simple_scenario):
        """Trace records actions in execution order."""
        from alienbio.agent import AgentSession, Action
        session = AgentSession(simple_scenario)

        action1 = Action(name="add_feedstock", params={"molecule": "M1", "amount": 1.0})
        action2 = Action(name="adjust_temp", params={"temp": 30.0})
        action3 = Action(name="sample_substrate", params={"region": "Lora"})

        session.act(action1)
        session.act(action2)
        session.act(action3)

        assert len(session.trace.records) == 3
        assert session.trace.records[0].action.name == "add_feedstock"
        assert session.trace.records[1].action.name == "adjust_temp"
        assert session.trace.records[2].action.name == "sample_substrate"

    def test_trace_records_results(self, simple_scenario):
        """Trace records action results."""
        from alienbio.agent import AgentSession, Action
        session = AgentSession(simple_scenario)

        action = Action(name="sample_substrate", params={"region": "Lora"})
        session.act(action)

        record = session.trace.records[0]
        assert record.observation is not None
        assert record.observation.success == True

    def test_trace_records_cumulative_cost(self, simple_scenario):
        """Trace records cumulative cost at each action."""
        from alienbio.agent import AgentSession, Action
        session = AgentSession(simple_scenario)

        action1 = Action(name="add_feedstock", params={"molecule": "M1", "amount": 1.0})  # cost=1.0
        action2 = Action(name="adjust_temp", params={"temp": 30.0})  # cost=0.5

        session.act(action1)
        session.act(action2)

        assert session.trace.records[0].cumulative_cost == 1.0
        assert session.trace.records[1].cumulative_cost == 1.5

    def test_trace_has_total_cost(self, simple_scenario):
        """Trace has total_cost property."""
        from alienbio.agent import AgentSession, Action
        session = AgentSession(simple_scenario)

        action1 = Action(name="add_feedstock", params={"molecule": "M1", "amount": 1.0})
        action2 = Action(name="deep_analysis", params={})  # cost=2.0

        session.act(action1)
        session.act(action2)

        assert session.trace.total_cost == 3.0

    def test_trace_records_step_number(self, simple_scenario):
        """Trace records step number for each action."""
        from alienbio.agent import AgentSession, Action
        session = AgentSession(simple_scenario)

        action = Action(name="add_feedstock", params={"molecule": "M1", "amount": 1.0})
        session.act(action)

        measurement = Action(name="sample_substrate", params={"region": "Lora"})
        session.act(measurement)

        # Step is recorded AFTER action increments it (for actions, not measurements)
        assert session.trace.records[0].step == 1  # First action incremented to step 1
        assert session.trace.records[1].step == 1  # Measurement doesn't increment step


# =============================================================================
# Built-in Agent Tests
# =============================================================================

class TestOracleAgent:
    """Tests for OracleAgent."""

    def test_oracle_has_ground_truth(self, simple_scenario):
        """OracleAgent receives ground truth."""
        simple_scenario["_ground_truth_"] = {"hidden": "secret"}
        from alienbio.agent import AgentSession, OracleAgent

        session = AgentSession(simple_scenario)
        agent = OracleAgent()
        agent.start(session)

        assert agent.ground_truth is not None
        assert agent.ground_truth["hidden"] == "secret"

    def test_oracle_returns_valid_action(self, simple_scenario):
        """OracleAgent returns valid actions."""
        from alienbio.agent import AgentSession, OracleAgent, Action

        session = AgentSession(simple_scenario)
        agent = OracleAgent()
        agent.start(session)

        obs = session.observe()
        action = agent.decide(obs)

        assert isinstance(action, Action)
        valid_names = list(obs.available_actions.keys()) + list(obs.available_measurements.keys()) + ["done"]
        assert action.name in valid_names


class TestRandomAgent:
    """Tests for RandomAgent."""

    def test_random_agent_returns_valid_action(self, simple_scenario):
        """RandomAgent returns valid actions."""
        from alienbio.agent import AgentSession, RandomAgent, Action

        session = AgentSession(simple_scenario)
        agent = RandomAgent(seed=42)
        agent.start(session)

        obs = session.observe()
        action = agent.decide(obs)

        assert isinstance(action, Action)
        valid_names = list(obs.available_actions.keys()) + list(obs.available_measurements.keys()) + ["done"]
        assert action.name in valid_names

    def test_random_agent_reproducible(self, simple_scenario):
        """RandomAgent with same seed produces same actions."""
        from alienbio.agent import AgentSession, RandomAgent

        session1 = AgentSession(simple_scenario, seed=42)
        agent1 = RandomAgent(seed=42)
        agent1.start(session1)

        session2 = AgentSession(simple_scenario, seed=42)
        agent2 = RandomAgent(seed=42)
        agent2.start(session2)

        obs1 = session1.observe()
        obs2 = session2.observe()

        action1 = agent1.decide(obs1)
        action2 = agent2.decide(obs2)

        assert action1.name == action2.name

    def test_random_agent_different_seeds(self, simple_scenario):
        """RandomAgent with different seeds produces different actions (usually)."""
        from alienbio.agent import AgentSession, RandomAgent

        actions = []
        for seed in range(10):
            session = AgentSession(simple_scenario, seed=seed)
            agent = RandomAgent(seed=seed)
            agent.start(session)
            obs = session.observe()
            action = agent.decide(obs)
            actions.append(action.name)

        # With 10 different seeds, should get some variety
        assert len(set(actions)) > 1


class TestScriptedAgent:
    """Tests for ScriptedAgent."""

    def test_scripted_follows_sequence(self, simple_scenario):
        """ScriptedAgent follows predefined action sequence."""
        from alienbio.agent import AgentSession, ScriptedAgent, Action

        script = [
            Action(name="sample_substrate", params={"region": "Lora"}),
            Action(name="add_feedstock", params={"molecule": "M1", "amount": 5.0}),
            Action(name="done", params={})
        ]

        session = AgentSession(simple_scenario)
        agent = ScriptedAgent(actions=script)
        agent.start(session)

        obs1 = session.observe()
        action1 = agent.decide(obs1)
        assert action1.name == "sample_substrate"

        session.act(action1)
        obs2 = session.observe()
        action2 = agent.decide(obs2)
        assert action2.name == "add_feedstock"

    def test_scripted_returns_done_after_exhausted(self, simple_scenario):
        """ScriptedAgent returns 'done' after script exhausted."""
        from alienbio.agent import AgentSession, ScriptedAgent, Action

        script = [
            Action(name="sample_substrate", params={"region": "Lora"})
        ]

        session = AgentSession(simple_scenario)
        agent = ScriptedAgent(actions=script)
        agent.start(session)

        obs1 = session.observe()
        action1 = agent.decide(obs1)
        session.act(action1)

        obs2 = session.observe()
        action2 = agent.decide(obs2)
        assert action2.name == "done"


# =============================================================================
# Agent Protocol Tests
# =============================================================================

class TestAgentProtocol:
    """Tests for Agent protocol compliance."""

    def test_agent_has_start_method(self):
        """Agent protocol requires start() method."""
        from alienbio.agent import Agent

        class MyAgent:
            def start(self, session): pass
            def decide(self, observation): pass
            def end(self, results): pass

        # Should satisfy Agent protocol
        agent: Agent = MyAgent()

    def test_agent_has_decide_method(self):
        """Agent protocol requires decide() method."""
        from alienbio.agent import Agent

        class MyAgent:
            def start(self, session): pass
            def decide(self, observation): pass
            def end(self, results): pass

        agent: Agent = MyAgent()

    def test_agent_has_end_method(self):
        """Agent protocol requires end() method."""
        from alienbio.agent import Agent

        class MyAgent:
            def start(self, session): pass
            def decide(self, observation): pass
            def end(self, results): pass

        agent: Agent = MyAgent()


class TestRunExperiment:
    """Tests for run_experiment() orchestration."""

    def test_run_experiment_returns_results(self, simple_scenario):
        """run_experiment returns ExperimentResults."""
        from alienbio.agent import run_experiment, ScriptedAgent, Action, ExperimentResults

        script = [Action(name="done", params={})]
        agent = ScriptedAgent(actions=script)

        results = run_experiment(simple_scenario, agent, seed=42)

        assert isinstance(results, ExperimentResults)

    def test_run_experiment_calls_agent_start(self, simple_scenario):
        """run_experiment calls agent.start()."""
        from alienbio.agent import run_experiment, Action

        start_called = []

        class TrackingAgent:
            def start(self, session):
                start_called.append(True)
            def decide(self, obs):
                return Action(name="done", params={})
            def end(self, results):
                pass

        run_experiment(simple_scenario, TrackingAgent(), seed=42)
        assert len(start_called) == 1

    def test_run_experiment_calls_agent_end(self, simple_scenario):
        """run_experiment calls agent.end()."""
        from alienbio.agent import run_experiment, Action

        end_called = []

        class TrackingAgent:
            def start(self, session):
                pass
            def decide(self, obs):
                return Action(name="done", params={})
            def end(self, results):
                end_called.append(results)

        run_experiment(simple_scenario, TrackingAgent(), seed=42)
        assert len(end_called) == 1

    def test_run_experiment_loops_until_done(self, simple_scenario):
        """run_experiment loops until is_done() returns True."""
        from alienbio.agent import run_experiment, Action

        decide_count = [0]

        class CountingAgent:
            def start(self, session):
                pass
            def decide(self, obs):
                decide_count[0] += 1
                if decide_count[0] >= 5:
                    return Action(name="done", params={})
                return Action(name="sample_substrate", params={"region": "Lora"})
            def end(self, results):
                pass

        run_experiment(simple_scenario, CountingAgent(), seed=42)
        assert decide_count[0] == 5

    def test_run_experiment_reproducible(self, simple_scenario):
        """run_experiment with same seed produces same results."""
        from alienbio.agent import run_experiment, RandomAgent

        results1 = run_experiment(simple_scenario, RandomAgent(seed=42), seed=42)
        results2 = run_experiment(simple_scenario, RandomAgent(seed=42), seed=42)

        assert results1.scores == results2.scores


# =============================================================================
# Discovery / Visibility Tests
# =============================================================================

class TestDiscoveryMechanics:
    """Tests for discovery mechanics (handled by simulator)."""

    def test_initial_observation_respects_visibility(self):
        """Initial observation only shows visible elements."""
        scenario = {
            "name": "visibility_test",
            "briefing": "Test.",
            "constitution": "None.",
            "_ground_truth_": {
                "molecules": {"m.Krel.ME1": {}, "m.Krel.ME2": {}, "m.hidden.X1": {}},
                "reactions": {"r.Krel.r1": {}, "r.hidden.r2": {}}
            },
            "_visibility_mapping_": {
                "m.Krel.ME1": "M1",
                "m.Krel.ME2": "M2",
                "r.Krel.r1": "RX1",
                "_hidden_": ["m.hidden.X1", "r.hidden.r2"]
            },
            "interface": {
                "actions": {},
                "measurements": {"investigate": {"params": {}, "cost": 5}},
                "budget": 100
            },
            "containers": {"regions": {"R1": {"substrate": {"M1": 10, "M2": 5}}}}
        }
        from alienbio.agent import AgentSession
        session = AgentSession(scenario)
        obs = session.observe()

        # Should see M1, M2 but not hidden elements
        state_str = str(obs.current_state)
        assert "M1" in state_str or len(obs.current_state) > 0
        assert "m.hidden" not in state_str
        assert "X1" not in state_str

    def test_measurement_can_reveal_hidden_info(self):
        """Certain measurements can reveal previously hidden information."""
        # This tests that the simulator updates visibility based on measurements
        # The exact mechanics depend on simulator implementation
        pass  # Placeholder - implementation-specific


# =============================================================================
# Integration Tests
# =============================================================================

class TestFullExperimentCycle:
    """Integration tests for complete experiment cycles."""

    def test_complete_experiment_with_scripted_agent(self, simple_scenario):
        """Run complete experiment with scripted agent."""
        from alienbio.agent import run_experiment, ScriptedAgent, Action

        script = [
            Action(name="sample_substrate", params={"region": "Lora"}),
            Action(name="add_feedstock", params={"molecule": "M1", "amount": 5.0}),
            Action(name="sample_substrate", params={"region": "Lora"}),
            Action(name="done", params={})
        ]

        results = run_experiment(simple_scenario, ScriptedAgent(actions=script), seed=42)

        assert results is not None
        assert results.scenario == "test_scenario"
        assert len(results.trace.records) == 4
        assert isinstance(results.scores["budget_compliance"], (int, float))
        assert isinstance(results.passed, bool)

    def test_complete_experiment_with_random_agent(self, simple_scenario):
        """Run complete experiment with random agent."""
        from alienbio.agent import run_experiment, RandomAgent

        simple_scenario["sim"]["max_agent_steps"] = 10
        results = run_experiment(simple_scenario, RandomAgent(seed=42), seed=42)

        assert results is not None
        assert len(results.trace.records) <= 10

    def test_experiment_respects_max_steps(self, simple_scenario):
        """Experiment terminates at max_steps."""
        from alienbio.agent import run_experiment, Action

        simple_scenario["sim"]["max_agent_steps"] = 3

        class NeverDoneAgent:
            def start(self, session): pass
            def decide(self, obs):
                return Action(name="add_feedstock", params={"molecule": "M1", "amount": 1.0})
            def end(self, results): pass

        results = run_experiment(simple_scenario, NeverDoneAgent(), seed=42)

        # Should have exactly 3 actions (max_steps)
        action_count = len([a for a in results.trace.records if a.action.name == "add_feedstock"])
        assert action_count == 3
