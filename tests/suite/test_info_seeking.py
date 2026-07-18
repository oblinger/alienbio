"""Ground-truth tests for the M33.8 info-seeking / action-cost metrics."""

from __future__ import annotations

import dataclasses

import pytest

from alienbio.suite.info_seeking import (
    ActionRecord,
    actions_before_commit,
    destructive_count,
    destructive_rate,
    info_seeking_count,
    info_seeking_ratio,
)


# ═══════════════════════════════════════════════════════════════════════════
# ActionRecord
# ═══════════════════════════════════════════════════════════════════════════

def test_action_record_default_destructive_false():
    action = ActionRecord(kind="probe")
    assert action.kind == "probe"
    assert action.destructive is False


def test_action_record_is_frozen():
    action = ActionRecord(kind="probe")
    with pytest.raises(dataclasses.FrozenInstanceError):
        action.kind = "other"  # type: ignore[misc]


def test_action_record_is_hashable():
    a = ActionRecord(kind="probe", destructive=False)
    b = ActionRecord(kind="probe", destructive=False)
    assert hash(a) == hash(b)
    assert {a, b} == {a}


# ═══════════════════════════════════════════════════════════════════════════
# info_seeking_count / info_seeking_ratio
# ═══════════════════════════════════════════════════════════════════════════

def test_info_seeking_count_hand_computed():
    actions = [
        ActionRecord(kind="probe"),
        ActionRecord(kind="answer"),
        ActionRecord(kind="scan"),
        ActionRecord(kind="answer"),
    ]
    assert info_seeking_count(actions, {"probe", "scan"}) == 2


def test_info_seeking_ratio_hand_computed():
    actions = [
        ActionRecord(kind="probe"),
        ActionRecord(kind="answer"),
        ActionRecord(kind="scan"),
        ActionRecord(kind="answer"),
    ]
    # 2 of 4 investigative -> 0.5
    assert info_seeking_ratio(actions, {"probe", "scan"}) == pytest.approx(0.5)


def test_info_seeking_ratio_empty_log_is_zero():
    assert info_seeking_ratio([], {"probe"}) == 0.0


def test_info_seeking_count_empty_log_is_zero():
    assert info_seeking_count([], {"probe"}) == 0


def test_info_seeking_ratio_all_investigative_is_one():
    actions = [ActionRecord(kind="probe"), ActionRecord(kind="scan")]
    assert info_seeking_ratio(actions, {"probe", "scan"}) == pytest.approx(1.0)


def test_info_seeking_ratio_none_investigative_is_zero():
    actions = [ActionRecord(kind="answer"), ActionRecord(kind="commit")]
    assert info_seeking_ratio(actions, {"probe", "scan"}) == 0.0


def test_info_seeking_count_disjoint_kinds_never_counted():
    # investigative_kinds referencing a kind never present in the log.
    actions = [ActionRecord(kind="probe"), ActionRecord(kind="answer")]
    assert info_seeking_count(actions, {"nonexistent_kind"}) == 0


def test_info_seeking_ratio_in_bounds_for_mixed_log():
    actions = [ActionRecord(kind=k) for k in ["probe", "probe", "answer"]]
    ratio = info_seeking_ratio(actions, {"probe"})
    assert 0.0 <= ratio <= 1.0
    assert ratio == pytest.approx(2 / 3)


# ═══════════════════════════════════════════════════════════════════════════
# destructive_count / destructive_rate
# ═══════════════════════════════════════════════════════════════════════════

def test_destructive_count_hand_computed():
    actions = [
        ActionRecord(kind="probe", destructive=False),
        ActionRecord(kind="harvest", destructive=True),
        ActionRecord(kind="scan", destructive=False),
        ActionRecord(kind="cut", destructive=True),
    ]
    assert destructive_count(actions) == 2


def test_destructive_rate_hand_computed():
    actions = [
        ActionRecord(kind="probe", destructive=False),
        ActionRecord(kind="harvest", destructive=True),
        ActionRecord(kind="scan", destructive=False),
        ActionRecord(kind="cut", destructive=True),
    ]
    # 2 of 4 destructive -> 0.5
    assert destructive_rate(actions) == pytest.approx(0.5)


def test_destructive_count_empty_log_is_zero():
    assert destructive_count([]) == 0


def test_destructive_rate_empty_log_is_zero():
    assert destructive_rate([]) == 0.0


def test_destructive_rate_all_destructive_is_one():
    actions = [ActionRecord(kind="cut", destructive=True) for _ in range(3)]
    assert destructive_rate(actions) == pytest.approx(1.0)


def test_destructive_rate_none_destructive_is_zero():
    actions = [ActionRecord(kind="probe", destructive=False) for _ in range(3)]
    assert destructive_rate(actions) == 0.0


# ═══════════════════════════════════════════════════════════════════════════
# actions_before_commit
# ═══════════════════════════════════════════════════════════════════════════

def test_actions_before_commit_commit_in_middle():
    actions = [
        ActionRecord(kind="probe"),
        ActionRecord(kind="scan"),
        ActionRecord(kind="commit"),
        ActionRecord(kind="probe"),
    ]
    # first commit-kind action is at index 2 -> 2 preceding actions
    assert actions_before_commit(actions, {"commit"}) == 2


def test_actions_before_commit_at_index_zero():
    actions = [
        ActionRecord(kind="commit"),
        ActionRecord(kind="probe"),
    ]
    assert actions_before_commit(actions, {"commit"}) == 0


def test_actions_before_commit_absent_returns_full_length():
    actions = [
        ActionRecord(kind="probe"),
        ActionRecord(kind="scan"),
        ActionRecord(kind="probe"),
    ]
    assert actions_before_commit(actions, {"commit"}) == len(actions)


def test_actions_before_commit_empty_log_returns_zero():
    assert actions_before_commit([], {"commit"}) == 0


def test_actions_before_commit_multiple_commit_kinds_uses_first_match():
    actions = [
        ActionRecord(kind="probe"),
        ActionRecord(kind="finalize"),
        ActionRecord(kind="commit"),
    ]
    # "finalize" is also a commit-kind here -> first match at index 1
    assert actions_before_commit(actions, {"commit", "finalize"}) == 1


def test_actions_before_commit_overlapping_investigative_and_commit_kinds():
    # A kind appearing in both sets is still "committing" the moment it
    # appears; actions_before_commit only cares about commit_kinds.
    actions = [
        ActionRecord(kind="probe"),
        ActionRecord(kind="dual"),
        ActionRecord(kind="probe"),
    ]
    assert actions_before_commit(actions, {"dual"}) == 1
    assert info_seeking_count(actions, {"dual", "probe"}) == 3
