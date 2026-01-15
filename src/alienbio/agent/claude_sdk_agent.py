"""ClaudeAgentSDKBinding: Native Claude Agent SDK integration.

Uses the Claude Agent SDK for native tool handling and agent-aware
conversation management.

Example usage:
    from alienbio.agent import ClaudeAgentSDKBinding, run_experiment

    agent = ClaudeAgentSDKBinding(
        model="claude-sonnet-4-20250514",
    )
    results = run_experiment(scenario, agent, seed=42)

Requires: pip install claude-agent-sdk
"""

from typing import Any, Optional, TYPE_CHECKING
import json
import asyncio

if TYPE_CHECKING:
    from .types import Action, Observation, ExperimentResults
    from .session import AgentSession


class ClaudeAgentSDKBinding:
    """Agent that uses the native Claude Agent SDK.

    Uses the Claude Agent SDK for tool handling and conversation management,
    providing native integration with Claude's agent capabilities.

    Attributes:
        model: Model identifier (e.g., "claude-sonnet-4-20250514")
        api_key: API key (uses ANTHROPIC_API_KEY env var if not provided)
    """

    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> None:
        """Initialize the Claude Agent SDK binding.

        Args:
            model: Model to use (defaults to claude-sonnet-4-20250514)
            api_key: API key (uses ANTHROPIC_API_KEY env var if not provided)
        """
        self._model = model or "claude-sonnet-4-20250514"
        self._api_key = api_key

        self._session: Optional["AgentSession"] = None
        self._client: Any = None
        self._mcp_server: Any = None
        self._tool_names: list[str] = []
        self._pending_action: Optional["Action"] = None
        self._system_prompt: str = ""

    def start(self, session: "AgentSession") -> None:
        """Initialize the agent with scenario context.

        Sets up the Claude Agent SDK client with tools from the interface.
        """
        self._session = session
        self._pending_action = None

        # Build system prompt
        scenario = session.scenario
        briefing = scenario.get("briefing", "")
        constitution = scenario.get("constitution", "")
        self._system_prompt = self._build_system_prompt(briefing, constitution)

        # Build MCP server with tools from interface
        interface = scenario.get("interface", {})
        self._mcp_server, self._tool_names = self._build_mcp_server(interface)

    def decide(self, observation: "Observation") -> "Action":
        """Get action from Claude Agent SDK based on current observation.

        Uses asyncio to run the async SDK operations synchronously.
        """
        from .types import Action

        # Format the observation as a prompt
        prompt = self._format_observation(observation)

        try:
            # Run the async query synchronously
            try:
                loop = asyncio.get_running_loop()
                # If we're already in an async context, we can't use run()
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, self._query_agent(prompt))
                    action = future.result()
            except RuntimeError:
                # No event loop running, create one
                action = asyncio.run(self._query_agent(prompt))
            return action
        except Exception as e:
            print(f"Claude Agent SDK error: {e}")
            return Action(name="done", params={}, reasoning=f"SDK error: {e}")

    async def _query_agent(self, prompt: str) -> "Action":
        """Query the Claude Agent SDK asynchronously."""
        from .types import Action

        try:
            from claude_agent_sdk import (
                ClaudeSDKClient,
                ClaudeAgentOptions,
                AssistantMessage,
                ToolUseBlock,
                TextBlock,
            )
        except ImportError:
            return Action(
                name="done",
                params={},
                reasoning="claude-agent-sdk not installed. Run: pip install claude-agent-sdk"
            )

        # Build options with MCP server
        options = ClaudeAgentOptions(
            model=self._model,
            system_prompt=self._system_prompt,
            mcp_servers={"alienbio": self._mcp_server} if self._mcp_server else {},
            allowed_tools=self._tool_names,
            max_turns=1,  # Single turn for each decide() call
        )

        # Set API key in environment if provided
        if self._api_key:
            import os
            os.environ["ANTHROPIC_API_KEY"] = self._api_key

        action_name = "done"
        action_params: dict[str, Any] = {}
        reasoning = ""

        async with ClaudeSDKClient(options=options) as client:
            await client.query(prompt)

            async for message in client.receive_response():
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, ToolUseBlock):
                            # Extract action from tool use
                            tool_name = block.name
                            # MCP tools are prefixed with mcp__servername__
                            if tool_name.startswith("mcp__alienbio__"):
                                action_name = tool_name.replace("mcp__alienbio__", "")
                            else:
                                action_name = tool_name
                            action_params = block.input or {}
                        elif isinstance(block, TextBlock):
                            reasoning = block.text

        return Action(name=action_name, params=action_params, reasoning=reasoning)

    def end(self, results: "ExperimentResults") -> None:
        """Clean up after experiment."""
        self._session = None
        self._client = None
        self._mcp_server = None
        self._tool_names = []

    def observe_result(self, action_result: "Observation") -> None:
        """Note: Claude Agent SDK manages its own conversation history."""
        pass

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

    def _build_mcp_server(
        self,
        interface: dict[str, Any]
    ) -> tuple[Any, list[str]]:
        """Build MCP server with tools from interface."""
        try:
            from claude_agent_sdk import tool, create_sdk_mcp_server
        except ImportError:
            return None, []

        tools = []
        tool_names = []

        # Create tools for actions
        for name, info in interface.get("actions", {}).items():
            sdk_tool = self._create_sdk_tool(name, info, is_action=True)
            if sdk_tool:
                tools.append(sdk_tool)
                tool_names.append(f"mcp__alienbio__{name}")

        # Create tools for measurements
        for name, info in interface.get("measurements", {}).items():
            sdk_tool = self._create_sdk_tool(name, info, is_action=False)
            if sdk_tool:
                tools.append(sdk_tool)
                tool_names.append(f"mcp__alienbio__{name}")

        # Add 'done' tool
        @tool("done", "End the experiment. Call when you have completed your task.", {"reason": str})
        async def done_tool(args: dict[str, Any]) -> dict[str, Any]:
            return {
                "content": [{
                    "type": "text",
                    "text": f"Experiment ended: {args.get('reason', 'No reason provided')}"
                }]
            }
        tools.append(done_tool)
        tool_names.append("mcp__alienbio__done")

        # Create MCP server
        mcp_server = create_sdk_mcp_server(
            name="alienbio",
            version="1.0.0",
            tools=tools
        )

        return mcp_server, tool_names

    def _create_sdk_tool(
        self,
        name: str,
        info: dict[str, Any],
        is_action: bool
    ) -> Any:
        """Create an SDK tool from action/measurement definition."""
        try:
            from claude_agent_sdk import tool
        except ImportError:
            return None

        description = info.get("description", f"{'Action' if is_action else 'Measurement'}: {name}")
        cost = info.get("cost", 1.0 if is_action else 0)
        full_description = f"{description} (cost: {cost})"

        # Build input schema from params
        params = info.get("params", {})
        input_schema: dict[str, Any] = {}

        for param_name, param_type in params.items():
            if isinstance(param_type, str):
                # Map string type hints to Python types
                type_map = {
                    "str": str,
                    "string": str,
                    "float": float,
                    "int": int,
                    "integer": int,
                    "bool": bool,
                    "boolean": bool,
                }
                input_schema[param_name] = type_map.get(param_type.lower(), str)
            else:
                input_schema[param_name] = str

        # Create the tool handler that stores the action for later execution
        session = self._session

        async def tool_handler(args: dict[str, Any]) -> dict[str, Any]:
            # Store the action to be executed by the session
            self._pending_action = {
                "name": name,
                "params": args
            }
            return {
                "content": [{
                    "type": "text",
                    "text": f"Action '{name}' will be executed with params: {json.dumps(args)}"
                }]
            }

        # Use the @tool decorator
        decorated = tool(name, full_description, input_schema)(tool_handler)
        return decorated

    def _format_observation(self, observation: "Observation") -> str:
        """Format observation as prompt for Claude Agent SDK."""
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
