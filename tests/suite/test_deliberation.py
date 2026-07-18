"""Acceptance tests for the deliberation-trace capture data model (M33.1)."""

from __future__ import annotations

from alienbio.suite.deliberation import DeliberationStep, DeliberationTrace


def _trace() -> DeliberationTrace:
    """A small hand-built trace spanning 3 turns, mixed kinds, repeated refs.

    turn 0: reason step refs ("obj1",)
    turn 0: act step refs ("obj2",)           (same turn as above)
    turn 1: reason step refs ("obj1", "obj3")  (obj1 re-referenced later)
    turn 2: observe step refs ()               (no refs)
    """
    steps = (
        DeliberationStep(turn=0, kind="reason", content="thinking a", refs=("obj1",)),
        DeliberationStep(turn=0, kind="act", content="doing a", refs=("obj2",)),
        DeliberationStep(turn=1, kind="reason", content="thinking b", refs=("obj1", "obj3")),
        DeliberationStep(turn=2, kind="observe", content="seeing c", refs=()),
    )
    return DeliberationTrace(steps=steps)


def test_append_returns_new_instance_and_leaves_original_unchanged():
    original = DeliberationTrace()
    step = DeliberationStep(turn=0, kind="reason", content="x")
    updated = original.append(step)

    assert updated is not original
    assert original.steps == ()
    assert updated.steps == (step,)


def test_extend_returns_new_instance_and_leaves_original_unchanged():
    step0 = DeliberationStep(turn=0, kind="reason", content="x")
    original = DeliberationTrace(steps=(step0,))
    step1 = DeliberationStep(turn=1, kind="act", content="y")
    step2 = DeliberationStep(turn=2, kind="observe", content="z")
    updated = original.extend([step1, step2])

    assert updated is not original
    assert original.steps == (step0,)
    assert updated.steps == (step0, step1, step2)


def test_steps_of_kind_filters_and_preserves_order():
    trace = _trace()
    reason_steps = trace.steps_of_kind("reason")

    assert [s.content for s in reason_steps] == ["thinking a", "thinking b"]
    assert trace.steps_of_kind("act") == (trace.steps[1],)
    assert trace.steps_of_kind("nonexistent") == ()


def test_first_ref_turn_earliest_and_absent():
    trace = _trace()

    assert trace.first_ref_turn("obj1") == 0  # earliest turn, even though re-referenced at turn 1
    assert trace.first_ref_turn("obj2") == 0
    assert trace.first_ref_turn("obj3") == 1
    assert trace.first_ref_turn("obj_missing") is None


def test_refs_by_turn_merges_refs_sharing_a_turn():
    trace = _trace()
    by_turn = trace.refs_by_turn()

    assert by_turn == {
        0: frozenset({"obj1", "obj2"}),
        1: frozenset({"obj1", "obj3"}),
        2: frozenset(),
    }


def test_all_refs_is_the_union():
    trace = _trace()
    assert trace.all_refs() == frozenset({"obj1", "obj2", "obj3"})


def test_depth_counts_steps():
    trace = _trace()
    assert trace.depth() == 4
    assert DeliberationTrace().depth() == 0


def test_frozen_dataclasses_are_hashable_and_usable_in_a_set():
    step_a = DeliberationStep(turn=0, kind="reason", content="x", refs=("r1",))
    step_b = DeliberationStep(turn=0, kind="reason", content="x", refs=("r1",))
    step_c = DeliberationStep(turn=1, kind="act", content="y")

    assert hash(step_a) == hash(step_b)
    assert step_a == step_b
    assert len({step_a, step_b, step_c}) == 2

    trace_a = DeliberationTrace(steps=(step_a,))
    trace_b = DeliberationTrace(steps=(step_b,))
    assert hash(trace_a) == hash(trace_b)
    assert len({trace_a, trace_b}) == 1
