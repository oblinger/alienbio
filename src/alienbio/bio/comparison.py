"""Agent comparison: compare and rank agent performance across experiments."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List

from .harness import TestResults


@dataclass
class AgentStats:
    """Statistical summary for one agent."""

    agent_name: str
    mean: float
    std: float
    min: float
    max: float
    count: int
    pass_rate: float


@dataclass
class ComparisonTable:
    """Comparison of multiple agents."""

    agents: List[AgentStats]

    @property
    def ranking(self) -> List[AgentStats]:
        """Agents sorted by mean score, descending."""
        return sorted(self.agents, key=lambda a: a.mean, reverse=True)

    def leader(self) -> AgentStats:
        """Top-ranked agent."""
        return self.ranking[0]

    def to_dict(self) -> Dict[str, Any]:
        """Export as serializable dict."""
        return {
            "agents": [
                {
                    "agent_name": a.agent_name,
                    "mean": a.mean,
                    "std": a.std,
                    "min": a.min,
                    "max": a.max,
                    "count": a.count,
                    "pass_rate": a.pass_rate,
                }
                for a in self.ranking
            ],
        }


def _compute_stats(
    name: str,
    scores: List[float],
    threshold: float = 0.5,
) -> AgentStats:
    """Compute statistics for a list of scores."""
    n = len(scores)
    if n == 0:
        return AgentStats(name, 0.0, 0.0, 0.0, 0.0, 0, 0.0)

    mean = sum(scores) / n
    variance = sum((s - mean) ** 2 for s in scores) / n
    std = math.sqrt(variance)
    passed = sum(1 for s in scores if s >= threshold)

    return AgentStats(
        agent_name=name,
        mean=mean,
        std=std,
        min=min(scores),
        max=max(scores),
        count=n,
        pass_rate=passed / n,
    )


def compare(
    results: Dict[str, TestResults],
    *,
    threshold: float = 0.5,
) -> ComparisonTable:
    """Compare multiple agents' results.

    Args:
        results: Dict mapping agent_name -> TestResults
        threshold: Score threshold for pass/fail (default 0.5)

    Returns:
        ComparisonTable with ranked agent statistics
    """
    agents = []
    for agent_name, test_results in results.items():
        stats = _compute_stats(agent_name, test_results.scores, threshold)
        agents.append(stats)

    return ComparisonTable(agents=agents)


def compare_by_task(
    results: Dict[str, TestResults],
    *,
    threshold: float = 0.5,
) -> Dict[str, ComparisonTable]:
    """Compare agents grouped by task type.

    Args:
        results: Dict mapping agent_name -> TestResults
        threshold: Score threshold for pass/fail

    Returns:
        Dict mapping task_name -> ComparisonTable
    """
    # Collect scores by (task, agent)
    task_scores: Dict[str, Dict[str, List[float]]] = {}
    for agent_name, test_results in results.items():
        by_task = test_results.scores_by_task()
        for task_name, scores in by_task.items():
            if task_name not in task_scores:
                task_scores[task_name] = {}
            task_scores[task_name][agent_name] = scores

    # Build comparison table per task
    tables: Dict[str, ComparisonTable] = {}
    for task_name, agent_scores in task_scores.items():
        agents = []
        for agent_name, scores in agent_scores.items():
            stats = _compute_stats(agent_name, scores, threshold)
            agents.append(stats)
        tables[task_name] = ComparisonTable(agents=agents)

    return tables
