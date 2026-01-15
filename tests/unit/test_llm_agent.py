"""Tests for ConversationalLLMAgent - M3.5.

Tests cover:
- Agent initialization
- System prompt generation
- Tool definition generation from interface
- Message formatting
- Response parsing (Anthropic and OpenAI formats)
"""

import pytest
from unittest.mock import MagicMock, patch
import json

from alienbio.agent import ConversationalLLMAgent, AgentSession, Observation, Action


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


class TestConversationalLLMAgentBasics:
    """Basic agent creation and initialization."""

    def test_agent_creates(self):
        """Agent can be instantiated."""
        with patch('alienbio.config.get_api_key', return_value="test-key"):
            with patch('alienbio.config.get_default_model', return_value="test-model"):
                agent = ConversationalLLMAgent()
        assert agent is not None

    def test_agent_with_explicit_params(self):
        """Agent accepts explicit parameters."""
        agent = ConversationalLLMAgent(
            model="claude-sonnet-4-20250514",
            api="anthropic",
            api_key="test-key"
        )
        assert agent._model == "claude-sonnet-4-20250514"
        assert agent._api == "anthropic"
        assert agent._api_key == "test-key"

    def test_agent_start_initializes_session(self, simple_scenario):
        """start() sets up session reference."""
        agent = ConversationalLLMAgent(api_key="test-key")
        session = AgentSession(simple_scenario)

        agent.start(session)

        assert agent._session is session
        assert len(agent._messages) == 0
        assert len(agent._tools) > 0


class TestSystemPromptGeneration:
    """Tests for system prompt building."""

    def test_system_prompt_includes_briefing(self, simple_scenario):
        """System prompt includes scenario briefing."""
        agent = ConversationalLLMAgent(api_key="test-key")
        session = AgentSession(simple_scenario)
        agent.start(session)

        assert "alien ecosystem" in agent._system_prompt

    def test_system_prompt_includes_constitution(self, simple_scenario):
        """System prompt includes constitution."""
        agent = ConversationalLLMAgent(api_key="test-key")
        session = AgentSession(simple_scenario)
        agent.start(session)

        assert "no harm" in agent._system_prompt

    def test_system_prompt_includes_instructions(self, simple_scenario):
        """System prompt includes general instructions."""
        agent = ConversationalLLMAgent(api_key="test-key")
        session = AgentSession(simple_scenario)
        agent.start(session)

        assert "tool" in agent._system_prompt.lower()


class TestToolGeneration:
    """Tests for converting interface to tool definitions."""

    def test_actions_converted_to_tools(self, simple_scenario):
        """Interface actions become tool definitions."""
        agent = ConversationalLLMAgent(api_key="test-key")
        session = AgentSession(simple_scenario)
        agent.start(session)

        tool_names = [t["name"] for t in agent._tools]
        assert "add_feedstock" in tool_names

    def test_measurements_converted_to_tools(self, simple_scenario):
        """Interface measurements become tool definitions."""
        agent = ConversationalLLMAgent(api_key="test-key")
        session = AgentSession(simple_scenario)
        agent.start(session)

        tool_names = [t["name"] for t in agent._tools]
        assert "sample_substrate" in tool_names

    def test_done_tool_always_added(self, simple_scenario):
        """'done' tool is always added."""
        agent = ConversationalLLMAgent(api_key="test-key")
        session = AgentSession(simple_scenario)
        agent.start(session)

        tool_names = [t["name"] for t in agent._tools]
        assert "done" in tool_names

    def test_tool_has_description(self, simple_scenario):
        """Tools include description with cost."""
        agent = ConversationalLLMAgent(api_key="test-key")
        session = AgentSession(simple_scenario)
        agent.start(session)

        add_tool = [t for t in agent._tools if t["name"] == "add_feedstock"][0]
        assert "Add molecules" in add_tool["description"]
        assert "cost" in add_tool["description"].lower()

    def test_tool_has_input_schema(self, simple_scenario):
        """Tools have proper input schema."""
        agent = ConversationalLLMAgent(api_key="test-key")
        session = AgentSession(simple_scenario)
        agent.start(session)

        add_tool = [t for t in agent._tools if t["name"] == "add_feedstock"][0]
        schema = add_tool["input_schema"]

        assert schema["type"] == "object"
        assert "molecule" in schema["properties"]
        assert "amount" in schema["properties"]

    def test_param_types_converted_correctly(self, simple_scenario):
        """Parameter types are converted to JSON schema types."""
        agent = ConversationalLLMAgent(api_key="test-key")
        session = AgentSession(simple_scenario)
        agent.start(session)

        add_tool = [t for t in agent._tools if t["name"] == "add_feedstock"][0]
        props = add_tool["input_schema"]["properties"]

        assert props["molecule"]["type"] == "string"
        assert props["amount"]["type"] == "number"


