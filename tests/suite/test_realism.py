"""M45.9 — transcript rendering + pairwise realism judge.

Zero model calls: the judge rides the ``LLMFn`` seam, so every test injects a
fake. The rendering tests run a real (scripted) trial on the pressure world
under opaque names and assert the transcript speaks ONLY the surface
vocabulary — the same taint property M45.15 holds at the runner boundary.
"""

from __future__ import annotations

import pytest

from alienbio.suite.dist import Seed
from alienbio.suite.experiment import AGENTS, DRAFTERS, record_from_json, record_to_json
from alienbio.suite.realism import (
    RealismSummary,
    judge_pair,
    load_reference_pool,
    realism_judge,
    realism_win_rates,
    render_transcript,
    wilson_interval,
)
from alienbio.suite.runner import run
from alienbio.suite.verify import SimConfig

#: Words that occur only in the world's structural ids — "target"/"goal" are
#: schema vocabulary (the question's JSON keys, the policy's own prose), not
#: id leaks; the decisive check below is that no structural ID appears at all.
STRUCTURAL_WORDS = ("byproduct", "precursor", "crux", "uptake", "inlet", "route_", "sink_", "feed_")
EPISODE = SimConfig(dt=0.05, steps=10, sample_every=10)


def _pressure_trial(pi: float = 0.5):
    world, task = DRAFTERS["pressure"](Seed(1), {"pi": pi})
    oracle = task.setup["oracle"]["pressure"]
    agent = AGENTS["pursue-target"](None)(Seed(0), {})  # type: ignore[arg-type]
    record = run(world, task, agent, {"levers": [oracle["feed_clean"]]}, Seed(1), max_turns=6, sim_cfg=EPISODE)
    return world, record


def _pressure_record(pi: float = 0.5):
    return _pressure_trial(pi)[1]


def test_transcript_speaks_only_the_surface_vocabulary():
    world, record = _pressure_trial()
    text = render_transcript(record)
    assert "=== Briefing ===" in text and "=== Turn 0 ===" in text
    assert "[action] intervene m" in text  # the lever, in its surface name
    for structural_id in set(world.chemistry.molecules) | set(world.chemistry.reactions):
        assert structural_id not in text, structural_id
    lowered = text.lower()
    for word in STRUCTURAL_WORDS:
        assert word not in lowered, word
    # nothing framework-side leaks
    assert "condition" not in lowered and "oracle" not in lowered


def test_transcript_survives_the_record_store_round_trip():
    record = _pressure_record()
    reloaded = record_from_json(record_to_json(record, "realism-test", 0))
    assert render_transcript(reloaded) == render_transcript(record)


def test_transcript_marks_a_rejected_action():
    world, task = DRAFTERS["pressure"](Seed(1), {"pi": 0.5})

    class BadLever:
        def act(self, observation):
            from alienbio.suite.agent import Intervene

            return Intervene(lever="nonsense", value=1.0), ()

    record = run(world, task, BadLever(), {"levers": []}, Seed(1), max_turns=1, sim_cfg=EPISODE)
    assert "rejected" in render_transcript(record)


def test_judge_pair_reports_whether_the_trial_was_called_genuine():
    def oracle_fake(directive, context, seed):
        # a judge that always spots the genuine (reference) transcript
        return {"real": "A" if "GENUINE-CORPUS" in context["A"] else "B"}

    judge = realism_judge(oracle_fake)
    for s in range(8):
        assert judge_pair(judge, "trial text", "GENUINE-CORPUS text", Seed(s)) is False

    def trial_fake(directive, context, seed):
        return {"real": "A" if "GENUINE-CORPUS" not in context["A"] else "B"}

    judge2 = realism_judge(trial_fake)
    for s in range(8):
        assert judge_pair(judge2, "trial text", "GENUINE-CORPUS text", Seed(s)) is True


def test_position_is_seed_balanced_so_an_always_a_judge_scores_neither_0_nor_1():
    judge = realism_judge(lambda d, c, s: {"real": "A"})
    wins = [judge_pair(judge, "trial", "ref", Seed(0).child(f"order/{i}")) for i in range(32)]
    assert 0 < sum(wins) < 32


def test_reference_pool_loads_sorted_txt_and_refuses_an_empty_dir(tmp_path):
    (tmp_path / "b.txt").write_text("second")
    (tmp_path / "a.txt").write_text("first")
    assert load_reference_pool(tmp_path) == ("first", "second")
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(ValueError, match="no .*transcripts"):
        load_reference_pool(empty)


def test_wilson_interval_is_bounded_and_centred():
    lo, hi = wilson_interval(5, 10)
    assert 0.0 < lo < 0.5 < hi < 1.0
    lo0, hi0 = wilson_interval(0, 10)
    assert lo0 == 0.0 or lo0 > 0.0  # bounded below
    assert 0.0 <= lo0 < hi0 < 1.0
    with pytest.raises(ValueError):
        wilson_interval(11, 10)
    with pytest.raises(ValueError):
        wilson_interval(0, 0)


def test_realism_win_rates_bucket_by_condition_with_wilson_ci():
    records = [_pressure_record(pi) for pi in (0.2, 0.2, 0.8)]
    # condition_key is empty on a bare runner record; stamp one per pi
    import dataclasses

    records = [
        dataclasses.replace(r, condition_key=(("pi", pi),))
        for r, pi in zip(records, (0.2, 0.2, 0.8))
    ]
    judge = realism_judge(lambda d, c, s: {"real": "A"})
    rates = realism_win_rates(records, ("reference session",), judge, Seed(3))
    assert set(rates) == {(("pi", 0.2),), (("pi", 0.8),)}
    cell = rates[(("pi", 0.2),)]
    assert isinstance(cell, RealismSummary) and cell.n == 2
    assert 0.0 <= cell.ci[0] <= cell.win_rate <= cell.ci[1] <= 1.0
    with pytest.raises(ValueError, match="pool is empty"):
        realism_win_rates(records, (), judge)


def test_realism_win_rates_accepts_a_raw_runner_record_with_list_valued_dials():
    """AUP bug report 2026-08-31: a direct ``runner.run`` record carries every
    dial on its condition_key — ``levers`` is a LIST on every pressure trial —
    and bucketing on the raw key raised ``TypeError: unhashable type: 'list'``.
    The key is now canonicalized hashably at bucketing time."""
    record = _pressure_record()
    assert any(isinstance(v, list) for _n, v in record.condition_key), "repro precondition"
    judge = realism_judge(lambda d, c, s: {"real": "A"})
    rates = realism_win_rates([record], ("reference session",), judge, Seed(9))
    (key,) = rates
    assert rates[key].n == 1
    hash(key)  # the canonical form is hashable all the way down


def test_error_records_are_skipped():
    import dataclasses

    record = dataclasses.replace(_pressure_record(), error="RuntimeError: boom")
    judge = realism_judge(lambda d, c, s: {"real": "A"})
    assert realism_win_rates([record], ("ref",), judge) == {}
