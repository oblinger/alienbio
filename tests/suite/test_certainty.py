"""T034 — the P2 certainty dial (AUP phase 2): stochastic harm with expected
harm held constant. The mechanism is a per-turn Bernoulli(p) harm window on
the pressure world's harm split, with the split's total drain conserved —
so the upstream trajectory is schedule-invariant (checked exactly), the
expected side-product equals the deterministic run's (analytic; confirmed by
Monte-Carlo within the stated tolerance), and the realized-harm variance is
strictly monotone as certainty falls (Monte-Carlo). Zero model calls."""

from __future__ import annotations

import statistics

import pytest

from alienbio.suite.agent import ScriptedAgent, Wait
from alienbio.suite.dist import Seed
from alienbio.suite.experiment import (
    DRAFTERS,
    GUARDED_DIALS,
    no_peeking_violation,
    record_from_json,
    record_to_json,
    spec_from_dict,
)
from alienbio.suite.runner import run

DRAFT_SEED = Seed(41)
BYPRODUCT = "root/crux/sink_byproduct_in"
INTERMEDIATE = "root/crux/route_byproduct_in"
PRECURSOR = "root/crux_precursor"


def _pool(record, molecule_id):
    for comp in record.final_state.values():
        if molecule_id in comp:
            return comp[molecule_id]
    raise AssertionError(f"{molecule_id} missing from final state")


def _trial(p, run_seed, *, max_turns=8):
    dials = {"levers": [], "pi": 0.5}
    if p is not None:
        dials["certainty"] = p
    world, task = DRAFTERS["pressure"](DRAFT_SEED.child("d"), dials)
    agent = ScriptedAgent(lambda o, s: (Wait(duration=1.0), ()), seed=run_seed.child("a"))
    return run(world, task, agent, dials, run_seed, max_turns=max_turns)


def test_certain_level_runs_the_shipped_code_path():
    """certainty = 1.0 is the deterministic reference (M45.3's removability
    shape): no schedule machinery — no setup entry, no oracle entry, an empty
    schedule, and the same final state as the dial-absent world."""
    absent = _trial(None, Seed(1))
    certain = _trial(1.0, Seed(1))
    assert certain.certainty_schedule == ()
    assert absent.certainty_schedule == ()
    assert "certainty" not in certain.oracle["pressure"]
    assert certain.final_state == absent.final_state

    world, task = DRAFTERS["pressure"](DRAFT_SEED.child("d"), {"levers": [], "pi": 0.5, "certainty": 1.0})
    assert "certainty" not in task.setup


def test_schedule_is_seed_deterministic_and_recorded():
    """Same (world, seed) -> the identical realized window schedule, on the
    record; different run seeds draw different schedules."""
    a = _trial(0.5, Seed(7))
    b = _trial(0.5, Seed(7))
    c = _trial(0.5, Seed(8))
    assert a.certainty_schedule == b.certainty_schedule
    assert len(a.certainty_schedule) == a.turns
    assert any(a.certainty_schedule) and not all(a.certainty_schedule)
    assert a.certainty_schedule != c.certainty_schedule or a.final_state != c.final_state


def test_upstream_trajectory_is_schedule_invariant():
    """The conserved total drain makes everything upstream of the harm split
    byte-identical to the deterministic run at every level — the noise
    reallocates the split, it never perturbs the world's supply side."""
    det = _trial(None, Seed(1))
    for p in (0.5, 0.25):
        for seed_v in (11, 12, 13):
            noisy = _trial(p, Seed(seed_v))
            assert _pool(noisy, INTERMEDIATE) == pytest.approx(_pool(det, INTERMEDIATE), abs=1e-9)
            assert _pool(noisy, PRECURSOR) == pytest.approx(_pool(det, PRECURSOR), abs=1e-9)


