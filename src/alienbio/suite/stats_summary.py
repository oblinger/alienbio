"""M34.3 — single-sample summary statistics + confidence interval.

Pure, closed-form descriptive statistics over a single sample of plain
``float`` values. No randomness, no simulation, no I/O:

- :func:`sample_mean` — arithmetic mean.
- :func:`sample_variance` — unbiased (``n - 1``) sample variance.
- :func:`sample_std` — sample standard deviation (``sqrt`` of the variance).
- :func:`standard_error` — standard error of the mean (``std / sqrt(n)``).
- :func:`mean_confidence_interval` — ``(mean - z*se, mean + z*se)`` using a
  caller-supplied critical value ``z`` (default: the ~95% two-sided normal
  critical value). No stats library is consulted internally: the critical
  value is always passed in, with a documented default.
"""

from __future__ import annotations

import math
from typing import Sequence


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
    values: Sequence[float], z: float = 1.959963984540054
) -> tuple[float, float]:
    """Confidence interval for the sample mean: ``(mean - z*se, mean + z*se)``.

    ``z`` is a caller-supplied critical value (a normal or ``t`` multiplier);
    the default ``1.959963984540054`` is the standard two-sided ~95% normal
    critical value. This function never looks up a critical value itself.

    Raises :class:`ValueError` if ``values`` has fewer than 2 elements or if
    ``z < 0``.
    """
    if z < 0:
        raise ValueError(f"z must be >= 0, got {z}")
    mean = sample_mean(values)
    se = standard_error(values)
    half_width = z * se
    return (mean - half_width, mean + half_width)
