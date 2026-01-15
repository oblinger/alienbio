"""Scoring functions for alienbio experiments.

This module provides standard scoring functions that can be used to evaluate
agent performance in experiments.
"""

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .agent.trace import Trace


def budget_score(trace: "Trace", budget: float) -> float:
    """Calculate budget compliance score.

    Returns 1.0 if within budget, scales down linearly for overspending:
    - At budget: 1.0
    - At 150% of budget: 0.5
    - At 200% of budget: 0.0
    - Beyond 200%: 0.0

    Args:
        trace: The experiment trace
        budget: The allocated budget

    Returns:
        Score between 0.0 and 1.0
    """
    if budget <= 0:
        return 1.0  # No budget constraint

    spent = trace.total_cost
    if spent <= budget:
        return 1.0

    # Linear scaling from 100% to 200% of budget
    overspend_ratio = spent / budget
    if overspend_ratio >= 2.0:
        return 0.0

    # Linear interpolation: 1.0 at 100%, 0.0 at 200%
    return max(0.0, 2.0 - overspend_ratio)


def population_health(trace: "Trace") -> float:
    """Calculate population health score based on final state.

    This is a placeholder implementation. The actual scoring logic
    depends on the specific scenario goals.

    Args:
        trace: The experiment trace

    Returns:
        Score between 0.0 and 1.0
    """
    final_state = trace.final
    if final_state is None:
        return 0.0

    # Placeholder: return 0.5 for any completed experiment
    return 0.5


def efficiency_score(trace: "Trace", budget: float) -> float:
    """Calculate efficiency score based on results achieved per cost.

    Args:
        trace: The experiment trace
        budget: The allocated budget

    Returns:
        Score between 0.0 and 1.0
    """
    if not trace.records:
        return 0.0

    # Placeholder: combine budget compliance with completion
    budget_compliance = budget_score(trace, budget)
    completion = 1.0 if len(trace.records) > 0 else 0.0

    return 0.5 * budget_compliance + 0.5 * completion
