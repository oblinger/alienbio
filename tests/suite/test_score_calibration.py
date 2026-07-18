"""Acceptance tests for probabilistic-forecast calibration scoring (M33.8)."""

from __future__ import annotations

import pytest

from alienbio.suite.score_calibration import (
    brier_score,
    expected_calibration_error,
    mean_brier,
)


# ═══════════════════════════════════════════════════════════════════════════
# brier_score
# ═══════════════════════════════════════════════════════════════════════════

def test_brier_score_perfect_true():
    assert brier_score(1.0, True) == pytest.approx(0.0)


def test_brier_score_perfect_false_but_predicted_true():
    assert brier_score(0.0, True) == pytest.approx(1.0)


def test_brier_score_maximally_uncertain():
    assert brier_score(0.5, True) == pytest.approx(0.25)
    assert brier_score(0.5, False) == pytest.approx(0.25)


def test_brier_score_hand_value():
    # (0.7 - 1)**2 == 0.09
    assert brier_score(0.7, True) == pytest.approx(0.09)
    # (0.7 - 0)**2 == 0.49
    assert brier_score(0.7, False) == pytest.approx(0.49)


@pytest.mark.parametrize("bad_pred", [-0.01, 1.01, -5.0, 2.0])
def test_brier_score_out_of_range_raises(bad_pred):
    with pytest.raises(ValueError):
        brier_score(bad_pred, True)


# ═══════════════════════════════════════════════════════════════════════════
# mean_brier
# ═══════════════════════════════════════════════════════════════════════════

def test_mean_brier_hand_computed():
    preds = [1.0, 0.0, 0.5, 0.7]
    outcomes = [True, True, True, False]
    # per-item: 0.0, 1.0, 0.25, 0.49 -> mean == 1.74 / 4 == 0.435
    expected = (0.0 + 1.0 + 0.25 + 0.49) / 4
    assert mean_brier(preds, outcomes) == pytest.approx(expected)
    assert mean_brier(preds, outcomes) == pytest.approx(0.435)


def test_mean_brier_length_mismatch_raises():
    with pytest.raises(ValueError):
        mean_brier([0.5, 0.5], [True])


def test_mean_brier_empty_raises():
    with pytest.raises(ValueError):
        mean_brier([], [])


# ═══════════════════════════════════════════════════════════════════════════
# expected_calibration_error
# ═══════════════════════════════════════════════════════════════════════════

def test_ece_perfectly_calibrated_is_near_zero():
    # For each of 10 bins, put N=20 items at the bin midpoint; midpoint * N is
    # always an integer for N=20 & n_bins=10 (midpoint = (i+0.5)/10, so
    # midpoint*20 = 2i+1), so empirical frequency matches the midpoint exactly.
    n_bins = 10
    n_per_bin = 20
    preds: list[float] = []
    outcomes: list[bool] = []
    for i in range(n_bins):
        midpoint = (i + 0.5) / n_bins
        count_true = 2 * i + 1  # == round(midpoint * n_per_bin), exact here
        preds.extend([midpoint] * n_per_bin)
        outcomes.extend([True] * count_true + [False] * (n_per_bin - count_true))
    ece = expected_calibration_error(preds, outcomes, n_bins=n_bins)
    assert ece == pytest.approx(0.0, abs=1e-9)


def test_ece_maximally_miscalibrated_is_one():
    preds = [1.0] * 10
    outcomes = [False] * 10
    assert expected_calibration_error(preds, outcomes) == pytest.approx(1.0)


def test_ece_hand_computed_example():
    preds = [0.05, 0.15, 0.95]
    outcomes = [False, True, True]
    # bin(0.05)=0 -> |0.05 - 0| = 0.05
    # bin(0.15)=1 -> |0.15 - 1| = 0.85
    # bin(0.95)=9 -> |0.95 - 1| = 0.05
    # each bin has weight 1/3
    expected = (0.05 + 0.85 + 0.05) / 3
    assert expected_calibration_error(preds, outcomes, n_bins=10) == pytest.approx(expected)


def test_ece_length_mismatch_raises():
    with pytest.raises(ValueError):
        expected_calibration_error([0.5, 0.5], [True], n_bins=10)


def test_ece_empty_raises():
    with pytest.raises(ValueError):
        expected_calibration_error([], [], n_bins=10)


@pytest.mark.parametrize("bad_n_bins", [0, -1, -10])
def test_ece_bad_n_bins_raises(bad_n_bins):
    with pytest.raises(ValueError):
        expected_calibration_error([0.5], [True], n_bins=bad_n_bins)


def test_ece_bin_edge_placement_is_documented_and_deterministic():
    # With n_bins=10, width=0.1: exactly-representable edges (0.1, 0.5) land
    # in the bin ABOVE the edge; floating-point-short edges (0.3, 0.7) land in
    # the bin BELOW the edge (see module docstring). This test locks in that
    # behaviour so any change to the bin-index formula is caught.
    single_pred_outcome = [True]

    def _ece_single(pred: float) -> float:
        return expected_calibration_error([pred], single_pred_outcome, n_bins=10)

    # pred == outcome (True==1.0) -> |pred - 1.0| for whichever bin it lands in.
    assert _ece_single(0.1) == pytest.approx(abs(0.1 - 1.0))
    assert _ece_single(0.5) == pytest.approx(abs(0.5 - 1.0))
    assert _ece_single(0.3) == pytest.approx(abs(0.3 - 1.0))
    assert _ece_single(0.7) == pytest.approx(abs(0.7 - 1.0))
    # A prediction of exactly 1.0 is clamped into the last bin, not an
    # out-of-range 10th bin.
    assert expected_calibration_error([1.0], [True], n_bins=10) == pytest.approx(0.0)

    # Multi-item cases where the *value* depends on which side of the edge a
    # prediction lands on (a single-item ECE always equals |pred - outcome|
    # regardless of bin placement, so it cannot catch a wrong edge rule).
    # 0.1 lands in bin 1 (above the edge), separate from 0.05's bin 0:
    #   bin 0: {0.05}/{False} -> |0.05 - 0| = 0.05, weight 1/2
    #   bin 1: {0.1}/{True}   -> |0.1 - 1|  = 0.9,  weight 1/2
    #   ece == 0.5*0.05 + 0.5*0.9 == 0.475
    # If 0.1 instead shared bin 0 with 0.05, ece would be 0.425.
    assert expected_calibration_error(
        [0.05, 0.1], [False, True], n_bins=10
    ) == pytest.approx(0.475)
    # 0.3 lands in bin 2 (below the edge), sharing a bin with 0.25:
    #   bin 2: {0.25, 0.3}/{False, True} -> |0.275 - 0.5| = 0.225, weight 1
    #   ece == 0.225
    # If 0.3 instead landed in bin 3 alone, ece would be 0.475.
    assert expected_calibration_error(
        [0.25, 0.3], [False, True], n_bins=10
    ) == pytest.approx(0.225)


def test_ece_repeatable_deterministic():
    preds = [0.1, 0.2, 0.9]
    outcomes = [True, False, True]
    a = expected_calibration_error(preds, outcomes, n_bins=5)
    b = expected_calibration_error(preds, outcomes, n_bins=5)
    assert a == b
