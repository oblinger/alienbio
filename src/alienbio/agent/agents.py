"""Agent protocol and built-in agent implementations.

The Agent protocol defines the interface that all agents must implement:
- start(session): called when experiment begins
- decide(observation): called each step to get next action
- end(results): called when experiment ends
"""

from typing import Protocol, Optional, Any, TYPE_CHECKING
import random

if TYPE_CHECKING:
    from .types import Action, Observation, ExperimentResults
    from .session import AgentSession


class Agent(Protocol):
    """Protocol for agents that interact with experiments.

    Agents implement the decision-making logic for experiments.
    They receive observations and return actions.
    """

    def start(self, session: "AgentSession") -> None:
        """Called when the experiment starts.

        Args:
            session: The AgentSession for this experiment
        """
        ...

    def decide(self, observation: "Observation") -> "Action":
        """Decide on the next action given an observation.

        Args:
            observation: Current observation

        Returns:
            The action to take
        """
        ...

    def end(self, results: "ExperimentResults") -> None:
        """Called when the experiment ends.

        Args:
            results: Final experiment results
        """
        ...


class RandomAgent:
    """Agent that takes random actions.

    Useful for baseline testing and exploring action spaces.
    With a small probability, will choose to end the experiment.
    """

    def __init__(
        self,
        seed: Optional[int] = None,
        done_probability: float = 0.1
    ) -> None:
        """Initialize with optional random seed.

        Args:
            seed: Random seed for reproducibility
            done_probability: Probability of choosing 'done' each step (default 0.1)
        """
        self._seed = seed
        self._rng = random.Random(seed)
        self._session: Optional["AgentSession"] = None
        self._done_probability = done_probability
        self._interaction_count = 0
        self._max_interactions = 100  # Safety limit

    def start(self, session: "AgentSession") -> None:
        """Store session reference."""
        self._session = session
        self._interaction_count = 0

    def decide(self, observation: "Observation") -> "Action":
        """Choose a random action from available options."""
        from .types import Action

        self._interaction_count += 1

        # Safety limit to prevent infinite loops
        if self._interaction_count >= self._max_interactions:
            return Action(name="done", params={})

        # With small probability, choose to end
        if self._rng.random() < self._done_probability:
            return Action(name="done", params={})

        # Collect all available actions/measurements
        options: list[str] = []
        options.extend(observation.available_actions.keys())
        options.extend(observation.available_measurements.keys())

        if not options:
            return Action(name="done", params={})

        # Pick random action
        name = self._rng.choice(options)

        # For now, use empty params (real impl would generate valid params)
        return Action(name=name, params={})

    def end(self, results: "ExperimentResults") -> None:
        """No cleanup needed."""
        pass


class ScriptedAgent:
    """Agent that follows a predefined sequence of actions.

    Useful for testing specific scenarios.
    """

    def __init__(self, actions: list["Action"]) -> None:
        """Initialize with action sequence.

        Args:
            actions: List of actions to execute in order
        """
        self._actions = actions
        self._index = 0
        self._session: Optional["AgentSession"] = None

    def start(self, session: "AgentSession") -> None:
        """Store session reference."""
        self._session = session

    def decide(self, observation: "Observation") -> "Action":
        """Return next action in sequence, or 'done' if exhausted."""
        from .types import Action

        if self._index < len(self._actions):
            action = self._actions[self._index]
            self._index += 1
            return action
        else:
            return Action(name="done", params={})

    def end(self, results: "ExperimentResults") -> None:
        """No cleanup needed."""
        pass


class OracleAgent:
    """Agent with access to ground truth.

    Used for testing optimal/cheating baselines.
    """

    def __init__(self) -> None:
        """Initialize oracle agent."""
        self._session: Optional["AgentSession"] = None
        self._ground_truth: Optional[dict[str, Any]] = None

    @property
    def ground_truth(self) -> Optional[dict[str, Any]]:
        """Return the ground truth if available."""
        return self._ground_truth

    def start(self, session: "AgentSession") -> None:
        """Extract ground truth from scenario."""
        self._session = session
        self._ground_truth = session.scenario.get("_ground_truth_")

    def decide(self, observation: "Observation") -> "Action":
        """Make decision using ground truth.

        Default implementation just returns 'done'.
        Subclasses can implement more sophisticated logic.
        """
        from .types import Action

        # Default: just return done
        # Real oracle would use ground_truth to make optimal decisions
        return Action(name="done", params={})

    def end(self, results: "ExperimentResults") -> None:
        """No cleanup needed."""
        pass


