"""Tests for ClaudeAgentSDKBinding - M3.6.

Tests cover:
- Agent initialization
- System prompt generation
- Tool definition generation from interface (when SDK available)
- Graceful handling when SDK not installed
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import json

from alienbio.agent import ClaudeAgentSDKBinding, AgentSession, Observation, Action


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
            "sample_substrate": {"description": "Measure stuff", "cost": 0}
        },
        current_state={"regions": {"R1": {"M1": 5.0}}},
        step=0,
        budget=20.0,
        spent=0.0,
        remaining=20.0,
        _is_initial=True
    )


class TestClaudeAgentSDKBindingBasics:
    """Basic agent creation and initialization."""

    def test_agent_creates(self):
        """Agent can be instantiated."""
        agent = ClaudeAgentSDKBinding()
        assert agent is not None

    def test_agent_with_explicit_params(self):
        """Agent accepts explicit parameters."""
        agent = ClaudeAgentSDKBinding(
            model="claude-opus-4-20250514",
            api_key="test-key"
        )
        assert agent._model == "claude-opus-4-20250514"
        assert agent._api_key == "test-key"

    def test_agent_default_model(self):
        """Agent has default model."""
        agent = ClaudeAgentSDKBinding()
        assert "claude" in agent._model.lower()

    def test_agent_start_initializes_session(self, simple_scenario):
        """start() sets up session reference."""
        agent = ClaudeAgentSDKBinding()
        session = AgentSession(simple_scenario)

        agent.start(session)

        assert agent._session is session
        assert agent._system_prompt != ""


class TestSystemPromptGeneration:
    """Tests for system prompt building."""

    def test_system_prompt_includes_briefing(self, simple_scenario):
        """System prompt includes scenario briefing."""
        agent = ClaudeAgentSDKBinding()
        session = AgentSession(simple_scenario)
        agent.start(session)

        assert "alien ecosystem" in agent._system_prompt

    def test_system_prompt_includes_constitution(self, simple_scenario):
        """System prompt includes constitution."""
        agent = ClaudeAgentSDKBinding()
        session = AgentSession(simple_scenario)
        agent.start(session)

        assert "no harm" in agent._system_prompt

    def test_system_prompt_includes_instructions(self, simple_scenario):
        """System prompt includes general instructions."""
        agent = ClaudeAgentSDKBinding()
        session = AgentSession(simple_scenario)
        agent.start(session)

        assert "tool" in agent._system_prompt.lower()


class TestObservationFormatting:
    """Tests for observation formatting."""

    def test_observation_format_includes_state(self, mock_observation):
        """Observation message includes current state."""
        agent = ClaudeAgentSDKBinding()
        msg = agent._format_observation(mock_observation)

        assert "M1" in msg
        assert "5.0" in msg

    def test_observation_format_includes_budget(self, mock_observation):
        """Observation message includes budget info."""
        agent = ClaudeAgentSDKBinding()
        msg = agent._format_observation(mock_observation)

        assert "Budget" in msg
        assert "20.0" in msg

    def test_initial_observation_has_instruction(self, mock_observation):
        """Initial observation includes starting instruction."""
        agent = ClaudeAgentSDKBinding()
        msg = agent._format_observation(mock_observation)

        assert "initial" in msg.lower() or "first" in msg.lower()


class TestSDKNotInstalled:
    """Tests for graceful handling when SDK is not installed."""

    def test_decide_without_sdk_returns_done(self, simple_scenario, mock_observation):
        """decide() returns done action when SDK not installed."""
        agent = ClaudeAgentSDKBinding()
        session = AgentSession(simple_scenario)
        agent.start(session)

        # Mock ImportError for claude_agent_sdk
        with patch.dict('sys.modules', {'claude_agent_sdk': None}):
            # The import will fail, returning a done action
            action = agent.decide(mock_observation)

        # Should return some action (either done or error-based done)
        assert action is not None
        assert isinstance(action, Action)


class TestEndCleanup:
    """Tests for end() cleanup."""

    def test_end_clears_session(self, simple_scenario):
        """end() clears session reference."""
        agent = ClaudeAgentSDKBinding()
        session = AgentSession(simple_scenario)
        agent.start(session)

        assert agent._session is session

        from alienbio.agent import ExperimentResults
        results = ExperimentResults(
            scenario="test", seed=42, scores={}, trace=None, passed=True
        )
        agent.end(results)

        assert agent._session is None


class TestMCPServerBuilding:
    """Tests for MCP server building (when SDK available)."""

    def test_build_mcp_server_without_sdk(self, simple_scenario):
        """_build_mcp_server returns empty when SDK not installed."""
        agent = ClaudeAgentSDKBinding()

        # Mock ImportError
        with patch.dict('sys.modules', {'claude_agent_sdk': None}):
            server, tools = agent._build_mcp_server(simple_scenario["interface"])

        assert server is None
        assert tools == []


class TestToolCreation:
    """Tests for tool creation from interface."""

    def test_create_sdk_tool_without_sdk(self, simple_scenario):
        """_create_sdk_tool returns None when SDK not installed."""
        agent = ClaudeAgentSDKBinding()

        with patch.dict('sys.modules', {'claude_agent_sdk': None}):
            tool = agent._create_sdk_tool(
                "test_action",
                {"description": "Test", "params": {"x": "str"}, "cost": 1.0},
                is_action=True
            )

        assert tool is None


# Skip integration tests if SDK not installed
try:
    import claude_agent_sdk
    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False


@pytest.mark.skipif(not SDK_AVAILABLE, reason="claude-agent-sdk not installed")
class TestWithSDKInstalled:
    """Tests that require the actual SDK."""

    def test_mcp_server_created_with_tools(self, simple_scenario):
        """MCP server is created with tools from interface."""
        agent = ClaudeAgentSDKBinding()
        session = AgentSession(simple_scenario)
        agent.start(session)

        # Should have tools for actions + measurements + done
        assert len(agent._tool_names) >= 3
        assert any("add_feedstock" in t for t in agent._tool_names)
        assert any("sample_substrate" in t for t in agent._tool_names)
        assert any("done" in t for t in agent._tool_names)

    def test_tool_names_have_mcp_prefix(self, simple_scenario):
        """Tool names have MCP server prefix."""
        agent = ClaudeAgentSDKBinding()
        session = AgentSession(simple_scenario)
        agent.start(session)

        for tool_name in agent._tool_names:
            assert tool_name.startswith("mcp__alienbio__")
