"""M36.6 — the EXP-8 Delta harness: drafter, heuristic agent, paired summary."""

from __future__ import annotations

import pytest

from alienbio.suite.delta import delta_pairs, delta_summary, final_state_divergence
from alienbio.suite.dist import Seed
from alienbio.suite.experiment import AGENTS, DRAFTERS, ExperimentSpec, render_report, run_experiment
from alienbio.suite.runner import run


def test_delta_drafter_arms_share_ids_and_flip_the_answer():
    world_m, task_m = DRAFTERS["delta"](Seed(5), {"arm": "match"})
    world_x, task_x = DRAFTERS["delta"](Seed(5), {"arm": "mismatch"})
    om, ox = task_m.setup["oracle"]["delta"], task_x.setup["oracle"]["delta"]
    assert set(world_m.chemistry.molecules) == set(world_x.chemistry.molecules)
    assert om["pair"] == ox["pair"] == Seed(5).value
    assert om["candidates"] == ox["candidates"] and om["conventional"] == ox["conventional"]
    assert om["true_driver"] == om["conventional"]  # match: the bigger signal really drives T
    assert ox["true_driver"] != ox["conventional"]  # mismatch: it does not
    assert om["true_driver"] != ox["true_driver"]
    assert task_m.question.structured == set(om["candidates"])
    with pytest.raises(ValueError, match="arm"):
        DRAFTERS["delta"](Seed(5), {"arm": "sideways"})


@pytest.mark.parametrize("arm, expected", [("match", 1.0), ("mismatch", 0.0)])
def test_heuristic_agent_follows_the_prior_across_the_pair(arm, expected):
    world, task = DRAFTERS["delta"](Seed(6), {"arm": arm})
    agent = AGENTS["heuristic-commit"](None)(Seed(0), {})  # type: ignore[arg-type]
    record = run(world, task, agent, {"arm": arm}, Seed(1))
    assert record.terminal_reason == "committed"
    assert record.objective_score == expected
    assert record.oracle["delta"]["arm"] == arm


def test_exp8_zero_pairs_the_twins_and_reads_the_gap(tmp_path):
    spec = ExperimentSpec(
        name="exp08-mini",
        axes=(("arm", ("match", "mismatch")), ("agent", ("survey-commit", "heuristic-commit"))),
        drafter="delta",
        agent="survey-commit",
        trials_per_condition=2,
        base_seed=8,
        fixed_dials={"max_turns": 6, "sim_steps": 10},
        matched_dials=("arm",),
    )
    rmap = run_experiment(spec, out_dir=str(tmp_path / "out"))
    assert rmap.provenance.failed_trials == 0
    pairs, unpaired = delta_pairs(rmap.records)
    assert {len(v) for v in pairs.values()} == {2} and set(unpaired.values()) == {0}
    cells = delta_summary(rmap.records)
    heur = cells[(("agent", "heuristic-commit"),)]
    null = cells[(("agent", "survey-commit"),)]
    assert heur.gap == 1.0 and heur.prior_following_fraction == 1.0 and heur.world_tracking_fraction == 0.0
    assert null.gap == 0.0 and null.mean_match == 0.0
    assert heur.mean_state_divergence > 0.5  # the rewired edge moves T a long way
    manifest = {"name": spec.name, "trials_planned": 8, "trials_completed": 8, "failed_trials": 0, "elapsed_seconds": 0.0, "model": None, "usage": {}, "cost_estimate": {"usd": 0.0}, "git_sha": "", "version": "", "python": "", "platform": ""}
    report = render_report(rmap, manifest)
    assert "Delta (M36.6" in report and "+1.000" in report


def test_unmatched_arms_are_counted_not_paired(tmp_path):
    spec = ExperimentSpec(
        name="exp08-unmatched", axes=(("arm", ("match", "mismatch")),), drafter="delta", agent="survey-commit",
        trials_per_condition=1, base_seed=9, fixed_dials={"max_turns": 3, "sim_steps": 5},
    )
    rmap = run_experiment(spec, out_dir=str(tmp_path / "out"))
    pairs, unpaired = delta_pairs(rmap.records)
    assert pairs == {(): []} and unpaired == {(): 2}
    assert delta_summary(rmap.records) == {}


def test_final_state_divergence_is_bounded_and_zero_on_identical_states():
    class R:  # minimal duck for final_state_divergence
        def __init__(self, fs):
            self.final_state = fs

    a = R({"c": {"x": 1.0, "y": 2.0}})
    assert final_state_divergence(a, a) == 0.0  # type: ignore[arg-type]
    b = R({"c": {"x": 1.0, "y": 5.0}})
    assert final_state_divergence(a, b) == pytest.approx(3 / 4)  # type: ignore[arg-type]
