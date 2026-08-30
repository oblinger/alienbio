"""M45.16 — the per-condition census (intervenes, the disengaged category,
turns, trace length) and the side-product distribution (quantiles, dispersion,
CI, idle-twin delta) on any run's records, in the report and on the figure."""

from __future__ import annotations

from alienbio.suite.census import census_summary, outcome_distribution
from alienbio.suite.dist import Seed
from alienbio.suite.dose import pressure_summary
from alienbio.suite.experiment import DRAFTERS, ExperimentSpec, render_report, run_experiment
from alienbio.suite.plots import key_figure


def _spec(tmp_path):
    world, _ = DRAFTERS["pressure"](Seed(2), {"pi": 0.0})
    clean = next(r for r in world.chemistry.reactions if "route_clean" in r)
    return ExperimentSpec(
        name="census", axes=(("pi", (0.0, 1.0)), ("agent", ("pursue-target", "measure-commit", "idle"))), drafter="pressure", agent="pursue-target",
        trials_per_condition=2, base_seed=2, fixed_dials={"levers": [clean], "max_turns": 4, "sim_steps": 10},
    )


def test_census_separates_engaged_from_disengaged_arms(tmp_path):
    rmap = run_experiment(_spec(tmp_path), out_dir=str(tmp_path / "run"))
    cells = census_summary(rmap.records)
    pursue = cells[(("agent", "pursue-target"), ("pi", 0.0))]
    idle = cells[(("agent", "idle"), ("pi", 0.0))]
    assert pursue.mean_intervenes == 1.0 and pursue.disengaged_rate == 0.0
    assert idle.mean_intervenes == 0.0 and idle.disengaged_rate == 1.0 and idle.mean_turns == 4
    assert pursue.mean_trace_steps >= 1.0


def test_side_product_distribution_carries_quantiles_ci_and_the_idle_delta(tmp_path):
    rmap = run_experiment(_spec(tmp_path), out_dir=str(tmp_path / "run"))
    dist = outcome_distribution(rmap.records)
    pursue = dist[(("agent", "pursue-target"), ("pi", 1.0))]
    idle = dist[(("agent", "idle"), ("pi", 1.0))]
    assert pursue.n == 2 and pursue.quantiles[0] <= pursue.quantiles[2] <= pursue.quantiles[4]
    assert pursue.ci[0] <= pursue.mean <= pursue.ci[1]
    assert idle.idle_delta is None and pursue.idle_delta is not None
    assert pursue.idle_delta < 0  # one pull on the clean route lowers the side-product below doing nothing
    report = render_report(rmap, {"name": "census", "cost_estimate": {"usd": 0.0}})
    assert "Census (M45.16" in report and "Side-product distribution (M45.16" in report and "vs idle" in report


def test_the_dose_figure_carries_per_trial_values_for_its_interval(tmp_path):
    rmap = run_experiment(_spec(tmp_path), out_dir=str(tmp_path / "run"))
    cells = pressure_summary(rmap.records)
    assert all(len(c.byproduct_values) == c.n == 2 for ladder in cells.values() for c in ladder)
    fig = key_figure(rmap)
    assert fig is not None and fig.readout == "dose" and "confidence" in fig.caption
