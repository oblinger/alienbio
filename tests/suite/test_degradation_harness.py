"""M36.9 — EXP-10: degradation under the budget ladder, read off suite records."""

from __future__ import annotations

import pytest

from alienbio.suite.agent import Commit, Intervene, Measure, ScriptedAgent
from alienbio.suite.degradation import budget_total, degradation_ladder, degradation_summary, trial_degradation
from alienbio.suite.deliberation import DeliberationStep
from alienbio.suite.dist import Seed
from alienbio.suite.experiment import AGENTS, CATALYST_ID, DRAFTERS, ExperimentSpec, render_report, run_experiment
from alienbio.suite.runner import run
from alienbio.suite.types import Answer


def _agent(name: str):
    return AGENTS[name](None)(Seed(0), {})  # type: ignore[arg-type]


def test_budget_total_orders_the_ladder():
    assert budget_total("unlimited") == float("inf") and budget_total("4") == 4.0 and budget_total(7) == 7.0 and budget_total(None) == float("inf")


def test_trial_degradation_reads_the_patterns_off_the_log():
    world, task = DRAFTERS["discover"](Seed(2), {"pathway_length": 4, "distractor_count": 2, "symbiosis": 0.8})
    path = task.setup["oracle"]["discover"]["pathway"]
    probes = sorted(world.chemistry.molecules)
    # scope narrowing + reversion + premature + skipped verification, all at once
    policy = (
        Measure(probe=probes[0]), Measure(probe=probes[1]), Measure(probe=probes[2]),
        Measure(probe=probes[0]),  # re-measured after >= 2 intervening actions: reversion
        Measure(probe=probes[0]),
        Measure(probe=probes[0]),
        Commit(answer=Answer(value=list(reversed(path)), kind="ordered_path")),  # a wrong, non-empty answer
    )
    record = run(world, task, ScriptedAgent(policy, seed=Seed(0)), {"max_turns": 10, "sim_steps": 5}, Seed(1))
    d = trial_degradation(record)
    assert d.investigated == 6 and d.verified == 0 and d.committed and not d.exhausted
    assert d.reversion and d.scope_narrowing and d.skipped_verification
    assert not d.premature  # 6 investigations >= the pathway length 4
    assert not d.budget_aware
    # an explicit floor above the count makes it premature
    assert trial_degradation(record, evidence_floor=7).premature


def test_verification_and_budget_awareness_are_detected():
    world, task = DRAFTERS["discover"](Seed(3), {"pathway_length": 4, "symbiosis": 0.8})
    step = task.setup["oracle"]["discover"]["catalysed_step"]
    policy = (Measure(probe="r0"), Intervene(lever=step, value=0.5), Commit(answer=Answer(value=["r0"], kind="ordered_path")))
    record = run(world, task, ScriptedAgent(policy, seed=Seed(0)), {"levers": [step], "max_turns": 6, "sim_steps": 5}, Seed(1))
    d = trial_degradation(record)
    assert d.verified == 1 and not d.skipped_verification and d.premature  # 1 < 4
    aware = record.deliberation_trace.append(DeliberationStep(turn=0, kind="reason", content="I am running out of budget; committing now."))
    import dataclasses

    assert trial_degradation(dataclasses.replace(record, deliberation_trace=aware)).budget_aware


def test_budget_exhaustion_is_read_as_exhausted_not_committed():
    world, task = DRAFTERS["discover"](Seed(4), {"pathway_length": 5, "distractor_count": 6, "symbiosis": 0.8})
    record = run(world, task, _agent("survey-commit"), {"budget": "4", "max_turns": 24, "sim_steps": 5}, Seed(1))
    assert record.terminal_reason == "budget_exhausted"
    d = trial_degradation(record)
    assert d.exhausted and not d.committed and d.investigated == 4


def test_exp10_zero_reads_exhaustion_rising_down_the_ladder(tmp_path):
    spec = ExperimentSpec(
        name="exp10-mini",
        axes=(("budget", ("unlimited", "8", "4")), ("agent", ("survey-commit", "measure-commit"))),
        drafter="discover",
        agent="survey-commit",
        trials_per_condition=1,
        base_seed=10,
        fixed_dials={"pathway_length": 5, "distractor_count": 6, "symbiosis": 0.8, "observability": 0.5, "max_turns": 24, "sim_steps": 5},
    )
    rmap = run_experiment(spec, out_dir=str(tmp_path / "out"))
    assert rmap.provenance.failed_trials == 0
    cells = degradation_summary(rmap.records)
    ladders = degradation_ladder(cells)
    survey = ladders[(("agent", "survey-commit"),)]
    assert survey.levels == ("unlimited", "8", "4")
    exhausted = [c.exhausted_rate for c in survey.cells]
    assert exhausted[0] == 0.0 and exhausted[-1] == 1.0 and all(b >= a for a, b in zip(exhausted, exhausted[1:]))
    assert survey.accuracy_non_increasing and survey.cliff is None  # every scripted arm scores 0
    mc = ladders[(("agent", "measure-commit"),)]
    assert all(c.exhausted_rate == 0.0 and c.commit_rate == 1.0 for c in mc.cells)
    manifest = {"name": spec.name, "trials_planned": 6, "trials_completed": 6, "failed_trials": 0, "elapsed_seconds": 0.0, "model": None, "usage": {}, "cost_estimate": {"usd": 0.0}, "git_sha": "", "version": "", "python": "", "platform": ""}
    report = render_report(rmap, manifest)
    assert "Degradation (M36.9" in report and "budget ladder for" in report and "no cliff" in report
