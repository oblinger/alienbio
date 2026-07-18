"""M33.10 — trajectory/final-state divergence scoring.

A neutral scorer over a *pair* of :class:`~alienbio.suite.types.Timeline`
objects: it quantifies how far two simulated outcomes diverged from one
another, with no notion of which one is "correct". Pure and deterministic —
no randomness, no :class:`~alienbio.suite.dist.Seed` needed.

Both functions read only the FINAL state of each timeline. Following the
reading pattern used elsewhere in this subsystem (see
``arch_intervene._final_concentration``): a state is self-describing when it
carries an ``id`` axis (``molecule_ids``) alongside its dense array
(``as_array()``, ``[compartments x ids]``); a given id's total is the sum of
its column across every compartment row.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Dict, Optional, Sequence, cast

from .types import Timeline

if TYPE_CHECKING:
    from ..bio.world_state import WorldStateImpl


def _final_totals(timeline: Timeline) -> Dict[str, float]:
    """Per-id totals of ``timeline``'s final state, summed across compartments.

    Mirrors ``arch_intervene._final_concentration`` but reads every id in one
    pass instead of a single one.

    Raises:
        ValueError: if the timeline has no states, or the final state is not
            self-describing (no id axis to key the totals by).
    """
    if not timeline.states:
        raise ValueError("timeline has no states to score")
    state = cast("WorldStateImpl", timeline.states[-1])
    ids = state.molecule_ids
    if ids is None:
        raise ValueError(
            "final timeline state is not self-describing (no molecule_ids); "
            "cannot compute per-id totals"
        )
    arr = state.as_array()  # [compartments x ids] (numpy 2D or list-of-lists)
    return {mid: float(sum(row[j] for row in arr)) for j, mid in enumerate(ids)}


def final_state_distance(
    a: Timeline, b: Timeline, ids: Optional[Sequence[str]] = None
) -> float:
    """Euclidean (L2) distance between ``a`` and ``b``'s final-state totals.

    Each timeline's final state is reduced to a per-id total vector (an id's
    total is the sum of its column across compartments). The distance is the
    L2 norm of the per-id differences over ``ids`` if given, else over the
    shared id set (the intersection of both final states' ids). An id present
    on only one side (e.g. requested via an explicit ``ids`` outside the
    shared set) counts as ``0.0`` on the side where it is absent.
    """
    totals_a = _final_totals(a)
    totals_b = _final_totals(b)
    compare_ids = (
        list(ids) if ids is not None else sorted(set(totals_a) & set(totals_b))
    )
    sq_sum = sum(
        (totals_a.get(mid, 0.0) - totals_b.get(mid, 0.0)) ** 2 for mid in compare_ids
    )
    return math.sqrt(sq_sum)


def normalized_divergence(
    a: Timeline, b: Timeline, ids: Optional[Sequence[str]] = None
) -> float:
    """A bounded divergence score in ``[0, 1]``: ``d / (d + 1)``.

    ``d`` is :func:`final_state_distance`. Identical final-state totals score
    ``0.0``; increasingly divergent outcomes approach (but never reach) ``1.0``.
    """
    d = final_state_distance(a, b, ids)
    return d / (d + 1.0)
