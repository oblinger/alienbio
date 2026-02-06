"""Test harness: batch experiments with aggregation and export."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, TYPE_CHECKING

from .experiment import ExperimentResult, run_experiment

if TYPE_CHECKING:
    from .agent_interface import AgentInterface
    from .task import Task

AgentFn = Callable[["AgentInterface", "Task"], Any]


@dataclass
class TestSuite:
    """A batch of experiments to run.

    Pairs tasks with agent interfaces for batch execution.
    """

    name: str
    experiments: List[_ExperimentSpec] = field(default_factory=list)

    def add(self, interface: "AgentInterface", task: "Task") -> None:
        """Add an experiment to the suite."""
        self.experiments.append(_ExperimentSpec(interface, task))

    @property
    def count(self) -> int:
        return len(self.experiments)


@dataclass
class _ExperimentSpec:
    """Internal: pairs an interface with a task."""

    interface: "AgentInterface"
    task: "Task"


@dataclass
class TestResults:
    """Aggregated results from running a test suite."""

    suite_name: str
    results: List[ExperimentResult]

    @property
    def count(self) -> int:
        return len(self.results)

    @property
    def scores(self) -> List[float]:
        return [r.score for r in self.results]

    @property
    def mean_score(self) -> float:
        if not self.results:
            return 0.0
        return sum(self.scores) / len(self.scores)

    @property
    def pass_rate(self, threshold: float = 0.5) -> float:
        """Fraction of experiments scoring above threshold."""
        if not self.results:
            return 0.0
        passed = sum(1 for s in self.scores if s >= threshold)
        return passed / len(self.scores)

    def scores_by_task(self) -> Dict[str, List[float]]:
        """Group scores by task name."""
        by_task: Dict[str, List[float]] = {}
        for r in self.results:
            by_task.setdefault(r.task_name, []).append(r.score)
        return by_task

    def to_dict(self) -> Dict[str, Any]:
        """Export results as a serializable dict."""
        return {
            "suite_name": self.suite_name,
            "count": self.count,
            "mean_score": self.mean_score,
            "results": [
                {
                    "task_name": r.task_name,
                    "score": r.score,
                    "prediction": _safe_serialize(r.prediction),
                    "details": r.details,
                }
                for r in self.results
            ],
        }

    def to_json(self) -> str:
        """Export results as JSON string."""
        return json.dumps(self.to_dict(), indent=2, default=str)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TestResults":
        """Import results from a dict."""
        results = [
            ExperimentResult(
                task_name=r["task_name"],
                score=r["score"],
                prediction=r["prediction"],
                details=r["details"],
            )
            for r in data["results"]
        ]
        return cls(suite_name=data["suite_name"], results=results)

    @classmethod
    def from_json(cls, json_str: str) -> "TestResults":
        """Import results from JSON string."""
        return cls.from_dict(json.loads(json_str))


def run_suite(
    suite: TestSuite,
    agent: AgentFn,
) -> TestResults:
    """Run all experiments in a test suite.

    Args:
        suite: The test suite to run
        agent: Agent function to evaluate

    Returns:
        TestResults with all scores
    """
    results = []
    for spec in suite.experiments:
        result = run_experiment(spec.interface, spec.task, agent)
        results.append(result)

    return TestResults(suite_name=suite.name, results=results)


def _safe_serialize(value: Any) -> Any:
    """Convert value to JSON-safe type."""
    if isinstance(value, (int, float, str, bool, type(None))):
        return value
    if isinstance(value, dict):
        return {str(k): _safe_serialize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe_serialize(v) for v in value]
    return str(value)
