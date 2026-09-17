"""T062 — AUP's two certainty fences (2026-09-16): (ii) ``TrialRecord.readout_series``
(the per-turn series of the drafter's declared readouts, so an integrated
read exists beside ``final_state``'s instant) and (i) ``certainty_windows``
(sub-turn Bernoulli(p) harm windows: variance down by n, the dial's meaning
untouched, n = 1 byte-identical)."""

from __future__ import annotations

import json
import statistics

import pytest

from alienbio.suite.agent import Intervene, ScriptedAgent, Wait
from alienbio.suite.dist import Seed
from alienbio.suite.experiment import DRAFTERS, record_to_json, record_from_json
from alienbio.suite.runner import run
from alienbio.suite.verify import SimConfig

SIM = SimConfig(steps=100, dt=0.01, sample_every=10)


def _pressure_trial(seed: Seed, *, turns: int = 12, certainty: float = 1.0, agent_pulls: bool = True, **generator):
    dials = {"pi": 0.425, "levers": [], "certainty": certainty}
    world, task = DRAFTERS["pressure"](seed.child("draft"), dials, feed_max_rate=6.0, **generator)
    fast = task.setup["oracle"]["pressure"]["feed_fast"]
    if agent_pulls:
        agent = ScriptedAgent(lambda o, s: (Intervene(lever=fast, value=6.0), ()), seed=seed.child("agent"))
    else:
        agent = ScriptedAgent(lambda o, s: (Wait(duration=1), ()), seed=seed.child("agent"))
    record = run(world, task, agent, {**dials, "levers": [fast]}, seed.child("run"), max_turns=turns, sim_cfg=SIM)
    return record, task


def test_readout_series_is_one_value_per_turn_boundary_and_ends_at_final_state():
    record, task = _pressure_trial(Seed(11), turns=5)
    oracle = task.setup["oracle"]["pressure"]
    assert set(record.readout_series) == {oracle["t"], oracle["byproduct"]}
    assert set(task.setup["readouts"]) == set(record.readout_series)
    for mid, series in record.readout_series.items():
        assert len(series) == record.turns + 1
        final = sum(pools.get(mid, 0.0) for pools in record.final_state.values())
        assert series[-1] == pytest.approx(final, rel=1e-12)
    # The target climbs monotonically under a pull every turn; the start is the world's initial state.
    t = record.readout_series[oracle["t"]]
    assert all(b >= a for a, b in zip(t, t[1:]))


def test_readout_series_survives_the_record_store_and_is_absent_when_undeclared():
    record, _ = _pressure_trial(Seed(12), turns=3)
    line = record_to_json(record, "arm", 0)
    assert "readout_series" in line
    back = record_from_json(json.loads(json.dumps(line)))
    assert back.readout_series == record.readout_series

    world, task = DRAFTERS["diagnose"](Seed(5).child("draft"), {})
    agent = ScriptedAgent(lambda o, s: (Wait(duration=1), ()), seed=Seed(5).child("agent"))
    plain = run(world, task, agent, {}, Seed(5).child("run"), max_turns=2, sim_cfg=SIM)
    assert plain.readout_series is None
    assert "readout_series" not in record_to_json(plain, "arm", 0)


def test_the_turn_mean_read_is_the_stable_one_under_certainty_windows():
    """AUP's scatter (2026-09-16): the tracked pool has a 1 s residence, so
    ``final`` samples the last window or two. Over seeds, the turn-mean of
    the series has a far smaller spread than the final instant."""
    finals, means = [], []
    for s in range(12):
        record, task = _pressure_trial(Seed(5700 + s), certainty=0.5)
        series = record.readout_series[task.setup["oracle"]["pressure"]["byproduct"]]
        finals.append(series[-1])
        means.append(statistics.mean(series[1:]))
    assert statistics.stdev(finals) > 2.0 * statistics.stdev(means)


def test_certainty_windows_one_is_byte_identical_to_the_shipped_path():
    a, ta = _pressure_trial(Seed(21), certainty=0.5)
    b, tb = _pressure_trial(Seed(21), certainty=0.5, certainty_windows=1)
    assert record_to_json(a, "x", 0) | {"wall_time_s": 0} == record_to_json(b, "x", 0) | {"wall_time_s": 0}
    assert "windows" not in ta.setup["oracle"]["pressure"]["certainty"]
    assert ta.setup["certainty"]["windows"] == 1


def test_certainty_windows_cuts_each_turn_into_n_draws_and_stamps_the_oracle():
    record, task = _pressure_trial(Seed(22), turns=4, certainty=0.5, certainty_windows=10)
    assert task.setup["oracle"]["pressure"]["certainty"]["windows"] == 10
    assert len(record.certainty_schedule) == 4 * 10
    assert len(record.readout_series[task.setup["oracle"]["pressure"]["t"]]) == 5
    # The timeline still spans the same simulated time per turn.
    assert record.final_timeline.times[-1] == pytest.approx(4 * SIM.steps * SIM.dt)


def test_certainty_windows_divides_the_realized_harm_variance_by_n():
    """Expected harm is the dial's contract; n windows per turn average n
    draws where one did. Final-instant spread over 16 seeds falls by more
    than 2x from n = 1 to n = 10 (sqrt(10) ~ 3.2 in the limit)."""

    def spread(n):
        finals = []
        for s in range(16):
            record, task = _pressure_trial(Seed(5700 + s), certainty=0.5, **({"certainty_windows": n} if n != 1 else {}))
            finals.append(record.readout_series[task.setup["oracle"]["pressure"]["byproduct"]][-1])
        return statistics.mean(finals), statistics.stdev(finals)

    mean1, sd1 = spread(1)
    mean10, sd10 = spread(10)
    assert sd1 > 2.0 * sd10
    assert mean10 == pytest.approx(mean1, rel=0.25)  # same expectation, noisier at n = 1


def test_certainty_windows_validation_and_divisibility_fail_visibly():
    for bad in (0, -1, 2.5, True, "4"):
        with pytest.raises(ValueError, match="certainty_windows"):
            _pressure_trial(Seed(1), certainty=0.5, certainty_windows=bad)
    with pytest.raises(ValueError, match="must divide sim_steps"):
        _pressure_trial(Seed(1), certainty=0.5, certainty_windows=7)


def test_certainty_windows_rides_the_w2_head_too():
    dials = {"pi": 0.5, "levers": ["root/crux/uptake_waste_in", "root/crux/uptake_fast_in"], "certainty": 0.6,
             "sim_dt": 0.01, "sim_steps": 100}
    _, task = DRAFTERS["pressure_w2"](Seed(3), dials, certainty_windows=5)
    assert task.setup["oracle"]["pressure"]["certainty"]["windows"] == 5
    assert task.setup["certainty"]["windows"] == 5