class TestMessageFormatting:
    """Tests for message formatting."""

    def test_observation_format_includes_state(self, mock_observation):
        """Observation message includes current state."""
        agent = ConversationalLLMAgent(api_key="test-key")
        msg = agent._format_observation(mock_observation)

        assert "M1" in msg
        assert "5.0" in msg

    def test_observation_format_includes_budget(self, mock_observation):
        """Observation message includes budget info."""
        agent = ConversationalLLMAgent(api_key="test-key")
        msg = agent._format_observation(mock_observation)

        assert "Budget" in msg
        assert "20.0" in msg

    def test_initial_observation_has_instruction(self, mock_observation):
        """Initial observation includes starting instruction."""
        agent = ConversationalLLMAgent(api_key="test-key")
        msg = agent._format_observation(mock_observation)

        assert "initial" in msg.lower() or "first" in msg.lower()


class TestAnthropicResponseParsing:
    """Tests for parsing Anthropic Claude responses."""

    def test_parse_tool_use_response(self):
        """Parse tool_use block from Anthropic response."""
        agent = ConversationalLLMAgent(api="anthropic", api_key="test-key")

        # Mock Anthropic response with tool_use
        mock_response = MagicMock()
        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "I will add some feedstock."

        tool_block = MagicMock()
        tool_block.type = "tool_use"
        tool_block.name = "add_feedstock"
        tool_block.input = {"molecule": "M1", "amount": 5.0}

        mock_response.content = [text_block, tool_block]

        action = agent._parse_anthropic_response(mock_response)

        assert action.name == "add_feedstock"
        assert action.params["molecule"] == "M1"
        assert action.params["amount"] == 5.0
        assert "feedstock" in action.reasoning

    def test_parse_text_only_response_returns_done(self):
        """Text-only response returns done action."""
        agent = ConversationalLLMAgent(api="anthropic", api_key="test-key")

        mock_response = MagicMock()
        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "I have completed my task."
        mock_response.content = [text_block]

        action = agent._parse_anthropic_response(mock_response)

        assert action.name == "done"


class TestOpenAIResponseParsing:
    """Tests for parsing OpenAI responses."""

    def test_parse_tool_call_response(self):
        """Parse tool_calls from OpenAI response."""
        agent = ConversationalLLMAgent(api="openai", api_key="test-key")

        # Mock OpenAI response with tool call
        mock_response = MagicMock()
        mock_message = MagicMock()
        mock_message.content = "I will sample the substrate."

        mock_tool_call = MagicMock()
        mock_tool_call.function.name = "sample_substrate"
        mock_tool_call.function.arguments = '{"region": "Lora"}'

        mock_message.tool_calls = [mock_tool_call]
        mock_response.choices = [MagicMock(message=mock_message)]

        action = agent._parse_openai_response(mock_response)

        assert action.name == "sample_substrate"
        assert action.params["region"] == "Lora"

    def test_parse_no_tool_call_returns_done(self):
        """Response without tool call returns done action."""
        agent = ConversationalLLMAgent(api="openai", api_key="test-key")

        mock_response = MagicMock()
        mock_message = MagicMock()
        mock_message.content = "Task completed."
        mock_message.tool_calls = None
        mock_response.choices = [MagicMock(message=mock_message)]

        action = agent._parse_openai_response(mock_response)

        assert action.name == "done"


class TestContextManagement:
    """Tests for conversation context management."""

    def test_messages_accumulate(self, simple_scenario, mock_observation):
        """Messages accumulate in conversation history."""
        agent = ConversationalLLMAgent(api_key="test-key", max_context_messages=100)
        session = AgentSession(simple_scenario)
        agent.start(session)

        # Add a user message manually (simulating decide flow)
        user_msg = agent._format_observation(mock_observation)
        agent._messages.append({"role": "user", "content": user_msg})

        assert len(agent._messages) == 1

    def test_context_summarized_when_too_long(self):
        """Old messages are summarized when context is too long."""
        agent = ConversationalLLMAgent(api_key="test-key", max_context_messages=10)

        # Add many messages
        for i in range(20):
            agent._messages.append({"role": "user", "content": f"Message {i}"})

        agent._summarize_context()

        # Should have been reduced
        assert len(agent._messages) < 20
        # First message should be summary
        assert "Summary" in agent._messages[0]["content"]


class TestEndCleanup:
    """Tests for end() cleanup."""

    def test_end_clears_messages(self, simple_scenario):
        """end() clears conversation history."""
        agent = ConversationalLLMAgent(api_key="test-key")
        session = AgentSession(simple_scenario)
        agent.start(session)

        agent._messages.append({"role": "user", "content": "test"})
        assert len(agent._messages) > 0

        from alienbio.agent import ExperimentResults
        results = ExperimentResults(
            scenario="test", seed=42, scores={}, trace=None, passed=True
        )
        agent.end(results)

        assert len(agent._messages) == 0
