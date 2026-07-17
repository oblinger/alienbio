"""Core types for the agent interface.

This module defines the data types used in the agent-environment interaction loop:
- Action: represents an action or measurement the agent wants to take
- Observation: what the agent observes about the environment
- ActionResult: a kind of Observation with action feedback (subclass)
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
class Constitution:
    """Explicit agent-facing objectives, prohibitions, and priorities.

    Declared at the scenario level (scenario["constitution"]) and surfaced
    to the agent verbatim on every observation. The content is opaque text
    the framework does not interpret.

    Attributes:
        objectives: What the agent should try to achieve
        prohibitions: What the agent must not do
        priorities: Priority ordering (highest priority first)
    """
    objectives: list[str] = field(default_factory=list)
    prohibitions: list[str] = field(default_factory=list)
    priorities: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        """Render as plain text (e.g. for embedding in an agent prompt)."""
        sections = []
        if self.objectives:
            sections.append("Objectives:\n" + "\n".join(f"- {o}" for o in self.objectives))
        if self.prohibitions:
            sections.append("Prohibitions:\n" + "\n".join(f"- {p}" for p in self.prohibitions))
        if self.priorities:
            sections.append("Priorities (highest first):\n" + "\n".join(
                f"{i + 1}. {p}" for i, p in enumerate(self.priorities)
            ))
        return "\n\n".join(sections)


def coerce_constitution(spec: Any) -> "str | Constitution":
    """Coerce a scenario-level constitution spec to its observation form.

    Strings (legacy free-form constitutions) and Constitution instances pass
    through verbatim; dicts with objectives/prohibitions/priorities keys are
    converted to a Constitution; None/absent becomes the empty string.

    Raises:
        ValueError: If a dict spec contains unknown keys
        TypeError: If the spec is not None, str, dict, or Constitution
    """
    if spec is None:
        return ""
    if isinstance(spec, (str, Constitution)):
        return spec
    if isinstance(spec, dict):
        unknown = set(spec) - {"objectives", "prohibitions", "priorities"}
        if unknown:
            raise ValueError(f"Unknown constitution keys: {sorted(unknown)}")
        return Constitution(
            objectives=list(spec.get("objectives", [])),
            prohibitions=list(spec.get("prohibitions", [])),
            priorities=list(spec.get("priorities", [])),
        )
    raise TypeError(f"Invalid constitution spec type: {type(spec).__name__}")


@dataclass
class Observation:
    """What the agent observes about the environment.

    The observation provides the agent with all information needed to decide
    on the next action. This is the base class for all agent perceptions.

    Attributes:
        briefing: Scenario description/instructions for the agent
        constitution: Rules/constraints the agent should follow — either
            free-form text or a structured Constitution
        available_actions: Actions the agent can take (name -> info dict)
        available_measurements: Measurements available (name -> info dict)
        current_state: Observable state of the environment
        step: Current step number (0 at start)
        budget: Total budget allocated. Normally interface.budget; when the
            scenario sets the opaque "deliberation_budget" dial (M32.1 time
            pressure), that value overrides interface.budget as the effective
            budget surfaced here and enforced by the session.
        spent: Budget spent so far
        remaining: Budget remaining (budget - spent)
        stakes: Opaque scenario-level "stakes" dial (magnitude of
            consequences). Set independently of reversibility. None if unset.
        reversibility: Opaque scenario-level "reversibility" dial (whether key
            effects/actions can be undone). Set independently of stakes. None
            if unset. (Per-action reversibility is carried on each action spec
            in available_actions via an optional "reversible" flag.)
        observation_noise: Opaque scenario-level "observation noise" dial
            (M28.3). Non-negative noise level applied to the numeric readings
            in current_state / measurement data — the observed values, never
            the ground-truth world state. None if unset (readings pass through
            untouched).
        observability: Opaque scenario-level "observability" dial (M28.2) — the
            fraction of world-state entries visible to the agent. This is the
            fraction that was applied to filter current_state; None when unset
            (in which case current_state is unfiltered / byte-identical to the
            no-dial case). The ground-truth world state is untouched; only what
            the agent observes is filtered.
    """
    briefing: str
    constitution: "str | Constitution"
    available_actions: dict[str, Any]
    available_measurements: dict[str, Any]
    current_state: dict[str, Any]
    step: int
    budget: float
    spent: float
    remaining: float
    stakes: Any = None
    reversibility: Any = None
    observation_noise: Any = None
    observability: Any = None
    _is_initial: bool = field(default=True, repr=False)

    def is_initial(self) -> bool:
        """Return True if this is the first observation (before any actions)."""
        return self._is_initial


@dataclass
class ActionResult(Observation):
    """Result of executing an action - a kind of Observation.

    ActionResult is a subclass of Observation because it represents what the
    agent perceives after taking an action. It includes all the standard
    observation fields (world state, budget, etc.) plus action-specific feedback.

    In a simple turn-based world, ActionResult arrives immediately after the
    action. In a more complex async world, there may be other observations
    between action initiation and this result.

    Attributes (in addition to Observation fields):
        action_name: Name of the action this result is for
        success: Whether the action executed successfully
        error: Error message if success is False
        data: Result data (especially for measurements)
        cost: Cost charged for this action
        initiated: Simulation time when action started
        completed: Simulation time when action finished
        completion_time: Duration of the action
    """
    action_name: str = ""
    success: bool = True
    error: Optional[str] = None
    data: Optional[Any] = None
    cost: float = 0.0
    initiated: Optional[float] = None
    completed: Optional[float] = None
    completion_time: Optional[float] = None


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
