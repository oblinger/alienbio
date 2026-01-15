"""Core types for the agent interface.

This module defines the data types used in the agent-environment interaction loop:
- Action: represents an action or measurement the agent wants to take
- ActionResult: the result of executing an action
- Observation: what the agent observes about the environment
- ExperimentResults: final results of an experiment run
"""

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Action:
    """An action or measurement the agent wants to take.

    Actions modify the environment state; measurements observe without modifying.
    The kind is inferred from the scenario interface if not specified.

    Attributes:
        name: Name of the action (must match scenario interface)
        params: Parameters for the action
        kind: "action" or "measurement" (inferred if not provided)
        wait: Whether to wait for completion (uses scenario default if not provided)
        reasoning: Optional explanation of why this action was chosen
    """
    name: str
    params: dict[str, Any] = field(default_factory=dict)
    kind: Optional[str] = None  # "action" or "measurement", inferred if None
    wait: Optional[bool] = None  # Uses scenario default_wait if None
    reasoning: Optional[str] = None


@dataclass
class ActionResult:
    """Result of executing an action.

    Attributes:
        success: Whether the action executed successfully
        error: Error message if success is False
        data: Result data (especially for measurements)
        cost: Cost charged for this action
        new_state: Observable state after action (if available)
        initiated: Simulation time when action started
        completed: Simulation time when action finished
        completion_time: Duration of the action
    """
    success: bool
    error: Optional[str] = None
    data: Optional[Any] = None
    cost: float = 0.0
    new_state: Optional[dict[str, Any]] = None
    initiated: Optional[float] = None
    completed: Optional[float] = None
    completion_time: Optional[float] = None


@dataclass
class Observation:
    """What the agent observes about the environment.

    The observation provides the agent with all information needed to decide
    on the next action.

    Attributes:
        briefing: Scenario description/instructions for the agent
        constitution: Rules/constraints the agent should follow
        available_actions: Actions the agent can take (name -> info dict)
        available_measurements: Measurements available (name -> info dict)
        current_state: Observable state of the environment
        step: Current step number (0 at start)
        budget: Total budget allocated
        spent: Budget spent so far
        remaining: Budget remaining (budget - spent)
    """
    briefing: str
    constitution: str
    available_actions: dict[str, Any]
    available_measurements: dict[str, Any]
    current_state: dict[str, Any]
    step: int
    budget: float
    spent: float
    remaining: float
    _is_initial: bool = field(default=True, repr=False)

    def is_initial(self) -> bool:
        """Return True if this is the first observation (before any actions)."""
        return self._is_initial


@dataclass
class ExperimentResults:
    """Results of a completed experiment run.

    Attributes:
        scenario: Name of the scenario that was run
        seed: Random seed used (for reproducibility)
        scores: Dictionary of score name -> value
        trace: The Trace recording all actions taken
        passed: Whether the experiment passed (score >= passing_score)
        status: "completed" or "incomplete"
        incomplete_reason: Reason if status is "incomplete"
    """
    scenario: str
    seed: Optional[int]
    scores: dict[str, float]
    trace: Any  # Trace object (avoid circular import)
    passed: bool
    status: str = "completed"
    incomplete_reason: Optional[str] = None
