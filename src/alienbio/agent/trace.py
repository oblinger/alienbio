"""Trace for recording agent-centric action→observation history.

The Trace is an agent-centric record of what happened during an experiment.
It captures the sequence of (action, observation) pairs that represent the
agent's experience of interacting with the environment.

This differs from the Timeline which is system-centric and includes all
events with precise timestamps. The Trace focuses on what matters for
understanding and scoring agent behavior.
"""

from dataclasses import dataclass, field
from typing import Any, Iterator, Optional

from .types import Action, Observation


@dataclass
class ActionObservationRecord:
    """A single action→observation pair in the trace.

    Records what the agent did (action) and what it observed afterward
    (observation). This is the fundamental unit of the agent's experience.

    Attributes:
        action: The action the agent took
        observation: The observation received after the action
        step: The step number when this action was taken
        cumulative_cost: Total cost spent up to and including this action
    """
    action: Action
    observation: Observation
    step: int
    cumulative_cost: float


class Trace:
    """Agent-centric record of all actions and observations.

    The trace captures the sequence of action→observation pairs that
    represent the agent's experience. This is used for:
    - Scoring agent behavior
    - Analyzing agent strategy
    - Replaying agent decisions

    Note: The trace records the observation AFTER each action, not before.
    The initial observation (before any actions) is not in the trace but
    is available via the session.
    """

    def __init__(self) -> None:
        """Initialize an empty trace."""
        self._records: list[ActionObservationRecord] = []
        self._total_cost: float = 0.0

    def __len__(self) -> int:
        """Return the number of action→observation records."""
        return len(self._records)

    def __iter__(self) -> Iterator[ActionObservationRecord]:
        """Iterate over all records in order."""
        return iter(self._records)

    def __getitem__(self, index: int) -> ActionObservationRecord:
        """Get record by index."""
        return self._records[index]

    @property
    def records(self) -> list[ActionObservationRecord]:
        """Return all action→observation records."""
        return self._records

    @property
    def total_cost(self) -> float:
        """Return total cost of all actions in the trace."""
        return self._total_cost

    def append(
        self,
        action: Action,
        observation: Observation,
        step: int,
        cost: float
    ) -> None:
        """Add an action→observation pair to the trace.

        Args:
            action: The action that was taken
            observation: The observation received after the action
            step: The step number
            cost: Cost of this action
        """
        self._total_cost += cost
        record = ActionObservationRecord(
            action=action,
            observation=observation,
            step=step,
            cumulative_cost=self._total_cost
        )
        self._records.append(record)

    @property
    def actions(self) -> list[Action]:
        """Return list of all actions taken in order.

        This is a convenience property for analyzing agent behavior.
        """
        return [r.action for r in self._records]

    @property
    def final(self) -> Optional[dict[str, Any]]:
        """Return the final state from the last observation, or None if empty.

        This is a convenience property for scoring functions that need
        the final state of the experiment.
        """
        if not self._records:
            return None
        return self._records[-1].observation.current_state