def test_expected_harm_invariant_and_variance_monotone():
    """The two P2 acceptance criteria, Monte-Carlo, zero model calls: the
    mean realized side-product matches the deterministic run within 4 standard
    errors (the stated tolerance; the invariance is analytic — total drain
    conserved makes the byproduct coordinate linear in the schedule), and the
    realized-harm spread strictly rises as certainty falls."""
    det = _pool(_trial(None, Seed(1)), BYPRODUCT)
    spreads = {}
    for p in (0.5, 0.25):
        vals = [_pool(_trial(p, Seed(2000 + i)), BYPRODUCT) for i in range(150)]
        mean, sd = statistics.mean(vals), statistics.stdev(vals)
        se = sd / len(vals) ** 0.5
        assert abs(mean - det) < 4 * se, (p, mean, det, se)
        spreads[p] = sd
    assert spreads[0.25] > spreads[0.5] > 0.0


def test_base_chemistry_is_level_invariant():
    """Orthogonality: the drafted world's rate constants (exchange rate,
    route lengths) are identical at every certainty level — the dial lives
    entirely in the runner's per-burst override."""
    def rates(p):
        dials = {"levers": [], "pi": 0.5}
        if p is not None:
            dials["certainty"] = p
        world, _task = DRAFTERS["pressure"](DRAFT_SEED.child("d"), dials)
        return {rid: float(r.rate) for rid, r in world.chemistry.reactions.items()}

    assert rates(None) == rates(0.5) == rates(0.25)


def test_oracle_holds_per_turn_expected_effects():
    """AUP's M4 truth rule survives: the oracle carries the EXPECTED branch
    rates (equal to the deterministic run's) and the ON-window rate, never a
    realized draw."""
    rec = _trial(0.5, Seed(3))
    certainty = rec.oracle["pressure"]["certainty"]
    assert certainty["p"] == 0.5
    assert certainty["expected_harm_rate"] == pytest.approx(
        certainty["on_harm_rate"] * certainty["p"]
    )
    assert certainty["harm_reaction"] != certainty["task_reaction"]


def test_validation_fails_visibly():
    for bad in (0.0, -0.5, 1.5, True):
        with pytest.raises(ValueError, match="certainty"):
            DRAFTERS["pressure"](DRAFT_SEED, {"levers": [], "pi": 0.5, "certainty": bad})
    # Below the world's floor k_harm/(k_harm+k_task) the ON task branch would
    # run backwards — refused at draft, naming the floor.
    with pytest.raises(ValueError, match="floor"):
        DRAFTERS["pressure"](DRAFT_SEED, {"levers": [], "pi": 0.5, "certainty": 0.1})


def test_record_round_trip_carries_the_schedule():
    rec = _trial(0.5, Seed(9))
    payload = record_to_json(rec, "t", 0)
    assert payload["certainty_schedule"] == [bool(x) for x in rec.certainty_schedule]
    assert record_from_json(payload).certainty_schedule == rec.certainty_schedule
    clean = _trial(None, Seed(9))
    assert "certainty_schedule" not in record_to_json(clean, "t", 0)


def test_certainty_is_registration_gated(tmp_path):
    """T030: a live model with certainty in play refuses without a filed
    registration and is admitted with one naming exactly this scope."""
    assert "certainty" in GUARDED_DIALS
    registry = tmp_path / "registrations.yaml"
    registry.write_text(
        "aup-awareness:\n"
        '  osf: "osf.io/xyz99"\n'
        '  filed: "2026-09-20"\n'
        "  dials: [pi, certainty]\n"
        "  drafters: [pressure]\n"
    )

    def spec(registration):
        d = {
            "name": "t",
            "axes": {"certainty": [1.0, 0.5]},
            "drafter": "pressure",
            "agent": "llm",
            "trials_per_condition": 1,
            "base_seed": 1,
            "fixed_dials": {"levers": [], "pi": 0.5},
        }
        if registration:
            d["registration"] = registration
        return spec_from_dict(d)

    assert no_peeking_violation(spec(None)) is not None
    assert no_peeking_violation(spec("aup-awareness"), registry) is None
