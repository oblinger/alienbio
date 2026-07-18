"""Acceptance tests for two-sample effect-size statistics (M34.3)."""

from __future__ import annotations

import math

import pytest

from alienbio.suite.effect_size import cohens_d, mean_difference, welch_t


# ═══════════════════════════════════════════════════════════════════════════
# mean_difference
# ═══════════════════════════════════════════════════════════════════════════

def test_mean_difference_hand_computed():
    # mean([1,2,3]) == 2, mean([4,5,6]) == 5 -> 2 - 5 == -3
    assert mean_difference([1, 2, 3], [4, 5, 6]) == pytest.approx(-3.0)


def test_mean_difference_sign_flips_with_argument_order():
    assert mean_difference([4, 5, 6], [1, 2, 3]) == pytest.approx(3.0)


def test_mean_difference_zero_when_equal_means():
    assert mean_difference([1, 2, 3], [0, 2, 4]) == pytest.approx(0.0)


def test_mean_difference_empty_a_raises():
    with pytest.raises(ValueError):
        mean_difference([], [1, 2, 3])


def test_mean_difference_empty_b_raises():
    with pytest.raises(ValueError):
        mean_difference([1, 2, 3], [])


def test_mean_difference_both_empty_raises():
    with pytest.raises(ValueError):
        mean_difference([], [])


# ═══════════════════════════════════════════════════════════════════════════
# cohens_d
# ═══════════════════════════════════════════════════════════════════════════

def test_cohens_d_hand_computed():
    # a=[1,2,3]: mean=2, sample variance = ((1-2)^2+(2-2)^2+(3-2)^2)/(3-1) = 2/2 = 1
    # b=[4,5,6]: mean=5, sample variance = 1 (identical shape, shifted)
    # pooled_var = ((3-1)*1 + (3-1)*1) / (3+3-2) = 4/4 = 1 -> pooled_sd = 1
    # cohens_d = (2 - 5) / 1 == -3
    assert cohens_d([1, 2, 3], [4, 5, 6]) == pytest.approx(-3.0)


def test_cohens_d_sign_flips_with_argument_order():
    assert cohens_d([4, 5, 6], [1, 2, 3]) == pytest.approx(3.0)


def test_cohens_d_zero_when_means_equal():
    # a=[1,2,3] mean=2, b=[0,2,4] mean=2 -> numerator is 0 regardless of
    # pooled_sd (which is nonzero here: variances are 1 and 4).
    assert cohens_d([1, 2, 3], [0, 2, 4]) == pytest.approx(0.0)


def test_cohens_d_pooled_sd_matches_common_sample_std_when_equal_variance():
    # Equal-size, equal-variance groups: pooled_sd must equal the common
    # per-group sample standard deviation (sanity check on the pooling math).
    a = [1, 2, 3]
    b = [4, 5, 6]
    common_sd = 1.0  # hand-computed: sample variance of both groups is 1
    expected_d = (2.0 - 5.0) / common_sd
    assert cohens_d(a, b) == pytest.approx(expected_d)


def test_cohens_d_unequal_size_unequal_variance_hand_computed():
    # a=[1,2,3,4]: mean=2.5, sample variance = ((1-2.5)^2+(2-2.5)^2+(3-2.5)^2+(4-2.5)^2)/(4-1)
    #            = (2.25+0.25+0.25+2.25)/3 = 5/3
    # b=[10,14]: mean=12, sample variance = ((10-12)^2+(14-12)^2)/(2-1) = 8/1 = 8
    # pooled_var = (3*(5/3) + 1*8) / (4+2-2) = (5 + 8) / 4 = 13/4
    # cohens_d = (2.5 - 12) / sqrt(13/4) = -9.5 / sqrt(3.25)
    # This pins the (n1-1)/(n2-1) weighting: an unweighted average
    # ((5/3 + 8) / 2) would give a different pooled_var and a different d.
    a = [1, 2, 3, 4]
    b = [10, 14]
    assert cohens_d(a, b) == pytest.approx(-9.5 / math.sqrt(13.0 / 4.0))
    assert cohens_d(a, b) == pytest.approx(-5.269651864139677)


def test_cohens_d_a_too_short_raises():
    with pytest.raises(ValueError):
        cohens_d([1.0], [1, 2, 3])


def test_cohens_d_b_too_short_raises():
    with pytest.raises(ValueError):
        cohens_d([1, 2, 3], [1.0])


def test_cohens_d_zero_pooled_sd_raises():
    # Both groups have zero variance (all values identical within each
    # group) -> pooled_sd == 0 -> undefined effect size.
    with pytest.raises(ValueError):
        cohens_d([5, 5, 5], [1, 1, 1])


# ═══════════════════════════════════════════════════════════════════════════
# welch_t
# ═══════════════════════════════════════════════════════════════════════════

def test_welch_t_hand_computed():
    # a=[1,2,3] mean=2 var=1 n=3; b=[4,5,6] mean=5 var=1 n=3
    # denom = sqrt(1/3 + 1/3) = sqrt(2/3)
    # t = (2 - 5) / sqrt(2/3)
    expected = (2.0 - 5.0) / math.sqrt(2.0 / 3.0)
    assert welch_t([1, 2, 3], [4, 5, 6]) == pytest.approx(expected)
    assert welch_t([1, 2, 3], [4, 5, 6]) == pytest.approx(-3.674234614174767)


def test_welch_t_sign_flips_with_argument_order():
    expected = (5.0 - 2.0) / math.sqrt(2.0 / 3.0)
    assert welch_t([4, 5, 6], [1, 2, 3]) == pytest.approx(expected)
    assert welch_t([4, 5, 6], [1, 2, 3]) == pytest.approx(3.674234614174767)


def test_welch_t_zero_when_means_equal():
    assert welch_t([1, 2, 3], [0, 2, 4]) == pytest.approx(0.0)


def test_welch_t_unequal_size_unequal_variance_hand_computed():
    # a=[1,2,3,4]: mean=2.5, sample variance=5/3, n=4
    # b=[10,14]: mean=12, sample variance=8, n=2
    # denom = sqrt((5/3)/4 + 8/2) = sqrt(5/12 + 4) = sqrt(53/12)
    # t = (2.5 - 12) / sqrt(53/12) = -9.5 / sqrt(53/12)
    # This pins the s1^2/n1 + s2^2/n2 term pairing: a swapped-denominator
    # variant (s1^2/n2 + s2^2/n1) gives a different value here.
    a = [1, 2, 3, 4]
    b = [10, 14]
    expected = -9.5 / math.sqrt(53.0 / 12.0)
    assert welch_t(a, b) == pytest.approx(expected)
    assert welch_t(a, b) == pytest.approx(-4.520394038593421)


def test_welch_t_a_too_short_raises():
    with pytest.raises(ValueError):
        welch_t([1.0], [1, 2, 3])


def test_welch_t_b_too_short_raises():
    with pytest.raises(ValueError):
        welch_t([1, 2, 3], [1.0])


def test_welch_t_zero_denominator_raises():
    with pytest.raises(ValueError):
        welch_t([5, 5, 5], [1, 1, 1])
