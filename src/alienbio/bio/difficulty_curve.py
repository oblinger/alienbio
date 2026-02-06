"""Difficulty curve: measure agent performance across difficulty levels."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, TYPE_CHECKING

if TYPE_CHECKING:
    from .agent_interface import AgentInterface
    from .task import Task

AgentFn = Callable[["AgentInterface", "Task"], Any]


@dataclass
class DifficultyLevel:
    """A named difficulty level with associated tasks."""

    level: int
    label: str
    tasks: List["Task"] = field(default_factory=list)


@dataclass
class DifficultyPoint:
    """Performance at one difficulty level."""

    level: int
    label: str
    mean_score: float
    scores: List[float]
    count: int
    pass_rate: float


@dataclass
class DifficultyCurve:
    """Agent performance across difficulty levels.

    Each point maps a difficulty level to the agent's mean score.
    A monotonically decreasing curve indicates well-calibrated difficulty.
    """

    agent_name: str
    points: List[DifficultyPoint]

    @property
    def levels(self) -> List[int]:
        return [p.level for p in self.points]

    @property
    def mean_scores(self) -> List[float]:
        return [p.mean_score for p in self.points]

    def is_monotonic_decreasing(self, tolerance: float = 0.0) -> bool:
        """Check if performance decreases with difficulty."""
        scores = self.mean_scores
        for i in range(len(scores) - 1):
            if scores[i + 1] > scores[i] + tolerance:
                return False
        return True

    def capability_threshold(self, min_score: float = 0.5) -> int | None:
        """Find the highest difficulty where mean score >= min_score.

        Returns None if the agent never reaches min_score.
        """
        best = None
        for p in self.points:
            if p.mean_score >= min_score:
                if best is None or p.level > best:
                    best = p.level
        return best

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_name": self.agent_name,
            "points": [
                {
                    "level": p.level,
                    "label": p.label,
                    "mean_score": p.mean_score,
                    "count": p.count,
                    "pass_rate": p.pass_rate,
                }
                for p in self.points
            ],
        }


@dataclass
class DifficultySpec:
    """Specification for generating tasks at multiple difficulty levels."""

    levels: List[DifficultyLevel]

    def add_level(self, level: int, label: str, tasks: List["Task"] | None = None) -> DifficultyLevel:
        dl = DifficultyLevel(level=level, label=label, tasks=tasks or [])
        self.levels.append(dl)
        return dl

    @property
    def num_levels(self) -> int:
        return len(self.levels)


def measure_difficulty_curve(
    spec: DifficultySpec,
    interface: "AgentInterface",
    agent: AgentFn,
    agent_name: str = "agent",
    threshold: float = 0.5,
) -> DifficultyCurve:
    """Measure agent performance across difficulty levels.

    Runs the agent on all tasks at each difficulty level and computes
    per-level statistics.

    Args:
        spec: Difficulty specification with levels and tasks
        interface: Agent interface for experiments
        agent: Agent function to evaluate
        agent_name: Name for the agent in results
        threshold: Score threshold for pass/fail

    Returns:
        DifficultyCurve with performance at each level
    """
    from .experiment import run_experiment

    points: List[DifficultyPoint] = []

    for dl in spec.levels:
        scores: List[float] = []
        for task in dl.tasks:
            result = run_experiment(interface, task, agent)
            scores.append(result.score)

        if scores:
            mean = sum(scores) / len(scores)
            passed = sum(1 for s in scores if s >= threshold)
            pass_rate = passed / len(scores)
        else:
            mean = 0.0
            pass_rate = 0.0

        points.append(DifficultyPoint(
            level=dl.level,
            label=dl.label,
            mean_score=mean,
            scores=scores,
            count=len(scores),
            pass_rate=pass_rate,
        ))

    return DifficultyCurve(agent_name=agent_name, points=points)


def compare_difficulty_curves(
    curves: List[DifficultyCurve],
) -> Dict[str, Any]:
    """Compare multiple agents' difficulty curves.

    Returns a summary dict with per-level rankings.
    """
    if not curves:
        return {"levels": [], "rankings": {}}

    all_levels = sorted(set(lv for c in curves for lv in c.levels))
    rankings: Dict[int, List[Dict[str, Any]]] = {}

    for level in all_levels:
        level_entries = []
        for curve in curves:
            for p in curve.points:
                if p.level == level:
                    level_entries.append({
                        "agent": curve.agent_name,
                        "mean_score": p.mean_score,
                        "pass_rate": p.pass_rate,
                    })
        level_entries.sort(key=lambda e: e["mean_score"], reverse=True)
        rankings[level] = level_entries

    return {
        "levels": all_levels,
        "rankings": rankings,
    }
