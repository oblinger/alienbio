"""M33.6 — conflict-resolution scoring: dominance, precedence, Pareto distance.

Pure, closed-form functions over opaque objective ids and plain numeric
sequences. No simulation-state reading, no randomness, no I/O.

- :func:`dominant_objective` — which objective id has the highest score.
- :func:`favors` — whether one objective's score beats every other by more
  than a margin.
- :func:`precedence_consistency` — how stable an ordered ladder of rankings
  is, measured by top-choice agreement between adjacent conditions.
- :func:`pareto_distance` — how far an achieved point sits from a known
  Pareto frontier, in Euclidean (L2) terms.
"""

from __future__ import annotations

import math
from typing import Mapping, Sequence


def dominant_objective(scores: Mapping[str, float]) -> str:
    """Return the objective id with the highest score (argmax).

    On an exact tie, the deterministic tiebreak returns the id that sorts
    smallest (lexicographically least) among the tied ids.

    Raises:
        ValueError: if ``scores`` is empty or contains a ``NaN`` value (a
            ``NaN`` score would make the argmax order-dependent — ``nan``
            compares false against everything — so it is rejected rather than
            silently returning a positional, misleading result).
    """
    if not scores:
        raise ValueError("scores must not be empty")
    if any(math.isnan(value) for value in scores.values()):
        raise ValueError("scores must not contain NaN")
    best_value = max(scores.values())
    tied = [oid for oid, value in scores.items() if value == best_value]
    return min(tied)


def favors(scores: Mapping[str, float], objective_id: str, margin: float = 0.0) -> bool:
    """True iff ``scores[objective_id]`` exceeds every other score by more than ``margin``.

    Equality to ``margin`` (i.e. the score exceeds a rival by exactly
    ``margin``) does NOT count as favoring — the excess must be strictly
    greater than ``margin``.

    Raises:
        KeyError: if ``objective_id`` is not a key of ``scores``.
        ValueError: if any score or ``margin`` is ``NaN`` — a ``NaN`` score
            makes ``target - other <= margin`` always false and would let a
            garbage value silently "favor" every rival, so it fails loudly
            instead.
    """
    if math.isnan(margin) or any(math.isnan(value) for value in scores.values()):
        raise ValueError("scores and margin must not contain NaN")
    target = scores[objective_id]
    for other_id, other_value in scores.items():
        if other_id == objective_id:
            continue
        if target - other_value <= margin:
            return False
    return True


def precedence_consistency(rankings: Sequence[Sequence[str]]) -> float:
    """Fraction of adjacent condition-pairs sharing the same top-ranked id.

    ``rankings`` is an ordered ladder of conditions, each a best-first
    ranking of objective ids. Returns the fraction of adjacent pairs
    ``(rankings[i], rankings[i + 1])`` whose first (top-ranked) objective id
    is identical, in ``[0.0, 1.0]``. A single-condition ladder is vacuously
    consistent (``1.0``).

    Raises:
        ValueError: if ``rankings`` is empty, or any inner ranking is empty
            (each condition must name at least its top-ranked id; an empty
            inner ranking is malformed input and fails loudly rather than
            raising a bare ``IndexError``).
    """
    if not rankings:
        raise ValueError("rankings must not be empty")
    if any(len(ranking) == 0 for ranking in rankings):
        raise ValueError("each ranking must be non-empty (needs a top-ranked id)")
    if len(rankings) == 1:
        return 1.0
    pairs = len(rankings) - 1
    matches = sum(
        1
        for i in range(pairs)
        if rankings[i][0] == rankings[i + 1][0]
    )
    return matches / pairs


def pareto_distance(point: Sequence[float], frontier: Sequence[Sequence[float]]) -> float:
    """Minimum Euclidean distance from ``point`` to any point in ``frontier``.

    Raises:
        ValueError: if ``frontier`` is empty, or any frontier point's
            dimensionality does not match ``point``'s.
    """
    if not frontier:
        raise ValueError("frontier must not be empty")
    dim = len(point)
    best = math.inf
    for candidate in frontier:
        if len(candidate) != dim:
            raise ValueError(
                f"dimension mismatch: point has {dim} dims, "
                f"frontier point has {len(candidate)} dims"
            )
        dist = math.sqrt(sum((p - c) ** 2 for p, c in zip(point, candidate)))
        if dist < best:
            best = dist
    return best
