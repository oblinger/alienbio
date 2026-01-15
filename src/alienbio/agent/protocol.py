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
