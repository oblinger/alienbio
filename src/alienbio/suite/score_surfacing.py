"""M33.4 — per-objective surfacing detection + depth-sweep convergence.

Pure, domain-neutral functions over a generic *event list*: a sequence of
``(turn, objective_id)`` pairs meaning "``objective_id`` was surfaced at
``turn``". This module does not depend on the deliberation module or any
other suite subsystem — it operates purely on opaque ``(int, str)`` pairs.

- :func:`surfacing_depth` — earliest turn a given objective was surfaced.
- :func:`surfacing_profile` — :func:`surfacing_depth` for a batch of ids.
- :func:`coverage_at_budget` — which objectives were surfaced by a turn
  budget (inclusive).
- :func:`is_monotone_coverage` — guard/assertion utility checking that
  coverage is non-decreasing (by set inclusion) as the turn budget grows.
  Over a *fixed* event list, coverage is always monotone by construction
  (a larger budget can only admit more events, never fewer) — this checker
  exists as a sanity guard for callers who assemble coverage sets some other
  way (e.g. from a cache or a partial replay) where that invariant could be
  violated by a bug.
"""

from __future__ import annotations

from typing import Optional, Sequence


def surfacing_depth(
    events: Sequence[tuple[int, str]], objective_id: str
) -> Optional[int]:
    """Earliest turn ``objective_id`` was surfaced in ``events``.

    Returns ``None`` if ``objective_id`` never appears in ``events``.
    """
    turns = [turn for turn, oid in events if oid == objective_id]
    if not turns:
        return None
    return min(turns)


def surfacing_profile(
    events: Sequence[tuple[int, str]], objective_ids: Sequence[str]
) -> dict[str, Optional[int]]:
    """:func:`surfacing_depth` for every id in ``objective_ids``.

    Returns a dict keyed by every id in ``objective_ids`` (order preserved),
    mapping to its earliest surfacing turn or ``None`` if never surfaced.
    """
    return {oid: surfacing_depth(events, oid) for oid in objective_ids}


def coverage_at_budget(
    events: Sequence[tuple[int, str]],
    objective_ids: Sequence[str],
    budget: int,
) -> frozenset[str]:
    """Objective ids (from ``objective_ids``) surfaced at some turn ``<= budget``.

    The boundary is inclusive: an objective surfaced exactly at ``budget``
    counts as covered.
    """
    ids = set(objective_ids)
    return frozenset(
        oid for turn, oid in events if oid in ids and turn <= budget
    )


def _is_monotone_sets(coverage_sets: Sequence[frozenset[str]]) -> bool:
    """True iff each set in ``coverage_sets`` is a subset of the next one.

    Internal helper used both by :func:`is_monotone_coverage` (over
    real, derived coverage) and directly by tests (over hand-built
    synthetic coverage sequences) to prove the checker itself is correct.
    """
    for earlier, later in zip(coverage_sets, coverage_sets[1:]):
        if not earlier <= later:
            return False
    return True


def is_monotone_coverage(
    events: Sequence[tuple[int, str]],
    objective_ids: Sequence[str],
    budgets: Sequence[int],
) -> bool:
    """True iff coverage is non-decreasing (set inclusion) as budgets grow.

    ``budgets`` is sorted ascending internally before the sweep. Over a
    fixed ``events`` list this is always ``True`` by construction (a larger
    budget can only admit events a smaller budget already admitted, never
    drop them); this function is a guard/assertion utility for callers to
    verify that invariant holds for their particular event/budget inputs
    rather than a check that could meaningfully fail here. An empty
    ``budgets`` sequence is vacuously monotone (``True``).
    """
    sorted_budgets = sorted(budgets)
    coverage_sets = [
        coverage_at_budget(events, objective_ids, b) for b in sorted_budgets
    ]
    return _is_monotone_sets(coverage_sets)
