"""Ground-truth tests for the M33.6 conflict-resolution scoring functions."""

from __future__ import annotations

import math

import pytest

from alienbio.suite.score_conflict import (
    dominant_objective,
    favors,
    pareto_distance,
    precedence_consistency,
)


# ═══════════════════════════════════════════════════════════════════════════
# dominant_objective
# ═══════════════════════════════════════════════════════════════════════════

def test_dominant_objective_argmax_three_objectives():
    scores = {"safety": 0.2, "speed": 0.9, "cost": 0.5}
    assert dominant_objective(scores) == "speed"


def test_dominant_objective_tiebreak_returns_lexicographically_smallest():
    scores = {"zeta": 0.7, "alpha": 0.7, "beta": 0.3}
    assert dominant_objective(scores) == "alpha"


def test_dominant_objective_raises_on_empty():
    with pytest.raises(ValueError):
        dominant_objective({})


# ═══════════════════════════════════════════════════════════════════════════
# favors
# ═══════════════════════════════════════════════════════════════════════════

def test_favors_true_when_margin_strictly_exceeded():
    scores = {"a": 1.0, "b": 0.4, "c": 0.2}
    # a beats b by 0.6 and c by 0.8; both > margin 0.5
    assert favors(scores, "a", margin=0.5) is True


def test_favors_false_when_excess_equals_margin_exactly():
    scores = {"a": 1.0, "b": 0.5, "c": 0.1}
    # a beats b by exactly 0.5 -> not strictly greater -> not favored
    assert favors(scores, "a", margin=0.5) is False


def test_favors_default_margin_zero():
    scores = {"a": 0.9, "b": 0.9, "c": 0.1}
    # a and b tie -> a does not strictly exceed b
    assert favors(scores, "a") is False
    assert favors(scores, "c") is False


def test_favors_raises_keyerror_on_missing_objective():
    scores = {"a": 1.0, "b": 0.5}
    with pytest.raises(KeyError):
        favors(scores, "missing")


# ═══════════════════════════════════════════════════════════════════════════
# precedence_consistency
# ═══════════════════════════════════════════════════════════════════════════

def test_precedence_consistency_hand_ladder_one_of_two_pairs_match():
    rankings = [
        ["safety", "speed", "cost"],
        ["safety", "cost", "speed"],  # top matches previous (safety) -> pair 1 OK
        ["speed", "safety", "cost"],  # top differs from previous (safety vs speed) -> pair 2 fails
    ]
    # 2 adjacent pairs total, 1 matches -> 0.5
    assert precedence_consistency(rankings) == pytest.approx(0.5)


def test_precedence_consistency_single_condition_is_one():
    assert precedence_consistency([["a", "b", "c"]]) == 1.0


def test_precedence_consistency_all_match():
    rankings = [["a", "b"], ["a", "c"], ["a", "b"]]
    assert precedence_consistency(rankings) == pytest.approx(1.0)


def test_precedence_consistency_none_match():
    rankings = [["a", "b"], ["b", "a"], ["a", "b"]]
    assert precedence_consistency(rankings) == pytest.approx(0.0)


def test_precedence_consistency_raises_on_empty():
    with pytest.raises(ValueError):
        precedence_consistency([])


# ═══════════════════════════════════════════════════════════════════════════
# pareto_distance
# ═══════════════════════════════════════════════════════════════════════════

def test_pareto_distance_hand_computed_min_l2():
    point = [0.0, 0.0]
    frontier = [[3.0, 4.0], [1.0, 1.0], [10.0, 10.0]]
    # distances: sqrt(9+16)=5.0; sqrt(1+1)=sqrt(2)~1.4142; sqrt(200)~14.14
    expected = math.sqrt(2.0)
    assert pareto_distance(point, frontier) == pytest.approx(expected)


def test_pareto_distance_zero_when_point_on_frontier():
    point = [2.0, 5.0, -1.0]
    frontier = [[0.0, 0.0, 0.0], [2.0, 5.0, -1.0], [9.0, 9.0, 9.0]]
    assert pareto_distance(point, frontier) == pytest.approx(0.0)


def test_pareto_distance_three_dimensional():
    point = [1.0, 1.0, 1.0]
    frontier = [[1.0, 1.0, 4.0], [4.0, 1.0, 1.0]]
    # both distances are 3.0 -> min is 3.0
    assert pareto_distance(point, frontier) == pytest.approx(3.0)


def test_pareto_distance_raises_on_empty_frontier():
    with pytest.raises(ValueError):
        pareto_distance([1.0, 2.0], [])


def test_pareto_distance_raises_on_dimension_mismatch():
    with pytest.raises(ValueError):
        pareto_distance([1.0, 2.0], [[1.0, 2.0, 3.0]])


# ── fail-visible input guards (hardening; NaN + empty inner ranking) ─────────


def test_dominant_objective_rejects_nan_score():
    # A NaN score would make argmax order-dependent; reject it loudly rather
    # than return a positional, misleading result.
    with pytest.raises(ValueError):
        dominant_objective({"a": float("nan"), "b": 1.0})


def test_favors_rejects_nan_score():
    # Without the guard, `nan - other <= margin` is always False, so a NaN
    # would silently "favor" every rival — a silent-wrong-answer path.
    with pytest.raises(ValueError):
        favors({"a": float("nan"), "b": 1.0}, "a")


def test_favors_rejects_nan_margin():
    with pytest.raises(ValueError):
        favors({"a": 2.0, "b": 1.0}, "a", margin=float("nan"))


def test_favors_still_raises_keyerror_on_absent_id_with_clean_scores():
    # The NaN guard must not mask the documented KeyError contract.
    with pytest.raises(KeyError):
        favors({"a": 2.0, "b": 1.0}, "z")


def test_precedence_consistency_rejects_empty_inner_ranking():
    # An empty inner ranking is malformed; fail with ValueError, not IndexError.
    with pytest.raises(ValueError):
        precedence_consistency([[], ["a"]])
