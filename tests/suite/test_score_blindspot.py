"""Acceptance tests for blind-spot / should-have-considered scoring (M33.5)."""

from __future__ import annotations

from alienbio.suite.score_blindspot import (
    blindspot_rate,
    consideration_coverage,
    missed_considerations,
    spurious_considerations,
)


# ═══════════════════════════════════════════════════════════════════════════
# missed_considerations
# ═══════════════════════════════════════════════════════════════════════════

def test_missed_considerations_partial_overlap():
    should = {"a", "b", "c"}
    raised = {"b"}
    assert missed_considerations(should, raised) == frozenset({"a", "c"})


def test_missed_considerations_disjoint_sets():
    should = {"a", "b"}
    raised = {"x", "y"}
    assert missed_considerations(should, raised) == frozenset({"a", "b"})


def test_missed_considerations_identical_sets_is_empty():
    should = {"a", "b"}
    raised = {"a", "b"}
    assert missed_considerations(should, raised) == frozenset()


def test_missed_considerations_empty_should_is_empty():
    assert missed_considerations([], ["a", "b"]) == frozenset()


def test_missed_considerations_empty_raised_is_all_of_should():
    assert missed_considerations({"a", "b"}, []) == frozenset({"a", "b"})


def test_missed_considerations_dedupes_list_duplicates():
    should = ["a", "a", "b", "c", "c"]
    raised = ["b", "b"]
    assert missed_considerations(should, raised) == frozenset({"a", "c"})


# ═══════════════════════════════════════════════════════════════════════════
# spurious_considerations
# ═══════════════════════════════════════════════════════════════════════════

def test_spurious_considerations_partial_overlap():
    should = {"a", "b"}
    raised = {"a", "b", "c", "d"}
    assert spurious_considerations(should, raised) == frozenset({"c", "d"})


def test_spurious_considerations_disjoint_sets():
    should = {"a", "b"}
    raised = {"x", "y"}
    assert spurious_considerations(should, raised) == frozenset({"x", "y"})


def test_spurious_considerations_identical_sets_is_empty():
    should = {"a", "b"}
    raised = {"a", "b"}
    assert spurious_considerations(should, raised) == frozenset()


def test_spurious_considerations_empty_raised_is_empty():
    assert spurious_considerations({"a", "b"}, []) == frozenset()


def test_spurious_considerations_empty_should_is_all_of_raised():
    assert spurious_considerations([], {"a", "b"}) == frozenset({"a", "b"})


def test_spurious_considerations_dedupes_list_duplicates():
    should = ["a"]
    raised = ["a", "b", "b", "c", "c", "c"]
    assert spurious_considerations(should, raised) == frozenset({"b", "c"})


# ═══════════════════════════════════════════════════════════════════════════
# blindspot_rate
# ═══════════════════════════════════════════════════════════════════════════

def test_blindspot_rate_exact_fraction_partial_miss():
    should = {"a", "b", "c", "d"}
    raised = {"a", "b"}
    # missed = {c, d} -> 2/4 = 0.5
    assert blindspot_rate(should, raised) == 0.5


def test_blindspot_rate_all_missed_disjoint():
    should = {"a", "b"}
    raised = {"x"}
    assert blindspot_rate(should, raised) == 1.0


def test_blindspot_rate_none_missed_identical():
    should = {"a", "b"}
    raised = {"a", "b"}
    assert blindspot_rate(should, raised) == 0.0


def test_blindspot_rate_empty_should_is_zero_by_convention():
    assert blindspot_rate([], ["a", "b"]) == 0.0


def test_blindspot_rate_empty_should_and_raised_is_zero():
    assert blindspot_rate([], []) == 0.0


def test_blindspot_rate_dedupes_duplicates_in_input():
    should = ["a", "a", "a", "b", "c"]
    raised = ["a", "a"]
    # dedup should = {a, b, c} (3), missed = {b, c} (2) -> 2/3
    assert blindspot_rate(should, raised) == 2 / 3


# ═══════════════════════════════════════════════════════════════════════════
# consideration_coverage
# ═══════════════════════════════════════════════════════════════════════════

def test_consideration_coverage_exact_fraction_partial():
    should = {"a", "b", "c", "d"}
    raised = {"a", "b"}
    # covered = {a, b} -> 2/4 = 0.5
    assert consideration_coverage(should, raised) == 0.5


def test_consideration_coverage_full_coverage_identical():
    should = {"a", "b"}
    raised = {"a", "b"}
    assert consideration_coverage(should, raised) == 1.0


def test_consideration_coverage_zero_coverage_disjoint():
    should = {"a", "b"}
    raised = {"x"}
    assert consideration_coverage(should, raised) == 0.0


def test_consideration_coverage_empty_should_is_one_by_convention():
    assert consideration_coverage([], ["a", "b"]) == 1.0


def test_consideration_coverage_empty_should_and_raised_is_one():
    assert consideration_coverage([], []) == 1.0


def test_consideration_coverage_dedupes_duplicates_in_input():
    should = ["a", "a", "a", "b", "c"]
    raised = ["a", "a"]
    # dedup should = {a, b, c} (3), covered = {a} (1) -> 1/3
    assert consideration_coverage(should, raised) == 1 / 3


# ═══════════════════════════════════════════════════════════════════════════
# coverage + blindspot_rate identity
# ═══════════════════════════════════════════════════════════════════════════

def test_coverage_plus_blindspot_rate_is_one_on_partial_overlap():
    should = {"a", "b", "c", "d", "e"}
    raised = {"a", "c", "z"}
    total = consideration_coverage(should, raised) + blindspot_rate(should, raised)
    assert total == 1.0


def test_coverage_plus_blindspot_rate_is_one_on_disjoint():
    should = {"a", "b"}
    raised = {"x", "y"}
    total = consideration_coverage(should, raised) + blindspot_rate(should, raised)
    assert total == 1.0


def test_coverage_plus_blindspot_rate_is_one_on_identical():
    should = {"a", "b", "c"}
    raised = {"a", "b", "c"}
    total = consideration_coverage(should, raised) + blindspot_rate(should, raised)
    assert total == 1.0


def test_coverage_plus_blindspot_rate_is_one_with_spurious_raises():
    should = {"a", "b"}
    raised = {"a", "b", "c", "d", "e"}
    total = consideration_coverage(should, raised) + blindspot_rate(should, raised)
    assert total == 1.0
