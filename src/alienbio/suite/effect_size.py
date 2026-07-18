"""M34.3 — two-sample effect-size and test statistics.

Pure, closed-form comparisons between two groups of opaque numeric
observations. No simulation, no randomness (no bootstrap/permutation), no
I/O. All variances used here are *sample* (``n - 1`` denominator) variances.

- :func:`mean_difference` — ``mean(a) - mean(b)``.
- :func:`cohens_d` — standardized mean difference using a pooled sample
  standard deviation.
- :func:`welch_t` — Welch's t statistic (unequal-variance two-sample
  t-statistic), which does not assume equal variances or pool them.
"""

from __future__ import annotations

import math
import statistics
from typing import Sequence


def mean_difference(a: Sequence[float], b: Sequence[float]) -> float:
    """Return ``mean(a) - mean(b)``.

    Raises:
        ValueError: if either ``a`` or ``b`` is empty.
    """
    if not a:
        raise ValueError("a must not be empty")
    if not b:
        raise ValueError("b must not be empty")
    return statistics.fmean(a) - statistics.fmean(b)


def cohens_d(a: Sequence[float], b: Sequence[float]) -> float:
    """Standardized mean difference between ``a`` and ``b`` (Cohen's d).

    Computed as ``(mean(a) - mean(b)) / pooled_sd``, where ``pooled_sd`` is
    the pooled sample standard deviation::

        sqrt(((n1 - 1) * s1**2 + (n2 - 1) * s2**2) / (n1 + n2 - 2))

    using sample (``n - 1``) variances ``s1**2`` and ``s2**2``.

    Raises:
        ValueError: if either group has fewer than 2 values, or if the
            pooled standard deviation is exactly 0 (undefined effect size —
            fails loudly rather than dividing by zero).
    """
    n1 = len(a)
    n2 = len(b)
    if n1 < 2:
        raise ValueError(f"a must have at least 2 values, got {n1}")
    if n2 < 2:
        raise ValueError(f"b must have at least 2 values, got {n2}")
    s1_sq = statistics.variance(a)
    s2_sq = statistics.variance(b)
    pooled_var = ((n1 - 1) * s1_sq + (n2 - 1) * s2_sq) / (n1 + n2 - 2)
    pooled_sd = math.sqrt(pooled_var)
    if pooled_sd == 0:
        raise ValueError("pooled standard deviation is 0 — Cohen's d is undefined")
    return (statistics.fmean(a) - statistics.fmean(b)) / pooled_sd


def welch_t(a: Sequence[float], b: Sequence[float]) -> float:
    """Welch's t statistic for two independent samples with unequal variance.

    Computed as ``(mean(a) - mean(b)) / sqrt(s1**2 / n1 + s2**2 / n2)`` using
    sample (``n - 1``) variances ``s1**2`` and ``s2**2``.

    Raises:
        ValueError: if either group has fewer than 2 values, or if the
            denominator is exactly 0 (undefined — fails loudly rather than
            dividing by zero).
    """
    n1 = len(a)
    n2 = len(b)
    if n1 < 2:
        raise ValueError(f"a must have at least 2 values, got {n1}")
    if n2 < 2:
        raise ValueError(f"b must have at least 2 values, got {n2}")
    s1_sq = statistics.variance(a)
    s2_sq = statistics.variance(b)
    denom = math.sqrt(s1_sq / n1 + s2_sq / n2)
    if denom == 0:
        raise ValueError("denominator is 0 — Welch's t is undefined")
    return (statistics.fmean(a) - statistics.fmean(b)) / denom
