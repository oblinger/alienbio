"""M34.4 — condition-cell aggregation + 2×2 interaction contrast.

The reliability-map primitive: bin trial observations by an opaque condition
key and read cell means (and a spread) plus a 2×2 interaction effect between
two opaque factors. Pure, closed-form — no simulation, no randomness, no I/O.

- :class:`CellStats` — n / mean / sample std for one condition-cell.
- :func:`aggregate_cells` — group (condition_key, value) pairs by key and
  reduce each group to a :class:`CellStats`.
- :func:`cell_mean` — the mean for a single condition key.
- :func:`two_way_interaction` — the additive-interaction contrast of a 2×2
  design given its four cell means.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Mapping, Sequence


@dataclass(frozen=True)
class CellStats:
    """Summary statistics for one condition-cell.

    ``std`` is the sample (n - 1) standard deviation; it is ``0.0`` when
    ``n < 2`` (a single observation, or the empty case handled by callers,
    has no sample spread to estimate).
    """

    n: int
    mean: float
    std: float


def aggregate_cells(
    observations: Sequence[tuple[object, float]],
) -> dict[object, CellStats]:
    """Group ``(condition_key, value)`` pairs by key and reduce to :class:`CellStats`.

    ``observations`` is a flat sequence of (opaque condition key, numeric
    value) pairs; keys need only be hashable, their meaning is never
    inspected. Observations are grouped by key in first-seen order, and each
    group's values are reduced to their count, mean, and sample (n - 1)
    standard deviation (``0.0`` for a singleton group).

    An empty ``observations`` sequence returns an empty dict.
    """
    groups: dict[object, list[float]] = {}
    for key, value in observations:
        groups.setdefault(key, []).append(value)

    result: dict[object, CellStats] = {}
    for key, values in groups.items():
        n = len(values)
        mean = sum(values) / n
        std = statistics.stdev(values) if n >= 2 else 0.0
        result[key] = CellStats(n=n, mean=mean, std=std)
    return result


def cell_mean(observations: Sequence[tuple[object, float]], key: object) -> float:
    """Mean value of the observations whose condition key equals ``key``.

    Matching uses identity-or-equality (``k is key or k == key``), the same
    rule Python's own ``dict`` grouping uses (as :func:`aggregate_cells`
    relies on). This keeps the two functions consistent even for a
    self-unequal hashable key such as ``float('nan')``.

    Raises:
        KeyError: if no observation in ``observations`` carries ``key``.
    """
    values = [value for k, value in observations if k is key or k == key]
    if not values:
        raise KeyError(key)
    return sum(values) / len(values)


def two_way_interaction(cells: Mapping[tuple[object, object], float]) -> float:
    """Interaction contrast of a 2x2 design given its four cell means.

    ``cells`` maps ``(factor_a_level, factor_b_level)`` to that cell's mean.
    The two levels of each factor are inferred from the keys and then
    *sorted*: the smaller sorts first and is labeled ``a0``/``b0``, the
    larger is ``a1``/``b1`` (levels must therefore be mutually comparable,
    e.g. strings or ints — do not mix incomparable types within a factor).

    Returns the additive-interaction contrast::

        m[a1, b1] - m[a1, b0] - m[a0, b1] + m[a0, b0]

    A value of ``0.0`` means the two factors combine purely additively; a
    nonzero value is the size of the super-/sub-additive interaction.

    Raises:
        ValueError: if ``cells`` does not name exactly 2 distinct A-levels
            and exactly 2 distinct B-levels, or if any of the 4 required
            combinations is missing.
    """
    # `object` keys are not statically comparable, but the contract requires
    # mutually comparable level labels at runtime (see docstring above).
    a_levels = sorted({a for a, _ in cells.keys()})  # type: ignore[type-var]
    b_levels = sorted({b for _, b in cells.keys()})  # type: ignore[type-var]
    if len(a_levels) != 2:
        raise ValueError(f"expected exactly 2 A-levels, got {a_levels!r}")
    if len(b_levels) != 2:
        raise ValueError(f"expected exactly 2 B-levels, got {b_levels!r}")

    a0, a1 = a_levels
    b0, b1 = b_levels
    required = [(a0, b0), (a0, b1), (a1, b0), (a1, b1)]
    missing = [combo for combo in required if combo not in cells]
    if missing:
        raise ValueError(f"missing required cell combination(s): {missing!r}")

    return cells[(a1, b1)] - cells[(a1, b0)] - cells[(a0, b1)] + cells[(a0, b0)]
