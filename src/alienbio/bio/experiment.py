"""Experiment protocol: combine world, task, and agent for evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from .agent_interface import AgentInterface
    from .task import Task, TaskResult


AgentFn = Callable[["AgentInterface", "Task"], Any]


@dataclass
class ExperimentResult:
    """Result of running an experiment."""

    task_name: str
    score: float
    prediction: Any
    details: Dict[str, Any]


def run_experiment(
    interface: "AgentInterface",
    task: "Task",
    agent: AgentFn,
) -> ExperimentResult:
    """Run an experiment: have the agent attempt the task.

    Args:
        interface: Agent-facing API for the system
        task: The task to evaluate
        agent: A callable (interface, task) -> prediction

    Returns:
        ExperimentResult with score and details
    """
    prediction = agent(interface, task)
    result: TaskResult = task.score(interface, prediction)

    return ExperimentResult(
        task_name=task.name,
        score=result.score,
        prediction=prediction,
        details=result.details,
    )
