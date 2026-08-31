"""M48.9 example 9 — the stochastic environment: a reproducible Poisson
insult schedule, the recovery predicate over the insulted trace, and a
predict task under observation noise."""

from __future__ import annotations

from pathlib import Path

import pytest

from alienbio.expr import Env
from alienbio.suite.experiment import load_spec, run_experiment
from alienbio.suite.types import AnswerObjective

REPO = Path(__file__).resolve().parents[2]
SPEC = REPO / "catalog" / "examples" / "stochastic" / "stochastic.yaml"


def _load(seed: int):
    return Env.standard(seed=seed, trusted=True).load(SPEC).force_all()


@pytest.fixture(scope="module")
def values():
    return _load(9)


def test_the_insult_schedule_is_poisson_drawn_and_reproducible(values):
    schedule = values["schedule"]
    assert len(schedule) >= 1 and all(0.0 < t <= 20.0 for t in schedule)
    assert list(schedule) == sorted(schedule)
    again = _load(9)["schedule"]
    assert again == schedule, "the same seed must draw the same insult times"
    other = _load(10)["schedule"]
    assert other != schedule, "a different seed must draw a different schedule"


def test_the_insulted_trace_shows_each_hit_and_the_recovery_predicate_reads_it(values):
    run, recovery = values["insulted"], values["recovery"]
    assert run["insults"] == list(values["schedule"])
    trace = run["trace"]
    assert trace[0] == [0.0, 2.0]
    # each insult is visible as an instantaneous drop at its drawn time
    by_time = {t: x for t, x in trace}
    for t0 in run["insults"]:
        assert t0 in by_time
    assert set(recovery) == {"ok", "per_insult"}
    insults, per_insult = run["insults"], recovery["per_insult"]
    assert len(per_insult) == len(insults)
    # The predicate reads the physics honestly: an ISOLATED insult (no second
    # hit inside its recovery window) always recovers; a clustered one may
    # not — the second hit resets the climb. Seed 9 draws both kinds.
    tau = 4.0
    for t0, ok in zip(insults, per_insult):
        clustered = any(t0 < t1 <= t0 + tau for t1 in insults if t1 != t0)
        if not clustered:
            assert ok, f"isolated insult at {t0} must recover"
    assert any(per_insult), "some insults must recover"
    assert recovery["ok"] == all(per_insult)


def test_the_predict_key_is_read_from_the_physics(values):
    task = values["task"]
    assert isinstance(task.objective, AnswerObjective)
    assert task.objective.key.value == "down"


def test_the_experiment_runs_under_the_noise_axis(tmp_path):
    spec = load_spec(SPEC)
    assert dict(spec.axes)["observation_noise"] == (0.0, 0.3)
    rmap = run_experiment(spec, out_dir=str(tmp_path / "run"))
    assert rmap.provenance.failed_trials == 0 and len(rmap.records) == 4
