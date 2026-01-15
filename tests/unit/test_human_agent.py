"""Tests for HumanAgent - M3.3 Built-in Agents.

These tests verify the HumanAgent implementation:
- Interactive CLI interface
- Action parsing
- State display
- Budget display
"""

import pytest
from unittest.mock import patch, MagicMock
from io import StringIO

from alienbio.agent import HumanAgent, Action, AgentSession, Observation


@pytest.fixture
def simple_scenario():
    """Minimal scenario for testing."""
    return {
        "name": "test_scenario",
        "briefing": "You are testing an alien ecosystem.",
        "constitution": "Do no harm.",
        "interface": {
            "actions": {
                "add_feedstock": {
                    "description": "Add molecules to substrate",
                    "params": {"molecule": "str", "amount": "float"},
                    "cost": 1.0
                },
            },
            "measurements": {
                "sample_substrate": {
                    "description": "Measure concentrations",
                    "params": {"region": "str"},
                    "cost": 0
                },
            },
            "budget": 20
        },
        "sim": {"max_agent_steps": 50},
        "containers": {
            "regions": {"Lora": {"substrate": {"M1": 10.0}}}
        }
    }


@pytest.fixture
def mock_observation():
    """Create a mock observation for testing."""
    return Observation(
        briefing="Test briefing",
        constitution="Test constitution",
        available_actions={
            "add_feedstock": {"description": "Add stuff", "cost": 1.0}
        },
        available_measurements={
            "sample": {"description": "Measure stuff", "cost": 0}
        },
        current_state={"regions": {"R1": {"M1": 5.0}}},
        step=0,
        budget=20.0,
        spent=0.0,
        remaining=20.0,
        _is_initial=True
    )


class TestHumanAgentBasics:
    """Basic HumanAgent functionality tests."""

    def test_human_agent_creates(self):
        """HumanAgent can be instantiated."""
        agent = HumanAgent()
        assert agent is not None

    def test_human_agent_custom_prompt(self):
        """HumanAgent accepts custom prompt."""
        agent = HumanAgent(prompt=">>> ")
        assert agent._prompt == ">>> "

    def test_human_agent_start_stores_session(self, simple_scenario, capsys):
        """start() stores session reference and displays briefing."""
        session = AgentSession(simple_scenario)
        agent = HumanAgent()
        agent.start(session)

        assert agent._session is session

        # Check output includes scenario info
        captured = capsys.readouterr()
        assert "test_scenario" in captured.out
        assert "alien ecosystem" in captured.out


class TestHumanAgentParsing:
    """Tests for action parsing."""

    def test_parse_simple_action(self, mock_observation):
        """Parse action name without parameters."""
        agent = HumanAgent()
        action = agent._parse_action("add_feedstock", mock_observation)

        assert action is not None
        assert action.name == "add_feedstock"
        assert action.params == {}

    def test_parse_action_with_params(self, mock_observation):
        """Parse action with parameters."""
        agent = HumanAgent()
        action = agent._parse_action("add_feedstock molecule=M1 amount=5.0", mock_observation)

        assert action is not None
        assert action.name == "add_feedstock"
        assert action.params["molecule"] == "M1"
        assert action.params["amount"] == 5.0

    def test_parse_action_with_int_param(self, mock_observation):
        """Parse action with integer parameter."""
        agent = HumanAgent()
        action = agent._parse_action("add_feedstock count=10", mock_observation)

        assert action is not None
        assert action.params["count"] == 10
        assert isinstance(action.params["count"], int)

    def test_parse_unknown_action_returns_none(self, mock_observation):
        """Unknown action returns None."""
        agent = HumanAgent()
        action = agent._parse_action("unknown_action", mock_observation)

        assert action is None

    def test_parse_measurement(self, mock_observation):
        """Parse measurement action."""
        agent = HumanAgent()
        action = agent._parse_action("sample region=R1", mock_observation)

        assert action is not None
        assert action.name == "sample"
        assert action.params["region"] == "R1"


class TestHumanAgentDecide:
    """Tests for decide() method with mocked input."""

    def test_decide_done_command(self, mock_observation):
        """'done' command returns done action."""
        agent = HumanAgent()

        with patch('builtins.input', return_value='done'):
            action = agent.decide(mock_observation)

        assert action.name == "done"

    def test_decide_action_command(self, mock_observation):
        """Action command returns parsed action."""
        agent = HumanAgent()

        with patch('builtins.input', return_value='add_feedstock molecule=M1'):
            action = agent.decide(mock_observation)

        assert action.name == "add_feedstock"
        assert action.params["molecule"] == "M1"

    def test_decide_help_then_done(self, mock_observation, capsys):
        """Help command displays info, then done exits."""
        agent = HumanAgent()

        with patch('builtins.input', side_effect=['?', 'done']):
            action = agent.decide(mock_observation)

        assert action.name == "done"
        captured = capsys.readouterr()
        assert "Available Actions" in captured.out

    def test_decide_state_then_done(self, mock_observation, capsys):
        """State command displays state, then done exits."""
        agent = HumanAgent()

        with patch('builtins.input', side_effect=['state', 'done']):
            action = agent.decide(mock_observation)

        assert action.name == "done"
        captured = capsys.readouterr()
        assert "State:" in captured.out

    def test_decide_budget_then_done(self, mock_observation, capsys):
        """Budget command displays budget, then done exits."""
        agent = HumanAgent()

        with patch('builtins.input', side_effect=['budget', 'done']):
            action = agent.decide(mock_observation)

        assert action.name == "done"
        captured = capsys.readouterr()
        assert "Budget:" in captured.out

    def test_decide_handles_eof(self, mock_observation, capsys):
        """EOF (Ctrl+D) returns done action."""
        agent = HumanAgent()

        with patch('builtins.input', side_effect=EOFError()):
            action = agent.decide(mock_observation)

        assert action.name == "done"
        captured = capsys.readouterr()
        assert "Interrupted" in captured.out

    def test_decide_handles_keyboard_interrupt(self, mock_observation, capsys):
        """Keyboard interrupt (Ctrl+C) returns done action."""
        agent = HumanAgent()

        with patch('builtins.input', side_effect=KeyboardInterrupt()):
            action = agent.decide(mock_observation)

        assert action.name == "done"


class TestHumanAgentEnd:
    """Tests for end() method."""

    def test_end_displays_results(self, capsys):
        """end() displays experiment results."""
        from alienbio.agent import ExperimentResults

        agent = HumanAgent()
        results = ExperimentResults(
            scenario="test",
            seed=42,
            scores={"budget_compliance": 1.0, "accuracy": 0.8},
            trace=None,
            passed=True,
            status="completed"
        )

        agent.end(results)

        captured = capsys.readouterr()
        assert "EXPERIMENT COMPLETE" in captured.out
        assert "Passed: True" in captured.out
        assert "budget_compliance" in captured.out
        assert "0.800" in captured.out


class TestHumanAgentIntegration:
    """Integration tests with AgentSession."""

    def test_full_interaction_cycle(self, simple_scenario, capsys):
        """Complete interaction: start, decide (done), end."""
        from alienbio.agent import run_experiment

        agent = HumanAgent()

        # Mock input to immediately say 'done'
        with patch('builtins.input', return_value='done'):
            results = run_experiment(simple_scenario, agent, seed=42)

        assert results is not None
        assert results.status == "completed"

        captured = capsys.readouterr()
        assert "test_scenario" in captured.out
        assert "EXPERIMENT COMPLETE" in captured.out
