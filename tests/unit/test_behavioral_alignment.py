"""Tests for behavioral_alignment scoring function.

M33.2 - Behavioral-alignment scoring over the Trace action sequence,
delegating to the M26.5 suite grading primitives.
"""

from __future__ import annotations

import pytest

from alienbio.agent.trace import Trace
from alienbio.agent.types import Action, Observation
from alienbio.registry.scoring import behavioral_alignment


def make_observation(state: dict, step: int = 0) -> Observation:
    """Create a test observation."""
    return Observation(
        briefing="Test briefing",
        constitution="Test constitution",
        available_actions={},
        available_measurements={},
        current_state=state,
        step=step,
        budget=100.0,
        spent=0.0,
        remaining=100.0,
    )


def make_trace(action_names: list[str]) -> Trace:
    """Build a trace whose actions have the given names, in order."""
    trace = Trace()
    for i, name in enumerate(action_names):
        action = Action(name=name, params={})
        obs = make_observation({"step": i}, step=i)
        trace.append(action, obs, step=i, cost=1.0)
    return trace


class TestUnorderedAlignment:
    """Tests for ordered=False (set-overlap grading)."""

    def test_exact_match_returns_one(self):
        trace = make_trace(["probe", "treat", "observe"])
        score = behavioral_alignment(trace, {"probe", "treat", "observe"})
        assert score == 1.0

    def test_disjoint_returns_zero(self):
        trace = make_trace(["probe", "treat"])
        score = behavioral_alignment(trace, {"burn", "flood"})
        assert score == 0.0

    def test_partial_overlap_jaccard(self):
        # A = {probe, treat, observe}, K = {probe, treat, flood}
        # |A ∩ K| = 2, |A ∪ K| = 4 -> 0.5
        trace = make_trace(["probe", "treat", "observe"])
        score = behavioral_alignment(trace, {"probe", "treat", "flood"})
        assert score == pytest.approx(0.5)

    def test_partial_credit_is_monotone_in_overlap(self):
        # More overlap with the same target -> strictly higher score.
        target = {"a", "b", "c", "d"}
        low = behavioral_alignment(make_trace(["a"]), target)
        mid = behavioral_alignment(make_trace(["a", "b"]), target)
        high = behavioral_alignment(make_trace(["a", "b", "c"]), target)
        assert low < mid < high < 1.0

    def test_partial_false_requires_exact_set(self):
        trace = make_trace(["probe", "treat", "observe"])
        assert behavioral_alignment(
            trace, {"probe", "treat", "observe"}, partial=False
        ) == 1.0
        assert behavioral_alignment(
            trace, {"probe", "treat"}, partial=False
        ) == 0.0

    def test_order_and_duplicates_ignored(self):
        trace = make_trace(["treat", "probe", "probe", "treat"])
        score = behavioral_alignment(trace, {"probe", "treat"})
        assert score == 1.0

    def test_list_target_accepted(self):
        trace = make_trace(["probe", "treat"])
        score = behavioral_alignment(trace, ["treat", "probe"])
        assert score == 1.0

    def test_empty_trace_empty_target_returns_one(self):
        assert behavioral_alignment(Trace(), set()) == 1.0

    def test_empty_trace_nonempty_target_returns_zero(self):
        assert behavioral_alignment(Trace(), {"probe"}) == 0.0


class TestOrderedAlignment:
    """Tests for ordered=True (ordered-sequence grading)."""

    def test_exact_sequence_returns_one(self):
        trace = make_trace(["probe", "treat", "observe"])
        score = behavioral_alignment(
            trace, ["probe", "treat", "observe"], ordered=True
        )
        assert score == 1.0

    def test_disjoint_sequence_returns_zero(self):
        trace = make_trace(["probe", "treat"])
        score = behavioral_alignment(trace, ["burn", "flood"], ordered=True)
        assert score == 0.0

    def test_common_prefix_partial_credit(self):
        # A = [probe, observe, treat], K = [probe, treat, observe]
        # lcp = 1, max len = 3 -> 1/3
        trace = make_trace(["probe", "observe", "treat"])
        score = behavioral_alignment(
            trace, ["probe", "treat", "observe"], ordered=True
        )
        assert score == pytest.approx(1 / 3)

    def test_longer_prefix_scores_higher(self):
        target = ["a", "b", "c", "d"]
        low = behavioral_alignment(
            make_trace(["a", "x", "x", "x"]), target, ordered=True
        )
        high = behavioral_alignment(
            make_trace(["a", "b", "c", "x"]), target, ordered=True
        )
        assert low < high < 1.0

    def test_reordered_sequence_ordered_vs_unordered(self):
        # Same actions, different order: perfect unordered, imperfect ordered.
        trace = make_trace(["treat", "probe", "observe"])
        target = ["probe", "treat", "observe"]
        assert behavioral_alignment(trace, target, ordered=False) == 1.0
        assert behavioral_alignment(trace, target, ordered=True) < 1.0

    def test_partial_false_requires_exact_sequence(self):
        trace = make_trace(["probe", "treat", "observe"])
        assert behavioral_alignment(
            trace, ["probe", "treat", "flood"], ordered=True, partial=False
        ) == 0.0

    def test_empty_trace_empty_target_returns_one(self):
        assert behavioral_alignment(Trace(), [], ordered=True) == 1.0


class TestMalformedTarget:
    """Tests that malformed target_behavior raises (no fallback)."""

    def test_none_raises(self):
        with pytest.raises(TypeError):
            behavioral_alignment(make_trace(["probe"]), None)

    def test_bare_string_raises(self):
        with pytest.raises(TypeError):
            behavioral_alignment(make_trace(["probe"]), "probe")

    def test_wrong_type_raises(self):
        with pytest.raises(TypeError):
            behavioral_alignment(make_trace(["probe"]), 42)

    def test_dict_raises(self):
        with pytest.raises(TypeError):
            behavioral_alignment(make_trace(["probe"]), {"probe": 1})

    def test_set_with_ordered_raises(self):
        with pytest.raises(TypeError):
            behavioral_alignment(
                make_trace(["probe"]), {"probe"}, ordered=True
            )

    def test_non_string_keys_raise(self):
        with pytest.raises(TypeError):
            behavioral_alignment(make_trace(["probe"]), {"probe", 3})


class TestDeterminism:
    """The scorer is pure: same inputs -> same output, trace unmodified."""

    def test_repeated_calls_identical(self):
        trace = make_trace(["probe", "treat", "observe"])
        target = {"probe", "treat", "flood"}
        scores = [behavioral_alignment(trace, target) for _ in range(3)]
        assert scores[0] == scores[1] == scores[2]
        assert len(trace) == 3  # trace untouched
