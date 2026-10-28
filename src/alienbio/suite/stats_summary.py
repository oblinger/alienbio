"""M34.3 — single-sample summary statistics + confidence interval.

Pure, closed-form descriptive statistics over a single sample of plain
``float`` values. No randomness, no simulation, no I/O:

- :func:`sample_mean` — arithmetic mean.
- :func:`sample_variance` — unbiased (``n - 1``) sample variance.
- :func:`sample_std` — sample standard deviation (``sqrt`` of the variance).
- :func:`standard_error` — standard error of the mean (``std / sqrt(n)``).
- :func:`mean_confidence_interval` — ``(mean - c*se, mean + c*se)`` where
  ``c`` is a caller-supplied critical value ``z``, else (the default) the
  two-sided 95 % Student-t quantile at ``n - 1`` degrees of freedom
  (:func:`t_critical`). T088 stats 1: the default used to be the normal
  1.96, which covers the true mean 81 % of the time at the n = 3 a catalog
  cell holds.
- :func:`t_critical` — the two-sided Student-t critical value, computed from
  the t CDF (regularized incomplete beta, bisection) with :mod:`math` only.
"""

from __future__ import annotations

import math
from typing import Optional, Sequence


def _betacf(a: float, b: float, x: float) -> float:
    """Continued fraction for the regularized incomplete beta (Lentz)."""
    tiny = 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 300):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-15:
            break
    return h


def _betainc(a: float, b: float, x: float) -> float:
    """Regularized incomplete beta ``I_x(a, b)``."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    front = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log1p(-x))
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1.0 - x) / b


def _t_two_sided_tail(t: float, df: float) -> float:
    """``P(|T| > t)`` for Student's t with ``df`` degrees of freedom."""
    return _betainc(df / 2.0, 0.5, df / (df + t * t))


def t_critical(df: float, confidence: float = 0.95) -> float:
    """The two-sided Student-t critical value: ``c`` with ``P(|T| <= c) =
    confidence`` at ``df`` degrees of freedom (4.303 at df = 2, 2.571 at 5,
    2.042 at 30). Bisection on the CDF, so exact to ~1e-12.

    Raises :class:`ValueError` unless ``df > 0`` and ``0 < confidence < 1``.
    """
    if not (df > 0 and math.isfinite(df)):
        raise ValueError(f"df must be a positive finite number, got {df!r}")
    if not 0.0 < confidence < 1.0:
        raise ValueError(f"confidence must be in (0, 1), got {confidence!r}")
    alpha = 1.0 - confidence
    lo, hi = 0.0, 1.0
    while _t_two_sided_tail(hi, df) > alpha:
        hi *= 2.0
    for _ in range(200):
        mid = (lo + hi) / 2.0
        if _t_two_sided_tail(mid, df) > alpha:
            lo = mid
        else:
            hi = mid
        if hi - lo < 1e-13 * hi:
            break
    return (lo + hi) / 2.0


def sample_mean(values: Sequence[float]) -> float:
    """Arithmetic mean of ``values``.

    Raises :class:`ValueError` if ``values`` is empty.
    """
    if not values:
        raise ValueError("values must be non-empty")
    return sum(values) / len(values)


def sample_variance(values: Sequence[float]) -> float:
    """Unbiased (``n - 1``) sample variance of ``values``.

    Raises :class:`ValueError` if ``values`` has fewer than 2 elements.
    """
    n = len(values)
    if n < 2:
        raise ValueError(f"values must have at least 2 elements, got {n}")
    mean = sample_mean(values)
    return sum((x - mean) ** 2 for x in values) / (n - 1)


def sample_std(values: Sequence[float]) -> float:
    """Sample standard deviation (``sqrt`` of :func:`sample_variance`).

    Raises :class:`ValueError` if ``values`` has fewer than 2 elements.
    """
    return math.sqrt(sample_variance(values))


def standard_error(values: Sequence[float]) -> float:
    """Standard error of the mean: ``sample_std(values) / sqrt(n)``.

    Raises :class:`ValueError` if ``values`` has fewer than 2 elements.
    """
    n = len(values)
    return sample_std(values) / math.sqrt(n)


def mean_confidence_interval(
    values: Sequence[float], z: Optional[float] = None
) -> tuple[float, float]:
    """The 95 % confidence interval for the sample mean: ``(mean - c*se,
    mean + c*se)``.

    ``c`` is ``z`` when the caller supplies one (a normal or ``t``
    multiplier), else the two-sided 95 % Student-t quantile at ``n - 1``
    degrees of freedom (:func:`t_critical`; 4.303 at n = 3), so the interval
    covers at its stated rate at the small n a run holds.

    Raises :class:`ValueError` if ``values`` has fewer than 2 elements or if
    ``z < 0``.
    """
    if z is not None and z < 0:
        raise ValueError(f"z must be >= 0, got {z}")
    mean = sample_mean(values)
    se = standard_error(values)
    crit = z if z is not None else t_critical(len(values) - 1)
    half_width = crit * se
    return (mean - half_width, mean + half_width)
