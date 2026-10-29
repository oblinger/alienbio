"""``ActionRecord``, the runner's logged action (the module's metrics were retired in T093)."""

from __future__ import annotations

import dataclasses

import pytest

from alienbio.suite.info_seeking import ActionRecord


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
