"""M33.8 — probabilistic-forecast calibration scoring.

Pure, closed-form scorers for how well an opaque agent's probabilistic
predictions (floats in ``[0, 1]``) match opaque binary outcomes (``bool``).
No randomness is involved, so no :class:`~alienbio.suite.dist.Seed` is
required — every function here is a deterministic function of its inputs:

- :func:`brier_score` — squared error of a single prediction against its
  realized outcome.
- :func:`mean_brier` — mean Brier score over a batch of (prediction, outcome)
  pairs.
- :func:`expected_calibration_error` — standard binned Expected Calibration
  Error (ECE): partitions ``[0, 1]`` into ``n_bins`` equal-width bins and
  measures the population-weighted gap between mean predicted probability and
  mean realized frequency within each non-empty bin.
"""

from __future__ import annotations

from typing import Sequence


def brier_score(pred: float, outcome: bool) -> float:
    """Squared error ``(pred - float(outcome)) ** 2`` for one forecast.

    ``pred`` must lie in ``[0.0, 1.0]``; raises :class:`ValueError` otherwise.
    Lower is better; a perfect forecast (``pred == float(outcome)``) scores 0.0.
    """
    if not (0.0 <= pred <= 1.0):
        raise ValueError(f"pred must be in [0.0, 1.0], got {pred!r}")
    return (pred - float(outcome)) ** 2


def mean_brier(preds: Sequence[float], outcomes: Sequence[bool]) -> float:
    """Mean per-item :func:`brier_score` over a batch of forecasts.

    Raises :class:`ValueError` if ``preds`` and ``outcomes`` differ in length
    or are empty.
    """
    if len(preds) != len(outcomes):
        raise ValueError(
            f"preds and outcomes must have equal length, got {len(preds)} vs {len(outcomes)}"
        )
    if not preds:
        raise ValueError("preds/outcomes must be non-empty")
    return sum(brier_score(p, o) for p, o in zip(preds, outcomes)) / len(preds)


def expected_calibration_error(
    preds: Sequence[float], outcomes: Sequence[bool], n_bins: int = 10
) -> float:
    """Standard binned Expected Calibration Error (ECE).

    Partitions ``[0, 1]`` into ``n_bins`` equal-width bins. For each non-empty
    bin, computes ``|mean(pred) - mean(outcome)|`` over the items landing in
    that bin, weights it by the bin's population fraction (``bin_count /
    total``), and returns the sum across bins.

    Bin membership is ``floor(pred / (1 / n_bins))``, clamped to
    ``n_bins - 1`` (so ``pred == 1.0`` always lands in the last bin rather
    than an out-of-range ``n_bins``-th bin). A prediction that sits exactly
    on an interior bin edge (a multiple of ``1 / n_bins``) lands in the bin
    *above* the edge when that multiple is exactly representable as a float
    (e.g. ``0.1``, ``0.5`` with ``n_bins=10``), and in the bin *below* the
    edge when floating-point rounding makes the division fall fractionally
    short (e.g. ``0.3``, ``0.7`` with ``n_bins=10``, since ``0.3 / 0.1`` ==
    ``2.9999999999999996``). This is deterministic for a given ``(pred,
    n_bins)`` pair but is a floating-point artifact, not a semantic choice —
    documented and tested explicitly below.

    Raises :class:`ValueError` if ``preds`` and ``outcomes`` differ in length,
    are empty, or ``n_bins < 1``.
    """
    if len(preds) != len(outcomes):
        raise ValueError(
            f"preds and outcomes must have equal length, got {len(preds)} vs {len(outcomes)}"
        )
    if not preds:
        raise ValueError("preds/outcomes must be non-empty")
    if n_bins < 1:
        raise ValueError(f"n_bins must be >= 1, got {n_bins}")

    for p in preds:
        if not (0.0 <= p <= 1.0):
            raise ValueError(f"pred must be in [0.0, 1.0], got {p!r}")

    bin_preds: list[list[float]] = [[] for _ in range(n_bins)]
    bin_outcomes: list[list[float]] = [[] for _ in range(n_bins)]
    width = 1.0 / n_bins
    for p, o in zip(preds, outcomes):
        idx = int(p / width)
        if idx >= n_bins:  # p == 1.0 lands exactly on the top edge
            idx = n_bins - 1
        bin_preds[idx].append(p)
        bin_outcomes[idx].append(float(o))

    total = len(preds)
    ece = 0.0
    for bp, bo in zip(bin_preds, bin_outcomes):
        if not bp:
            continue
        mean_pred = sum(bp) / len(bp)
        mean_outcome = sum(bo) / len(bo)
        ece += (len(bp) / total) * abs(mean_pred - mean_outcome)
    return ece
