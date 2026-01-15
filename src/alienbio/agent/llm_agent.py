"""ConversationalLLMAgent: LLM-based agent using tool/function calling.

This agent uses LLM APIs (Anthropic Claude, OpenAI) to decide on actions
based on the scenario briefing, constitution, and available tools.

Example usage:
    from alienbio.agent import ConversationalLLMAgent, run_experiment

    agent = ConversationalLLMAgent(
        model="claude-sonnet-4-20250514",
        api="anthropic",
    )
    results = run_experiment(scenario, agent, seed=42)
"""

from typing import Any, Optional, TYPE_CHECKING
import json

if TYPE_CHECKING:
    from .types import Action, Observation, ExperimentResults
    from .session import AgentSession


class ConversationalLLMAgent:
    """Agent that uses LLM APIs with tool/function calling.

    Supports Anthropic Claude and OpenAI APIs. Converts scenario
    actions/measurements to tool definitions and parses LLM responses.

    Attributes:
        model: Model identifier (e.g., "claude-sonnet-4-20250514")
        api: API provider ("anthropic" or "openai")
        api_key: API key (uses config if not provided)
    """

    def __init__(
        self,
        model: Optional[str] = None,
        api: str = "anthropic",
        api_key: Optional[str] = None,
        max_context_messages: int = 50,
    ) -> None:
        """Initialize the LLM agent.

        Args:
            model: Model to use (defaults to provider's default)
            api: API provider ("anthropic" or "openai")
            api_key: API key (uses config/env if not provided)
            max_context_messages: Max messages before summarizing (default 50)
        """
        from alienbio import config

        self._api = api
        self._api_key = api_key or config.get_api_key(api)
        self._model = model or config.get_default_model(api)
        self._max_context_messages = max_context_messages

        self._session: Optional["AgentSession"] = None
        self._messages: list[dict[str, Any]] = []
        self._tools: list[dict[str, Any]] = []
        self._system_prompt: str = ""

        # API clients (lazy initialized)
        self._anthropic_client: Any = None
        self._openai_client: Any = None

    def start(self, session: "AgentSession") -> None:
        """Initialize conversation with scenario context.

        Sets up the system prompt from briefing and constitution,
        and converts interface actions/measurements to tool definitions.
        """
        self._session = session
        self._messages = []

        # Build system prompt
        scenario = session.scenario
        briefing = scenario.get("briefing", "")
        constitution = scenario.get("constitution", "")

        self._system_prompt = self._build_system_prompt(briefing, constitution)

        # Build tool definitions from interface
        interface = scenario.get("interface", {})
        self._tools = self._build_tools(interface)

    def decide(self, observation: "Observation") -> "Action":
        """Get action from LLM based on current observation.

        Sends the observation to the LLM and parses the tool call response.
        """
        from .types import Action

        # Build user message from observation
        user_message = self._format_observation(observation)
        self._messages.append({"role": "user", "content": user_message})

        # Manage context length
        if len(self._messages) > self._max_context_messages:
            self._summarize_context()

        # Call LLM API
        try:
            if self._api == "anthropic":
                response = self._call_anthropic()
            elif self._api == "openai":
                response = self._call_openai()
            else:
                raise ValueError(f"Unsupported API: {self._api}")

            # Parse tool call from response
            action = self._parse_response(response)

            # Add assistant message to history
            self._messages.append({"role": "assistant", "content": response})

            return action

        except Exception as e:
            # On error, return done action
            print(f"LLM API error: {e}")
            return Action(name="done", params={}, reasoning=f"API error: {e}")

    def end(self, results: "ExperimentResults") -> None:
        """Clean up after experiment."""
        self._messages = []

    def observe_result(self, action_result: "Observation") -> None:
        """Add action result to conversation history.

        Called by the session after each action to keep the LLM
        informed of action outcomes.
        """
        result_msg = self._format_action_result(action_result)
        self._messages.append({"role": "user", "content": result_msg})

    def _build_system_prompt(self, briefing: str, constitution: str) -> str:
        """Build system prompt from scenario briefing and constitution."""
        parts = [
            "You are an AI agent participating in a biology simulation experiment.",
            "",
            "## Briefing",
            briefing or "(No briefing provided)",
            "",
            "## Constitution",
            constitution or "(No constitution provided)",
            "",
            "## Instructions",
            "- Use the available tools to interact with the simulation",
            "- Observe the results of your actions to learn about the system",
            "- Work towards understanding and achieving the experiment goals",
            "- Call the 'done' tool when you have completed your task",
            "",
            "Always explain your reasoning before taking an action.",
        ]
        return "\n".join(parts)

    def _build_tools(self, interface: dict[str, Any]) -> list[dict[str, Any]]:
        """Convert interface actions/measurements to tool definitions."""
        tools = []

        # Add actions
        for name, info in interface.get("actions", {}).items():
            tool = self._action_to_tool(name, info, is_action=True)
            tools.append(tool)

        # Add measurements
        for name, info in interface.get("measurements", {}).items():
            tool = self._action_to_tool(name, info, is_action=False)
            tools.append(tool)

        # Add 'done' tool
        tools.append({
            "name": "done",
            "description": "End the experiment. Call this when you have completed your task or want to stop.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "Reason for ending the experiment"
                    }
                },
                "required": []
            }
        })

        return tools

    def _action_to_tool(
        self,
        name: str,
        info: dict[str, Any],
        is_action: bool
    ) -> dict[str, Any]:
        """Convert a single action/measurement to tool definition."""
        description = info.get("description", f"{'Action' if is_action else 'Measurement'}: {name}")
        cost = info.get("cost", 1.0 if is_action else 0)

        # Build description with cost info
        full_description = f"{description} (cost: {cost})"

        # Build parameters schema
        params = info.get("params", {})
        properties = {}
        required = []

        for param_name, param_type in params.items():
            if isinstance(param_type, str):
                # Simple type hint like "str", "float", "int"
                json_type = {
                    "str": "string",
                    "string": "string",
                    "float": "number",
                    "int": "integer",
                    "integer": "integer",
                    "bool": "boolean",
                    "boolean": "boolean",
                }.get(param_type.lower(), "string")
                properties[param_name] = {"type": json_type}
            elif isinstance(param_type, dict):
                # Complex type definition
                properties[param_name] = param_type
            else:
                properties[param_name] = {"type": "string"}

            required.append(param_name)

        return {
            "name": name,
            "description": full_description,
            "input_schema": {
                "type": "object",
                "properties": properties,
                "required": required
            }
        }

    def _format_observation(self, observation: "Observation") -> str:
        """Format observation as message content for LLM."""
        parts = [
            f"## Current State (Step {observation.step})",
            "",
            f"Budget: {observation.spent:.1f} / {observation.budget:.1f} (remaining: {observation.remaining:.1f})",
            "",
            "### Observable State:",
            json.dumps(observation.current_state, indent=2),
        ]

        if observation.is_initial():
            parts.insert(0, "This is the initial observation. Please analyze the situation and decide on your first action.")
            parts.insert(1, "")

        return "\n".join(parts)

    def _format_action_result(self, result: "Observation") -> str:
        """Format action result as message content."""
        from .types import ActionResult

        if isinstance(result, ActionResult):
            parts = [
                f"## Action Result: {result.action_name}",
                f"Success: {result.success}",
            ]
            if result.error:
                parts.append(f"Error: {result.error}")
            if result.data is not None:
                parts.append(f"Data: {json.dumps(result.data, indent=2)}")
            parts.append(f"Cost: {result.cost}")
            return "\n".join(parts)
        else:
            return "Action completed. See current state for results."

    def _call_anthropic(self) -> Any:
        """Call Anthropic Claude API."""
        if self._anthropic_client is None:
            import anthropic
            self._anthropic_client = anthropic.Anthropic(api_key=self._api_key)

        # Convert tools to Anthropic format
        anthropic_tools = []
        for tool in self._tools:
            anthropic_tools.append({
                "name": tool["name"],
                "description": tool["description"],
                "input_schema": tool["input_schema"]
            })

        response = self._anthropic_client.messages.create(
            model=self._model,
            max_tokens=4096,
            system=self._system_prompt,
            tools=anthropic_tools,
            messages=self._convert_messages_for_anthropic(),
        )

        return response

    def _call_openai(self) -> Any:
        """Call OpenAI API."""
        if self._openai_client is None:
            import openai
            self._openai_client = openai.OpenAI(api_key=self._api_key)

        # Convert tools to OpenAI format
        openai_tools = []
        for tool in self._tools:
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["input_schema"]
                }
            })

        # Build messages with system prompt
        messages = [{"role": "system", "content": self._system_prompt}]
        messages.extend(self._convert_messages_for_openai())

        response = self._openai_client.chat.completions.create(
            model=self._model,
            messages=messages,
            tools=openai_tools if openai_tools else None,
        )

        return response

    def _convert_messages_for_anthropic(self) -> list[dict[str, Any]]:
        """Convert internal messages to Anthropic format."""
        # Anthropic expects alternating user/assistant messages
        result = []
        for msg in self._messages:
            if msg["role"] in ("user", "assistant"):
                result.append(msg)
        return result

    def _convert_messages_for_openai(self) -> list[dict[str, Any]]:
        """Convert internal messages to OpenAI format."""
        return self._messages

    def _parse_response(self, response: Any) -> "Action":
        """Parse LLM response to extract action."""
        from .types import Action

        if self._api == "anthropic":
            return self._parse_anthropic_response(response)
        elif self._api == "openai":
            return self._parse_openai_response(response)
        else:
            return Action(name="done", params={})

    def _parse_anthropic_response(self, response: Any) -> "Action":
        """Parse Anthropic Claude response for tool calls."""
        from .types import Action

        # Look for tool_use blocks in response
        for block in response.content:
            if block.type == "tool_use":
                name = block.name
                params = block.input or {}
                # Get reasoning from text blocks
                reasoning = ""
                for b in response.content:
                    if b.type == "text":
                        reasoning = b.text
                        break
                return Action(name=name, params=params, reasoning=reasoning)

        # No tool call - default to done
        text = ""
        for block in response.content:
            if block.type == "text":
                text = block.text
                break
        return Action(name="done", params={}, reasoning=text)

    def _parse_openai_response(self, response: Any) -> "Action":
        """Parse OpenAI response for tool calls."""
        from .types import Action

        message = response.choices[0].message

        # Check for tool calls
        if message.tool_calls:
            tool_call = message.tool_calls[0]
            name = tool_call.function.name
            params = json.loads(tool_call.function.arguments)
            reasoning = message.content or ""
            return Action(name=name, params=params, reasoning=reasoning)

        # No tool call - extract text and default to done
        reasoning = message.content or ""
        return Action(name="done", params={}, reasoning=reasoning)

    def _summarize_context(self) -> None:
        """Summarize old messages when context gets too long.

        Keeps recent messages and summarizes older ones into a single
        summary message.
        """
        if len(self._messages) <= self._max_context_messages // 2:
            return

        # Keep recent messages, summarize old ones
        keep_count = self._max_context_messages // 4
        old_messages = self._messages[:-keep_count]
        recent_messages = self._messages[-keep_count:]

        # Create summary
        summary = f"[Summary of {len(old_messages)} previous messages: The agent has been interacting with the simulation, taking actions and observing results.]"

        self._messages = [
            {"role": "user", "content": summary}
        ] + recent_messages
