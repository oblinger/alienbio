"""Acceptance tests for single-sample summary statistics (M34.3)."""

from __future__ import annotations

import math

import pytest

from alienbio.suite.stats_summary import (
    mean_confidence_interval,
    sample_mean,
    sample_std,
    sample_variance,
    standard_error,
)


# Hand-computed sample: mean=4.0, variance(n-1)=4.0, std=2.0,
# se = 2.0 / sqrt(3) == 1.1547005383792515
HAND_VALUES = [2.0, 4.0, 6.0]
HAND_MEAN = 4.0
HAND_VARIANCE = 4.0
HAND_STD = 2.0
HAND_SE = 2.0 / math.sqrt(3)

ZERO_VARIANCE_VALUES = [5.0, 5.0, 5.0]


# ═══════════════════════════════════════════════════════════════════════════
# sample_mean
# ═══════════════════════════════════════════════════════════════════════════

def test_sample_mean_hand_computed():
    assert sample_mean(HAND_VALUES) == pytest.approx(HAND_MEAN)


def test_sample_mean_single_element():
    assert sample_mean([7.0]) == pytest.approx(7.0)


def test_sample_mean_empty_raises():
    with pytest.raises(ValueError):
        sample_mean([])


# ═══════════════════════════════════════════════════════════════════════════
# sample_variance
# ═══════════════════════════════════════════════════════════════════════════

def test_sample_variance_hand_computed():
    # (2-4)^2 + (4-4)^2 + (6-4)^2 == 4 + 0 + 4 == 8; / (3-1) == 4.0
    assert sample_variance(HAND_VALUES) == pytest.approx(HAND_VARIANCE)


def test_sample_variance_zero_variance():
    assert sample_variance(ZERO_VARIANCE_VALUES) == pytest.approx(0.0)


def test_sample_variance_empty_raises():
    with pytest.raises(ValueError):
        sample_variance([])


def test_sample_variance_single_element_raises():
    with pytest.raises(ValueError):
        sample_variance([1.0])


# ═══════════════════════════════════════════════════════════════════════════
# sample_std
# ═══════════════════════════════════════════════════════════════════════════

def test_sample_std_hand_computed():
    assert sample_std(HAND_VALUES) == pytest.approx(HAND_STD)


def test_sample_std_zero_variance():
    assert sample_std(ZERO_VARIANCE_VALUES) == pytest.approx(0.0)


def test_sample_std_empty_raises():
    with pytest.raises(ValueError):
        sample_std([])


def test_sample_std_single_element_raises():
    with pytest.raises(ValueError):
        sample_std([1.0])


# ═══════════════════════════════════════════════════════════════════════════
# standard_error
# ═══════════════════════════════════════════════════════════════════════════

def test_standard_error_hand_computed():
    assert standard_error(HAND_VALUES) == pytest.approx(HAND_SE)


def test_standard_error_zero_variance():
    assert standard_error(ZERO_VARIANCE_VALUES) == pytest.approx(0.0)


def test_standard_error_empty_raises():
    with pytest.raises(ValueError):
        standard_error([])


def test_standard_error_single_element_raises():
    with pytest.raises(ValueError):
        standard_error([1.0])


# ═══════════════════════════════════════════════════════════════════════════
# mean_confidence_interval
# ═══════════════════════════════════════════════════════════════════════════

def test_mean_confidence_interval_hand_computed_default_z():
    default_z = 1.959963984540054
    lo, hi = mean_confidence_interval(HAND_VALUES)
    expected_half_width = default_z * HAND_SE
    assert lo == pytest.approx(HAND_MEAN - expected_half_width)
    assert hi == pytest.approx(HAND_MEAN + expected_half_width)


def test_mean_confidence_interval_midpoint_is_mean():
    lo, hi = mean_confidence_interval(HAND_VALUES, z=2.0)
    assert (lo + hi) / 2 == pytest.approx(HAND_MEAN)


def test_mean_confidence_interval_half_width_equals_z_times_se():
    z = 2.0
    lo, hi = mean_confidence_interval(HAND_VALUES, z=z)
    assert (hi - lo) / 2 == pytest.approx(z * HAND_SE)
    assert hi - HAND_MEAN == pytest.approx(z * HAND_SE)
    assert HAND_MEAN - lo == pytest.approx(z * HAND_SE)


def test_mean_confidence_interval_zero_variance_is_degenerate():
    mean = sample_mean(ZERO_VARIANCE_VALUES)
    lo, hi = mean_confidence_interval(ZERO_VARIANCE_VALUES)
    assert lo == pytest.approx(mean)
    assert hi == pytest.approx(mean)


def test_mean_confidence_interval_zero_z_is_degenerate():
    lo, hi = mean_confidence_interval(HAND_VALUES, z=0.0)
    assert lo == pytest.approx(HAND_MEAN)
    assert hi == pytest.approx(HAND_MEAN)


def test_mean_confidence_interval_empty_raises():
    with pytest.raises(ValueError):
        mean_confidence_interval([])


def test_mean_confidence_interval_single_element_raises():
    with pytest.raises(ValueError):
        mean_confidence_interval([1.0])


def test_mean_confidence_interval_negative_z_raises():
    with pytest.raises(ValueError):
        mean_confidence_interval(HAND_VALUES, z=-0.5)
