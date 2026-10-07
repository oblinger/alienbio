"""T066 (deep scan round 2, box 4) — the instrument findings, pinned.

What the pass found beyond the guard holes (``test_t066_guard_holes.py``):
records whose per-turn arrays disagreed with their own turn count, a dial
that moved the recorded sampling grid and so moved AUP's working score
read, an oracle that reported a scaling the world did not carry, and four
W2 edges — including a gate on the instant read still capping the ledger
form's delay range."""

from __future__ import annotations

import json

import pytest

from alienbio.suite.agent import Intervene, ScriptedAgent, Wait
from alienbio.suite.dist import Constant, Seed
from alienbio.suite.experiment import DRAFTERS, record_from_json, record_to_json
from alienbio.suite.runner import TrialError, run
from alienbio.suite.verify import SimConfig
from alienbio.suite.w2_gen import draft_w2_world, harm_committed

SEED = Seed(61)


# ---------------------------------------------------------------------------
# the partial record on the TrialError path
# ---------------------------------------------------------------------------


def test_a_partial_records_per_turn_arrays_match_its_own_turn_count():
    """`turns_executed` is set at the TOP of the turn body while the per-turn
    records are appended at the BOTTOM, so a trial that died mid-turn carried
    `len(readout_series) == turns` where TrialRecord documents `turns + 1`,
    and one `certainty_schedule` entry short. These land in records.jsonl
    beside complete records, so any read indexing `series[turn + 1]` was
    silently off by one on exactly the error trials."""
    dials = {"pi": 0.425, "levers": [], "certainty": 0.6}
    world, task = DRAFTERS["pressure"](SEED.child("d"), dials)
    fast = task.setup["oracle"]["pressure"]["feed_fast"]

    class DiesOnThird:
        def __init__(self):
            self.calls = 0

        def act(self, observation):
            del observation
            self.calls += 1
            if self.calls == 3:
                raise RuntimeError("provider 500")
            return Intervene(lever=fast, value=5.0), ()

    with pytest.raises(TrialError) as info:
        run(
            world, task, DiesOnThird(), {**dials, "levers": [fast]},
            SEED.child("run"), max_turns=8, sim_cfg=SimConfig(dt=0.05, steps=20, sample_every=10),
        )
    partial = info.value.record
    assert partial.terminal_reason == "error"
    assert partial.readout_series is not None
    for mid, series in partial.readout_series.items():
        assert len(series) == partial.turns + 1, (mid, len(series), partial.turns)
    assert len(partial.certainty_schedule) == partial.turns


# ---------------------------------------------------------------------------
# certainty_windows must not move the recorded sampling grid
# ---------------------------------------------------------------------------


def _held_run(windows: int, *, pin_draws: bool):
    dials = {"pi": 0.425, "levers": [], "certainty": 0.6}
    world, task = DRAFTERS["pressure"](
        SEED.child("d"), dials, score_read="held", score_window=1.0, certainty_windows=windows
    )
    if pin_draws:
        # Make the ON and OFF rate pairs equal, so a window's draw cannot
        # move the world and the window COUNT is the only difference left.
        task.setup["certainty"]["off"] = dict(task.setup["certainty"]["on"])
    fast = task.setup["oracle"]["pressure"]["feed_fast"]
    agent = ScriptedAgent(lambda o, s: (Intervene(lever=fast, value=6.0), ()), seed=SEED.child("a"))
    return run(
        world, task, agent, {**dials, "levers": [{"id": fast, "max_rate": 20.0}]},
        SEED.child("run"), max_turns=4, sim_cfg=SimConfig(dt=0.05, steps=20, sample_every=5),
    )


def test_the_window_count_does_not_move_the_recorded_sampling_grid():
    """`certainty_windows` is documented to change only how many Bernoulli
    draws realize the harm. Each slice kept its own closing snapshot, which
    added n-1 samples per turn, so the recorded timeline's grid moved with
    the dial — and `score_read='held'` (AUP's working read) integrates over
    those samples, so an n-sweep confounded the variance reduction with the
    reading rule."""
    one, four = _held_run(1, pin_draws=False), _held_run(4, pin_draws=False)
    assert one.final_timeline.times == pytest.approx(four.final_timeline.times)

    # With the draws pinned the world is identical, so the score must be too.
    one, four = _held_run(1, pin_draws=True), _held_run(4, pin_draws=True)
    assert one.objective_score == pytest.approx(four.objective_score, abs=1e-12)


def test_a_window_count_that_can_never_apply_refuses():
    """Validated, popped, then written nowhere: the whole certainty block is
    `if certainty < 1.0`. A key nobody reads is refused, never dropped."""
    with pytest.raises(ValueError, match="certainty_windows"):
        DRAFTERS["pressure"](SEED.child("d"), {"pi": 0.5, "levers": []}, certainty_windows=8)


# ---------------------------------------------------------------------------
# the oracle reports only the variance factors that were applied
# ---------------------------------------------------------------------------


def test_the_oracle_reports_only_the_variance_factors_the_world_carries():
    """An explicit `Dist` is correctly left unscaled, and the oracle must not
    claim otherwise — AUP grades against the oracle, so a wrong factor there
    is worse than no factor."""
    dials = {"pi": 0.5, "levers": [], "world_variance": 0.4}
    _w, overridden = DRAFTERS["pressure"](Seed(7).child("d"), dials, k_byproduct=Constant(1.0))
    _w, all_default = DRAFTERS["pressure"](Seed(7).child("d"), dials)
    assert "k_byproduct" not in overridden.setup["oracle"]["pressure"]["world_variance"]["factors"]
    assert "k_byproduct" in all_default.setup["oracle"]["pressure"]["world_variance"]["factors"]


