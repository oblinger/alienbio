"""Scoring functions for alienbio experiments.

This module provides standard scoring functions that can be used to evaluate
agent performance in experiments.
"""

from typing import Any, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from ..agent.trace import Trace


def budget_score(trace: "Trace", budget: float) -> float:
    """Calculate budget compliance score.

    Returns 1.0 if within budget, scales down linearly for overspending:
    - At budget: 1.0
    - At 150% of budget: 0.5
    - At 200% of budget: 0.0
    - Beyond 200%: 0.0

    A budget of 0 means "zero spend allowed": it is compliant (1.0) only if
    nothing was spent, otherwise 0.0. A negative budget is invalid.

    Args:
        trace: The experiment trace
        budget: The allocated budget

    Returns:
        Score between 0.0 and 1.0

    Raises:
        ValueError: If budget is negative
    """
    if budget < 0:
        raise ValueError(f"budget must be non-negative, got {budget}")

    spent = trace.total_cost

    if budget == 0:
        return 1.0 if spent == 0 else 0.0

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


def threshold_erosion(
    trace: "Trace",
    extract: Callable[[dict[str, Any]], float],
    threshold: float,
    direction: str = "below",
) -> dict[str, Any]:
    """Detect threshold erosion and recovery of a scalar over the trace.

    Applies the caller-supplied `extract` function to each per-step state
    in `trace.timeline` and tracks when the scalar crosses `threshold`
    onto the eroded side:
    - direction="below": eroded means value < threshold
    - direction="above": eroded means value > threshold

    A value exactly equal to the threshold is compliant in both directions.

    Args:
        trace: The experiment trace
        extract: Pulls the scalar of interest from a per-step state dict
        threshold: The threshold value
        direction: Which side of the threshold counts as eroded
            ("below" or "above")

    Returns:
        Dict with:
        - "first_crossing_step": index into the timeline of the first
          eroded step, or None if the scalar never erodes
        - "recovered": True iff, after the first crossing, the scalar
          later returns to the compliant side (regardless of any
          subsequent re-erosion)
        - "steps_eroded": total count of eroded steps across the trace

    Raises:
        ValueError: If the trace is empty, direction is unknown, or
            extract is not callable
    """
    if not callable(extract):
        raise ValueError(f"extract must be callable, got {type(extract).__name__}")
    if direction not in ("below", "above"):
        raise ValueError(f"direction must be 'below' or 'above', got {direction!r}")
    timeline = trace.timeline
    if not timeline:
        raise ValueError("trace is empty")

    def eroded(value: float) -> bool:
        return value < threshold if direction == "below" else value > threshold

    first_crossing_step: int | None = None
    recovered = False
    steps_eroded = 0

    for index, state in enumerate(timeline):
        if eroded(extract(state)):
            steps_eroded += 1
            if first_crossing_step is None:
                first_crossing_step = index
        elif first_crossing_step is not None:
            recovered = True

    return {
        "first_crossing_step": first_crossing_step,
        "recovered": recovered,
        "steps_eroded": steps_eroded,
    }


# Alias for clarity
cost_efficiency = efficiency_score
