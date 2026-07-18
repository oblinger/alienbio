"""Acceptance tests for per-objective surfacing detection (M33.4)."""

from __future__ import annotations

from alienbio.suite.score_surfacing import (
    coverage_at_budget,
    is_monotone_coverage,
    surfacing_depth,
    surfacing_profile,
)
from alienbio.suite.score_surfacing import _is_monotone_sets


# ═══════════════════════════════════════════════════════════════════════════
# surfacing_depth
# ═══════════════════════════════════════════════════════════════════════════

def test_surfacing_depth_earliest_of_multiple():
    events = [(5, "a"), (2, "a"), (8, "a")]
    assert surfacing_depth(events, "a") == 2


def test_surfacing_depth_single_occurrence():
    events = [(0, "x"), (1, "y"), (2, "z")]
    assert surfacing_depth(events, "y") == 1


def test_surfacing_depth_absent_is_none():
    events = [(0, "x"), (1, "y")]
    assert surfacing_depth(events, "z") is None


def test_surfacing_depth_empty_events_is_none():
    assert surfacing_depth([], "a") is None


# ═══════════════════════════════════════════════════════════════════════════
# surfacing_profile
# ═══════════════════════════════════════════════════════════════════════════

def test_surfacing_profile_maps_all_ids():
    events = [(3, "a"), (1, "a"), (4, "b")]
    profile = surfacing_profile(events, ["a", "b", "c"])
    assert profile == {"a": 1, "b": 4, "c": None}


def test_surfacing_profile_empty_ids_is_empty_dict():
    events = [(0, "a")]
    assert surfacing_profile(events, []) == {}


def test_surfacing_profile_empty_events_all_none():
    profile = surfacing_profile([], ["a", "b"])
    assert profile == {"a": None, "b": None}


# ═══════════════════════════════════════════════════════════════════════════
# coverage_at_budget
# ═══════════════════════════════════════════════════════════════════════════

def test_coverage_at_budget_exact_boundary_inclusive():
    events = [(5, "a"), (10, "b"), (11, "c")]
    # budget exactly equal to b's surfacing turn (10) -> b is included.
    assert coverage_at_budget(events, ["a", "b", "c"], budget=10) == frozenset(
        {"a", "b"}
    )


def test_coverage_at_budget_below_all_surfacings_is_empty():
    events = [(5, "a"), (10, "b")]
    assert coverage_at_budget(events, ["a", "b"], budget=0) == frozenset()


def test_coverage_at_budget_ignores_ids_not_in_objective_ids():
    events = [(1, "a"), (1, "b")]
    assert coverage_at_budget(events, ["a"], budget=5) == frozenset({"a"})


def test_coverage_at_budget_empty_events_is_empty():
    assert coverage_at_budget([], ["a", "b"], budget=100) == frozenset()


def test_coverage_at_budget_empty_ids_is_empty():
    events = [(1, "a")]
    assert coverage_at_budget(events, [], budget=100) == frozenset()


# ═══════════════════════════════════════════════════════════════════════════
# is_monotone_coverage
# ═══════════════════════════════════════════════════════════════════════════

def test_is_monotone_coverage_true_on_real_sweep():
    events = [(2, "a"), (4, "b"), (6, "c")]
    objective_ids = ["a", "b", "c"]
    budgets = [0, 2, 4, 6, 8]
    assert is_monotone_coverage(events, objective_ids, budgets) is True


def test_is_monotone_coverage_true_on_unsorted_budgets():
    events = [(2, "a"), (4, "b"), (6, "c")]
    objective_ids = ["a", "b", "c"]
    # deliberately out-of-order budgets; sorted internally before the sweep.
    budgets = [8, 0, 6, 2, 4]
    assert is_monotone_coverage(events, objective_ids, budgets) is True


def test_is_monotone_coverage_empty_budgets_is_vacuously_true():
    events = [(2, "a")]
    assert is_monotone_coverage(events, ["a"], []) is True


def test_is_monotone_coverage_empty_events_is_true():
    assert is_monotone_coverage([], ["a", "b"], [0, 1, 2]) is True


def test_is_monotone_sets_true_on_hand_built_monotone_sequence():
    coverage_sets = [
        frozenset(),
        frozenset({"a"}),
        frozenset({"a", "b"}),
        frozenset({"a", "b", "c"}),
    ]
    assert _is_monotone_sets(coverage_sets) is True


def test_is_monotone_sets_false_on_hand_built_non_monotone_sequence():
    # "b" appears at budget index 1 then disappears at index 2 -> not a
    # subset relation, so the checker must catch it.
    coverage_sets = [
        frozenset({"a"}),
        frozenset({"a", "b"}),
        frozenset({"a"}),
    ]
    assert _is_monotone_sets(coverage_sets) is False


def test_is_monotone_sets_false_when_a_later_set_drops_and_adds():
    coverage_sets = [frozenset({"a", "b"}), frozenset({"a", "c"})]
    # "b" is dropped even though "c" is added -> not a superset -> non-monotone.
    assert _is_monotone_sets(coverage_sets) is False


def test_is_monotone_sets_true_on_single_or_empty_sequence():
    assert _is_monotone_sets([]) is True
    assert _is_monotone_sets([frozenset({"a"})]) is True
