"""I. The integrative end-state — mass trials, the reliability map, matched
baselines, declared power (M48.1)."""

from __future__ import annotations

from alienbio.suite.experiment import idle_baseline_comparison
from alienbio.suite.power import PowerDesign

from .conftest import capability, catalog, small


@capability("I1")
def test_i1_a_two_axis_sweep_yields_cells_interactions_contrasts_and_idle_baselines(harness):
    """A two-axis sweep with a declared power design yields cells, interactions, contrasts and matched idle baselines."""
    spec = small(catalog("exp9"), axes=(("stakes", ("low", "high")), ("reversibility", ("reversible", "irreversible"))), trials=3,
                 fixed_dials={**catalog("exp9").fixed_dials, "max_turns": 2, "sim_steps": 5},
                 design=PowerDesign(target_effect_d=3.0, primary_contrast={"axis": "stakes", "low": "low", "high": "high"}))
    rmap, report, manifest = harness(spec)
    assert len(rmap.cells) == 8 and rmap.provenance.failed_trials == 0  # 2x2 x the matched idle arm
    assert rmap.interactions and rmap.contrasts
    twins = idle_baseline_comparison(rmap)
    assert twins and all(n == 3 for *_, n in twins)
    assert manifest["design"]["required_trials_per_condition"] <= 3
    assert "Declared design" in report or "design" in report.lower()
    assert manifest["trials_completed"] == 24
