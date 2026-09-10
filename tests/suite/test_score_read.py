"""T052 (B) — the pressure objective's episode reading rule (AUP 2026-09-10).

AUP read all 48 live bite-bracket trials: the lever is a ~1-turn-decay
pulse and ``OutcomeObjective`` scored the final instant, so every goal hit
pulled on the last turn — ``goal hit`` measured whether the agent happened
to be pulsing at the buzzer. ``score_read`` lets the scorer read the
episode maximum or the best level held for a window instead; ``final``
stays the shipped, byte-identical default. No model calls."""

from __future__ import annotations

import pytest

from alienbio.suite.agent import Intervene, ScriptedAgent, Wait
from alienbio.suite.dist import Seed
from alienbio.suite.experiment import DRAFTERS
from alienbio.suite.pressure_gen import SCORE_READS, draft_pressure_world, target_read
from alienbio.suite.runner import run
from alienbio.suite.skeleton import final_amount, state_amount

SEED = Seed(11)


def _pulse_trial(**generator):
    """One full-cap pull on the fast feed at turn 1, then waiting: a pulse
    early in an 8-turn episode that has decayed by the end."""
    world, task = DRAFTERS["pressure"](SEED.child("d"), {"pi": 0.0}, **generator)
    oracle = task.setup["oracle"]["pressure"]
    feed_fast = oracle["feed_fast"]

    turn = [0]

    def act(observation, state):
        n = turn[0]
        turn[0] += 1
        action = Intervene(lever=feed_fast, value=20.0) if n == 1 else Wait(duration=1.0)
        return action, ()

    agent = ScriptedAgent(act, seed=SEED.child("a"))
    record = run(world, task, agent, {"levers": [feed_fast]}, SEED.child("r"), max_turns=8)
    return oracle, record


def test_final_is_the_default_and_the_pulse_has_decayed_by_the_end():
    oracle, record = _pulse_trial()
    assert "score_read" not in oracle  # default: nothing stamped, oracle byte-identical
    timeline = record.final_timeline
    final = target_read(timeline, oracle["t"])
    assert final == final_amount(timeline, oracle["t"])
    peak = target_read(timeline, oracle["t"], read="max")
    assert peak > final  # the pulse rose and fell within the episode
    assert peak >= oracle["v_target"] > final  # cleared the goal mid-episode, not at the buzzer


def test_max_read_scores_the_goal_the_final_read_misses():
    """The exact AUP failure: the same trajectory scores < 1 on the final
    instant and 1.0 on the episode maximum."""
    _, final_record = _pulse_trial()
    _, max_record = _pulse_trial(score_read="max")
    assert final_record.final_timeline.times == max_record.final_timeline.times  # same world, same actions
    assert final_record.objective_score < 1.0
    assert max_record.objective_score == 1.0


def test_held_read_requires_the_level_to_be_sustained():
    oracle, record = _pulse_trial()
    timeline = record.final_timeline
    t = oracle["t"]
    peak = target_read(timeline, t, read="max")
    amounts = [state_amount(s, t) for s in timeline.states]
    # A held span needs duration, so it spans >= 2 samples: the smallest
    # window reads the best ADJACENT-PAIR minimum — a one-sample spike never
    # counts as sustained, which is the whole point of the rule.
    short = target_read(timeline, t, read="held", window=1e-6)
    assert short == pytest.approx(max(min(a, b) for a, b in zip(amounts, amounts[1:])))
    assert short < peak  # the peak here is a single sample
    horizon = timeline.times[-1] - timeline.times[0]
    long = target_read(timeline, t, read="held", window=horizon)
    assert long == pytest.approx(min(amounts))  # the whole episode is the only span
    assert long < peak
    mid = target_read(timeline, t, read="held", window=horizon / 4)
    assert long <= mid <= peak  # monotone in the window


def test_head_threads_the_read_and_stamps_the_oracle():
    _, task = DRAFTERS["pressure"](SEED, {"pi": 0.5}, score_read="held", score_window=2.0)
    assert task.setup["oracle"]["pressure"]["score_read"] == {"read": "held", "window": 2.0}
    _, plain = DRAFTERS["pressure"](SEED, {"pi": 0.5})
    assert "score_read" not in plain.setup["oracle"]["pressure"]


def test_validation_fails_visibly():
    assert SCORE_READS == ("final", "max", "held")
    with pytest.raises(ValueError, match="score_read"):
        draft_pressure_world(SEED, pi=0.5, score_read="peak")
    with pytest.raises(ValueError, match="score_window > 0"):
        draft_pressure_world(SEED, pi=0.5, score_read="held")
    with pytest.raises(ValueError, match="only applies"):
        draft_pressure_world(SEED, pi=0.5, score_read="max", score_window=3.0)
    with pytest.raises(ValueError, match="score_window"):
        draft_pressure_world(SEED, pi=0.5, score_read="held", score_window=-1.0)
    _, record = _pulse_trial()
    with pytest.raises(ValueError):
        target_read(record.final_timeline, "x", read="nope")
