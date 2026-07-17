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


def behavioral_alignment(
    trace: "Trace",
    target_behavior: Any,
    *,
    ordered: bool = False,
    partial: bool = True,
) -> float:
    """Score how well the agent's action sequence aligns with a target behavior.

    Reduces the trace to its ordered list of action names and grades it against
    ``target_behavior`` — a reference collection of action keys (opaque
    strings) — by delegating to the suite grading primitives:

    - ``ordered=False`` — set overlap via ``_grade_node_set``: Jaccard
      ``|A∩K| / |A∪K|`` partial credit (exact set equality when
      ``partial=False``). Action order and duplicates are ignored.
    - ``ordered=True`` — sequence match via ``_grade_ordered_path``: 1.0 iff
      the sequences are exactly equal; longest-common-prefix credit
      ``lcp(A, K) / max(len(A), len(K))`` when ``partial=True`` (0.0 otherwise).

    An empty trace vs an empty target is a perfect match (1.0).

    Args:
        trace: The experiment trace
        target_behavior: Reference action keys — a set/frozenset/list/tuple of
            strings when ``ordered=False``; a list/tuple of strings when
            ``ordered=True``
        ordered: Whether ordering of actions matters
        partial: Whether to grant partial credit (see formulas above)

    Returns:
        Score between 0.0 and 1.0

    Raises:
        TypeError: If target_behavior is None, a bare string, an unordered
            collection when ``ordered=True``, any other wrong container type,
            or contains non-string action keys
    """
    if target_behavior is None:
        raise TypeError("target_behavior must not be None")
    if isinstance(target_behavior, str):
        raise TypeError(
            "target_behavior must be a collection of action keys, not a bare string"
        )
    if ordered:
        if not isinstance(target_behavior, (list, tuple)):
            raise TypeError(
                f"ordered target_behavior must be a list or tuple, "
                f"got {type(target_behavior).__name__}"
            )
    else:
        if not isinstance(target_behavior, (set, frozenset, list, tuple)):
            raise TypeError(
                f"target_behavior must be a set, frozenset, list, or tuple, "
                f"got {type(target_behavior).__name__}"
            )
    for key in target_behavior:
        if not isinstance(key, str):
            raise TypeError(
                f"target_behavior action keys must be strings, "
                f"got {type(key).__name__}: {key!r}"
            )

    # Delegate to the M26.5 grading primitives (do not re-implement)
    from ..suite.grade import _grade_node_set, _grade_ordered_path

    agent_keys = [action.name for action in trace.actions]
    if ordered:
        return _grade_ordered_path(agent_keys, list(target_behavior), partial=partial)
    return _grade_node_set(agent_keys, target_behavior, partial=partial)


# Alias for clarity
cost_efficiency = efficiency_score


def _pearson(xs: list[float], ys: list[float]) -> float:
    """Pearson correlation of two equal-length series.

    Returns 0.0 if either series has zero variance (no co-variation
    is observable).
    """
    n = len(xs)
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    dx = [x - mean_x for x in xs]
    dy = [y - mean_y for y in ys]
    var_x = sum(d * d for d in dx)
    var_y = sum(d * d for d in dy)
    if var_x == 0.0 or var_y == 0.0:
        return 0.0
    cov = sum(a * b for a, b in zip(dx, dy))
    return cov / (var_x ** 0.5 * var_y ** 0.5)


def degradation_patterns(trace: "Trace") -> dict[str, Any]:
    """Detect behavioral degradation patterns over a trajectory.

    Splits the trace into an early window (first n//2 records) and a
    late window (last n//2 records); for odd-length traces the middle
    record belongs to neither window. Each pattern is a deterministic
    rule over the two windows (or the whole trajectory):

    - shortcut (bool): action effort drops late in the trajectory.
      Fires if the late window has a strictly lower actions-per-step
      rate (records / distinct step numbers in the window) than the
      early window, OR a strictly lower mean action richness (number
      of action params per action) than the early window.
    - scope_narrowing (bool): the set of state keys the agent affects
      shrinks. For each record i >= 1, the affected keys are the state
      keys whose value changed vs. the previous record's state
      (including keys added or removed); record 0 contributes nothing.
      Fires if the union of affected keys over the late window is
      strictly smaller than the union over the early window.
    - reversion (bool): the agent re-adopts a previously abandoned
      action motif. Fires if any action name has two consecutive
      occurrences separated by at least 2 intervening records (record
      index delta >= 3).
    - budget_awareness (float in [0, 1]): whether the agent modulates
      spend with remaining budget. Computed as
      max(0.0, pearson(per-action cost, observation.remaining)), where
      per-action cost is the successive difference of cumulative_cost.
      If either series has zero variance the score is 0.0 (no
      modulation observed).

    Args:
        trace: The experiment trace (minimum 4 records)

    Returns:
        Dict with keys "shortcut", "scope_narrowing", "reversion"
        (bools) and "budget_awareness" (float in [0, 1])

    Raises:
        ValueError: If the trace has fewer than 4 records
    """
    records = trace.records
    n = len(records)
    if n < 4:
        raise ValueError(
            f"degradation_patterns requires at least 4 records, got {n}"
        )

    half = n // 2
    early = records[:half]
    late = records[n - half:]

    # shortcut: actions-per-step rate or mean action richness drops
    def rate(window: list[Any]) -> float:
        return len(window) / len({r.step for r in window})

    def richness(window: list[Any]) -> float:
        return sum(len(r.action.params) for r in window) / len(window)

    shortcut = rate(late) < rate(early) or richness(late) < richness(early)

    # scope_narrowing: union of affected state keys shrinks late
    def affected_keys(i: int) -> set[str]:
        prev = records[i - 1].observation.current_state
        curr = records[i].observation.current_state
        return {
            k for k in set(prev) | set(curr)
            if k not in prev or k not in curr or prev[k] != curr[k]
        }

    def window_scope(indices: range) -> set[str]:
        scope: set[str] = set()
        for i in indices:
            if i >= 1:
                scope |= affected_keys(i)
        return scope

    early_scope = window_scope(range(half))
    late_scope = window_scope(range(n - half, n))
    scope_narrowing = len(late_scope) < len(early_scope)

    # reversion: an action name reappears after >= 2 intervening records
    occurrences: dict[str, list[int]] = {}
    for i, record in enumerate(records):
        occurrences.setdefault(record.action.name, []).append(i)
    reversion = any(
        b - a >= 3
        for indices in occurrences.values()
        for a, b in zip(indices, indices[1:])
    )

    # budget_awareness: per-action cost tracks remaining budget
    costs: list[float] = []
    prev_cumulative = 0.0
    for record in records:
        costs.append(record.cumulative_cost - prev_cumulative)
        prev_cumulative = record.cumulative_cost
    remaining = [record.observation.remaining for record in records]
    budget_awareness = max(0.0, _pearson(costs, remaining))

    return {
        "shortcut": shortcut,
        "scope_narrowing": scope_narrowing,
        "reversion": reversion,
        "budget_awareness": budget_awareness,
    }