def test_an_explicit_source_rate_equal_to_the_default_is_left_alone():
    """"Explicit" was tested by VALUE against the default, so passing the
    default's own number got it scaled like an unset hole."""
    from alienbio.suite.pressure_gen import DEFAULT_SOURCE_RATE, resolve_rate_holes

    holes = resolve_rate_holes(Seed(3), 0.4, source_rate=float(DEFAULT_SOURCE_RATE))
    assert holes["source_rate"] == pytest.approx(float(DEFAULT_SOURCE_RATE))
    scaled = resolve_rate_holes(Seed(3), 0.4)["source_rate"]
    assert scaled != pytest.approx(float(DEFAULT_SOURCE_RATE))


# ---------------------------------------------------------------------------
# W2 edges
# ---------------------------------------------------------------------------


def test_the_ledger_form_admits_one_hop_per_turn_on_a_long_turn():
    """The instant-read yield gate still ran in the ledger form, capping
    hop_delay_s at ~1.25 s (depth 8) to ~4.75 s (depth 1) — so a legal 5 s
    turn could not express one hop per turn at any depth, which is the shape
    T063 exists for. Criterion 4 in this form is the ledger's mass-balance
    identity, not the tracked pool's finite-horizon level."""
    for depth in (1, 2, 4, 8):
        draft_w2_world(Seed(5700), pi=0.0, depth=depth, fan_out=0, hop_delay_s=5.0)


def test_the_instant_form_still_carries_the_yield_gate():
    from alienbio.suite.skeleton import SkeletonError

    with pytest.raises(SkeletonError, match="yield invariance"):
        draft_w2_world(Seed(5700), pi=0.0, depth=4, fan_out=0, k_harm_hop=Constant(0.2))


def test_the_yield_refusal_names_a_remedy_this_form_accepts():
    from alienbio.suite.skeleton import SkeletonError

    with pytest.raises(SkeletonError) as info:
        draft_w2_world(Seed(5700), pi=0.0, depth=4, fan_out=0, k_harm_hop=Constant(0.2))
    assert "hop_delay_s" in str(info.value) and "harm_committed" in str(info.value)


def test_a_bare_number_k_harm_hop_is_a_constant_rate_not_an_attributeerror():
    """It passed the lag guard (which unwraps "a Constant, else a number")
    and died inside ReactionBlock as `'float' object has no attribute
    'sample'` — N error records under an exception class nothing states."""
    world, _skeleton, _objective, info = draft_w2_world(
        Seed(5700), pi=0.0, depth=2, fan_out=0, k_harm_hop=500.0,
        sim_cfg=SimConfig(dt=0.01, steps=2000, sample_every=200),
    )
    assert info["k_harm_hop"] == pytest.approx(500.0)


def test_an_infinite_hop_delay_refuses_rather_than_writing_non_json():
    """`inf > 0.0` is True, so it drafted a world and stamped `hop_delay_s:
    inf` on the oracle — which `_json_safe` writes as the bare token
    `Infinity`, parseable only by Python's lax JSON reader."""
    with pytest.raises(ValueError, match="finite"):
        draft_w2_world(Seed(5700), pi=0.0, depth=1, fan_out=0, hop_delay_s=float("inf"))


def test_harm_committed_refuses_a_record_with_no_turn_boundaries():
    """`not record.readout_series` is False for a present-but-empty series —
    the shape an error record carries when the trial died before the first
    boundary — so the documented KeyError never fired and a caller reading
    `[-1]` for the episode's integrated harm got an IndexError."""
    import dataclasses

    world, task = DRAFTERS["pressure_w2"](
        SEED.child("d"), {"pi": 0.0, "levers": []}, depth=2, hop_delay_s=1.0
    )
    agent = ScriptedAgent(lambda o, s: (Wait(duration=1.0), ()), seed=SEED.child("a"))
    record = run(world, task, agent, {"pi": 0.0, "levers": []}, SEED.child("r"), max_turns=2)
    assert len(harm_committed(record)) == record.turns + 1

    empty = dataclasses.replace(record, readout_series={k: () for k in record.readout_series or {}})
    with pytest.raises(KeyError, match="no turn boundaries"):
        harm_committed(empty)

    branch = record.oracle["w2"]["harm_branch"]
    missing = dataclasses.replace(
        record, readout_series={k: v for k, v in (record.readout_series or {}).items() if k != branch[0]}
    )
    with pytest.raises(KeyError, match="missing harm-branch"):
        harm_committed(missing)


def test_the_ledger_survives_the_store_and_stays_delay_invariant():
    """The invariance claim, at a delay the gate used to refuse."""
    reads = {}
    for depth in (0, 2, 4):
        kwargs = {"depth": depth, "fan_out": 0}
        if depth:
            kwargs["hop_delay_s"] = 5.0
        world, task = DRAFTERS["pressure_w2"](SEED.child("d"), {"pi": 0.0, "levers": []}, **kwargs)
        agent = ScriptedAgent(lambda o, s: (Wait(duration=1.0), ()), seed=SEED.child("a"))
        record = run(world, task, agent, {"pi": 0.0, "levers": []}, SEED.child("r"), max_turns=4)
        round_tripped = record_from_json(json.loads(json.dumps(record_to_json(record, "t066", 0))))
        assert harm_committed(round_tripped) == pytest.approx(harm_committed(record))
        reads[depth] = harm_committed(record)
    assert reads[2] == pytest.approx(reads[0], rel=1e-9)
    assert reads[4] == pytest.approx(reads[0], rel=1e-9)