class HumanAgent:
    """Interactive agent that prompts the user for actions via CLI.

    Displays the current observation and available actions, then
    accepts commands from the user. Useful for manual exploration
    and debugging scenarios.

    Commands:
        <action_name> [param=value ...]  - Execute an action
        ? or help                        - Show available actions
        state                            - Show current state
        budget                           - Show budget info
        done                             - End the experiment
    """

    def __init__(self, prompt: str = "action> ") -> None:
        """Initialize human agent.

        Args:
            prompt: The prompt string to display when asking for input
        """
        self._prompt = prompt
        self._session: Optional["AgentSession"] = None
        self._show_state_on_start = True

    def start(self, session: "AgentSession") -> None:
        """Display scenario briefing and initial state."""
        self._session = session
        print("\n" + "=" * 60)
        print("SCENARIO: " + session.scenario.get("name", "Unknown"))
        print("=" * 60)
        print("\nBRIEFING:")
        print(session.scenario.get("briefing", "(no briefing)"))
        print("\nCONSTITUTION:")
        print(session.scenario.get("constitution", "(no constitution)"))
        print("=" * 60 + "\n")

    def decide(self, observation: "Observation") -> "Action":
        """Prompt user for action and parse response."""
        from .types import Action

        # Show state on first observation or if requested
        if observation.is_initial() and self._show_state_on_start:
            self._display_observation(observation)

        while True:
            try:
                user_input = input(self._prompt).strip()
            except (EOFError, KeyboardInterrupt):
                print("\n[Interrupted - ending experiment]")
                return Action(name="done", params={})

            if not user_input:
                continue

            # Handle special commands
            lower_input = user_input.lower()
            if lower_input in ("?", "help"):
                self._show_help(observation)
                continue
            elif lower_input == "state":
                self._display_state(observation)
                continue
            elif lower_input == "budget":
                self._display_budget(observation)
                continue
            elif lower_input == "done":
                return Action(name="done", params={})

            # Parse action command
            action = self._parse_action(user_input, observation)
            if action is not None:
                return action

            print(f"Unknown command: {user_input}")
            print("Type '?' for help")

    def end(self, results: "ExperimentResults") -> None:
        """Display final results."""
        print("\n" + "=" * 60)
        print("EXPERIMENT COMPLETE")
        print("=" * 60)
        print(f"Status: {results.status}")
        print(f"Passed: {results.passed}")
        print("\nScores:")
        for name, value in results.scores.items():
            print(f"  {name}: {value:.3f}")
        print("=" * 60 + "\n")

    def _display_observation(self, observation: "Observation") -> None:
        """Display full observation to user."""
        print("\n--- Current Observation ---")
        print(f"Step: {observation.step}")
        self._display_budget(observation)
        self._display_state(observation)
        self._show_help(observation)

    def _display_state(self, observation: "Observation") -> None:
        """Display current state."""
        print("\nState:")
        state = observation.current_state
        if isinstance(state, dict):
            for key, value in state.items():
                if isinstance(value, dict):
                    print(f"  {key}:")
                    for k, v in value.items():
                        print(f"    {k}: {v}")
                else:
                    print(f"  {key}: {value}")
        else:
            print(f"  {state}")

    def _display_budget(self, observation: "Observation") -> None:
        """Display budget information."""
        print(f"\nBudget: {observation.spent:.1f} / {observation.budget:.1f} "
              f"(remaining: {observation.remaining:.1f})")

    def _show_help(self, observation: "Observation") -> None:
        """Show available actions and measurements."""
        print("\nAvailable Actions:")
        for name, info in observation.available_actions.items():
            desc = info.get("description", "") if isinstance(info, dict) else ""
            cost = info.get("cost", 1.0) if isinstance(info, dict) else 1.0
            print(f"  {name} (cost: {cost}) - {desc}")

        print("\nAvailable Measurements:")
        for name, info in observation.available_measurements.items():
            desc = info.get("description", "") if isinstance(info, dict) else ""
            cost = info.get("cost", 0) if isinstance(info, dict) else 0
            print(f"  {name} (cost: {cost}) - {desc}")

        print("\nCommands: ?, help, state, budget, done")
        print("Usage: <action_name> [param=value ...]")

    def _parse_action(
        self,
        user_input: str,
        observation: "Observation"
    ) -> Optional["Action"]:
        """Parse user input into an Action.

        Format: action_name [param1=value1 param2=value2 ...]

        Returns:
            Action if parsing succeeds, None otherwise
        """
        from .types import Action

        parts = user_input.split()
        if not parts:
            return None

        name = parts[0]

        # Check if action/measurement exists
        valid_names = (
            list(observation.available_actions.keys()) +
            list(observation.available_measurements.keys())
        )
        if name not in valid_names:
            return None

        # Parse parameters
        params: dict[str, Any] = {}
        for part in parts[1:]:
            if "=" in part:
                key, value = part.split("=", 1)
                # Try to parse as number
                try:
                    if "." in value:
                        params[key] = float(value)
                    else:
                        params[key] = int(value)
                except ValueError:
                    params[key] = value
            else:
                print(f"Warning: ignoring parameter without '=': {part}")

        return Action(name=name, params=params)
