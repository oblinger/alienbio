"""Acceptance tests for TrialRecord + condition_key + reasoning-step threading
(F020, Phase-2 D2)."""

from __future__ import annotations

import dataclasses

import pytest

from alienbio.suite.agent import Commit, Intervene, Measure, ReasoningStep
from alienbio.suite.deliberation import DeliberationTrace
from alienbio.suite.info_seeking import ActionRecord
from alienbio.suite.reliability_grid import aggregate_cells
from alienbio.suite.trial import TrialRecord, condition_key, thread_reasoning_steps
from alienbio.suite.types import Answer, Timeline


def _record(task_id: str, dials: dict, score: float, action_log=()) -> TrialRecord:
    return TrialRecord(
        task_id=task_id,
        condition_key=condition_key(dials),
        final_timeline=Timeline(times=(0.0,), states=()),
        deliberation_trace=DeliberationTrace(),
        action_log=action_log,
        objective_score=score,
    )


# ═══════════════════════════════════════════════════════════════════════════
# condition_key
# ═══════════════════════════════════════════════════════════════════════════


def test_condition_key_sorts_by_dial_name():
    key = condition_key({"pressure": "hi", "noise": "lo"})
    assert key == (("noise", "lo"), ("pressure", "hi"))


def test_condition_key_normalises_regardless_of_input_order():
    key_a = condition_key({"noise": "lo", "pressure": "hi"})
    key_b = condition_key({"pressure": "hi", "noise": "lo"})
    assert key_a == key_b


# ═══════════════════════════════════════════════════════════════════════════
# TrialRecord immutability
# ═══════════════════════════════════════════════════════════════════════════


def test_trial_record_is_frozen():
    record = _record("task-1", {"noise": "lo"}, 1.0)
    with pytest.raises(dataclasses.FrozenInstanceError):
        record.objective_score = 0.5  # type: ignore[misc]


# ═══════════════════════════════════════════════════════════════════════════
# condition_key round-trips through reliability_grid.aggregate_cells, no adapter
# ═══════════════════════════════════════════════════════════════════════════


def test_condition_key_bins_through_aggregate_cells_with_no_adapter():
    r1 = _record("t1", {"noise": "lo", "pressure": "lo"}, 1.0)
    r2 = _record("t2", {"noise": "lo", "pressure": "lo"}, 0.5)
    r3 = _record("t3", {"noise": "hi", "pressure": "lo"}, 0.0)

    cells = aggregate_cells(
        [(r.condition_key, r.objective_score) for r in (r1, r2, r3)]
    )

    lo_lo = condition_key({"noise": "lo", "pressure": "lo"})
    hi_lo = condition_key({"noise": "hi", "pressure": "lo"})

    assert cells[lo_lo].n == 2
    assert cells[lo_lo].mean == pytest.approx(0.75)
    assert cells[hi_lo].n == 1
    assert cells[hi_lo].mean == pytest.approx(0.0)


# ═══════════════════════════════════════════════════════════════════════════
# Reasoning-step threading into DeliberationTrace (1:1, turn/action tagged)
# ═══════════════════════════════════════════════════════════════════════════


def test_thread_reasoning_steps_1to1_turn_and_action_tagged():
    trace = DeliberationTrace()
    steps = (
        ReasoningStep(kind="policy", content="fired Measure", refs=("probe_x",)),
    )
    action = Measure(probe="probe_x")

    updated = thread_reasoning_steps(trace, turn=2, action=action, reasoning_steps=steps)

    assert trace.steps == ()  # original unchanged
    assert updated.depth() == 1
    step = updated.steps[0]
    assert step.turn == 2
    assert step.kind == "policy"
    assert step.content == "fired Measure"
    assert "probe_x" in step.refs
    assert "measure" in step.refs  # action-type tag


def test_thread_reasoning_steps_appends_multiple_steps_in_order_across_turns():
    trace = DeliberationTrace()
    trace = thread_reasoning_steps(
        trace,
        turn=0,
        action=Intervene(lever="pump_rate", value=2.0),
        reasoning_steps=(ReasoningStep(kind="policy", content="a"),),
    )
    trace = thread_reasoning_steps(
        trace,
        turn=1,
        action=Commit(answer=Answer(value="done", kind="scalar")),
        reasoning_steps=(
            ReasoningStep(kind="policy", content="b1"),
            ReasoningStep(kind="policy", content="b2"),
        ),
    )
    assert trace.depth() == 3
    assert [s.turn for s in trace.steps] == [0, 1, 1]
    assert [s.content for s in trace.steps] == ["a", "b1", "b2"]
    assert "intervene" in trace.steps[0].refs
    assert "commit" in trace.steps[1].refs
    assert "commit" in trace.steps[2].refs


# ═══════════════════════════════════════════════════════════════════════════
# Lazy diagnostic-scorer accessors (Q3 = C)
# ═══════════════════════════════════════════════════════════════════════════


def test_deliberation_depth_cached_property_matches_trace_depth():
    trace = DeliberationTrace()
    trace = thread_reasoning_steps(
        trace,
        turn=0,
        action=Measure(probe="probe_x"),
        reasoning_steps=(ReasoningStep(kind="policy", content="a"),),
    )
    record = TrialRecord(
        task_id="t1",
        condition_key=condition_key({"noise": "lo"}),
        final_timeline=Timeline(times=(0.0,), states=()),
        deliberation_trace=trace,
        action_log=(),
        objective_score=1.0,
    )
    assert record.deliberation_depth == 1


def test_info_seeking_and_destructive_rate_lazily_recomputed_over_action_log():
    action_log = (
        ActionRecord(kind="measure", destructive=False),
        ActionRecord(kind="measure", destructive=False),
        ActionRecord(kind="commit", destructive=True),
    )
    record = _record("t1", {"noise": "lo"}, 1.0, action_log=action_log)

    assert record.info_seeking_ratio({"measure"}) == pytest.approx(2 / 3)
    assert record.destructive_rate() == pytest.approx(1 / 3)
    assert record.actions_before_commit({"commit"}) == 2
