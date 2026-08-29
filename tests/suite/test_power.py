"""M46.9 — power arithmetic + the declared PowerDesign."""

from __future__ import annotations

import pytest

from alienbio.suite.power import (
    PowerDesign,
    bonferroni_alpha,
    detectable_effect,
    trials_for_effect,
    z_quantile,
)


def test_z_quantile_matches_textbook_values():
    assert z_quantile(0.975) == pytest.approx(1.959964, abs=1e-5)
    assert z_quantile(0.8) == pytest.approx(0.841621, abs=1e-5)
    with pytest.raises(ValueError):
        z_quantile(1.0)


def test_trials_for_effect_textbook_medium_effect():
    # d=0.5, alpha=0.05 two-sided, power=0.8: the normal approximation gives
    # 2*((1.96+0.8416)/0.5)^2 = 62.8 -> 63, +1 for the small-n correction.
    assert trials_for_effect(0.5) == 64
    assert trials_for_effect(0.8) == 26  # 2*(2.8016/0.8)^2 = 24.5 -> 25, +1
    assert trials_for_effect(5.0) == 2  # floor of 2
    with pytest.raises(ValueError):
        trials_for_effect(0.0)
    with pytest.raises(ValueError):
        trials_for_effect(0.5, alpha=1.5)


def test_detectable_effect_inverts_trials_for_effect():
    n = trials_for_effect(0.5)
    d = detectable_effect(n)
    assert d <= 0.5
    assert trials_for_effect(d) <= n + 1


def test_bonferroni_alpha():
    assert bonferroni_alpha(0.05, 1) == 0.05
    assert bonferroni_alpha(0.05, 5) == pytest.approx(0.01)


def test_power_design_validation_and_round_trip():
    design = PowerDesign(target_effect_d=0.8, primary_contrast={"axis": "pi", "low": 0.0, "high": 1.0})
    assert design.required_trials_per_condition == 26
    d = design.to_dict()
    assert d["required_trials_per_condition"] == 26
    assert PowerDesign.from_dict({k: v for k, v in d.items() if k != "required_trials_per_condition"}) == design
    with pytest.raises(ValueError, match="multiple_comparison"):
        PowerDesign(target_effect_d=0.5, multiple_comparison="holm")
    with pytest.raises(ValueError, match="primary_contrast"):
        PowerDesign(target_effect_d=0.5, primary_contrast={"axis": "pi"})
    with pytest.raises(ValueError, match="unknown design key"):
        PowerDesign.from_dict({"target_effect_d": 0.5, "bogus": 1})
