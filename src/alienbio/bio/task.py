"""Task protocol: goals with scoring criteria for agent evaluation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from .agent_interface import AgentInterface


@dataclass
class TaskResult:
    """Result of evaluating an agent on a task."""

    score: float
    details: Dict[str, Any]


class Task(ABC):
    """Abstract base class for tasks.

    A task defines:
    - A setup (preparing the system)
    - A goal description (what the agent should do)
    - Scoring criteria (how to evaluate the result)
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Short identifier for the task."""

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of the goal."""

    @abstractmethod
    def score(self, interface: "AgentInterface", prediction: Any) -> TaskResult:
        """Score the agent's prediction or action.

        Args:
            interface: The agent interface (gives access to system)
            prediction: The agent's output

        Returns:
            TaskResult with score in [0, 1] and details dict
        """


class PredictTask(Task):
    """Predict the concentration of a molecule after N simulation steps.

    The agent must forecast what the concentration of a target molecule
    will be after the system runs for a specified number of steps.
    """

    def __init__(
        self,
        target_molecule: str,
        steps: int,
        *,
        tolerance: float = 0.1,
    ) -> None:
        self._target = target_molecule
        self._steps = steps
        self._tolerance = tolerance

    @property
    def name(self) -> str:
        return "predict"

    @property
    def description(self) -> str:
        return (
            f"Predict the concentration of {self._target!r} "
            f"after {self._steps} simulation steps"
        )

    @property
    def target_molecule(self) -> str:
        return self._target

    @property
    def steps(self) -> int:
        return self._steps

    def score(self, interface: "AgentInterface", prediction: float) -> TaskResult:
        """Score a concentration prediction.

        Runs the system forward, compares prediction to actual.
        Score = max(0, 1 - |predicted - actual| / max(actual, tolerance)).

        Args:
            interface: Agent interface wrapping the system
            prediction: Predicted concentration value

        Returns:
            TaskResult with score in [0, 1]
        """
        # Run forward from current state
        interface.system.run(self._steps)
        actual = interface.measure("concentration", molecule=self._target)

        # Score: relative error, clamped to [0, 1]
        denom = max(abs(actual), self._tolerance)
        error = abs(prediction - actual) / denom
        task_score = max(0.0, 1.0 - error)

        return TaskResult(
            score=task_score,
            details={
                "predicted": prediction,
                "actual": actual,
                "error": abs(prediction - actual),
                "steps": self._steps,
                "target": self._target,
            },
        )
