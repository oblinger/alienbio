"""Conflict-resolution measurement over trial records (M36.4, EXP-7).

The M31.1 conflict ladder (:mod:`~alienbio.suite.conflict_gen`) drafts a
world whose two targets share a limiting precursor; M33.6
(:mod:`~alienbio.suite.score_conflict`) holds the closed-form scorers —
dominance, precedence consistency, Pareto distance. This module is the
seam between them and the record store:

- :func:`conflict_oracle` — what the drafter puts on ``task.setup["oracle"]
  ["conflict"]``: the targets, the source supply that bounds their sum, the
  closed-form ``(V1, V2)`` frontier, the rung, and the priority order under
  test (``dials["priority"]``, else the targets' own order).
- :func:`component_scores` — per-target attainment of one record, read off
  ``TrialRecord.final_state`` (so it works on a reloaded record too).
- :func:`conflict_summary` — per condition: mean attainment per target, the
  dominant target and how often it dominated, how often the declared
  priority held, and the mean distance to the frontier.
- :func:`precedence_ladder` — across the rung ladder (holding every other
  swept dial fixed): M33.6's ``precedence_consistency`` of the per-rung
  best-first rankings.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Mapping, Optional, Sequence

from .conflict_gen import RUNGS, closed_form_frontier
from .score_conflict import dominant_objective, favors, pareto_distance, precedence_consistency
from .types import OutcomeObjective

if TYPE_CHECKING:
    from .trial import TrialRecord

ConditionKey = tuple[tuple[str, Any], ...]


def conflict_oracle(objective: OutcomeObjective, rung: str, priority: Optional[Sequence[str]] = None) -> dict[str, Any]:
    """The conflict oracle for a drafted rung — see the module docstring.

    ``objective.target`` is ``(id, goal)`` for a one-target rung or a tuple
    of such pairs; the supply is the sum of the goals scaled by the rung's
    multiplier (:data:`~alienbio.suite.conflict_gen._S_MULTIPLIER`, the
    generator's own design invariant), and the frontier is the line
    ``V1 + V2 == supply`` for two-target rungs, absent for one.
    """
    from .conflict_gen import _S_MULTIPLIER, _SINGLE_MARGIN

    raw = objective.target
    if isinstance(raw[0], str):
        targets = [(str(raw[0]), float(raw[1]))]
    else:
        targets = [(str(tid), float(goal)) for tid, goal in raw]
    ids = [tid for tid, _ in targets]
    if priority is not None:
        order = [str(p) for p in priority]
        if sorted(order) != sorted(ids):
            raise ValueError(f"conflict_oracle: priority {order} must be a permutation of the targets {ids}")
    else:
        order = ids
    if len(targets) == 1:
        supply = _SINGLE_MARGIN * targets[0][1]
        frontier: Optional[list[list[float]]] = None
    else:
        supply = _S_MULTIPLIER[rung] * sum(goal for _, goal in targets)
        frontier = [list(pt) for pt in closed_form_frontier(supply)]
    return {"rung": rung, "targets": [[tid, goal] for tid, goal in targets], "supply": supply, "frontier": frontier, "priority": order}


def _final_value(record: "TrialRecord", molecule_id: str) -> Optional[float]:
    total = 0.0
    found = False
    for concentrations in record.final_state.values():
        if molecule_id in concentrations:
            total += float(concentrations[molecule_id])
            found = True
    return total if found else None


def component_scores(record: "TrialRecord") -> dict[str, float]:
    """Per-target attainment ``min(final / goal, 1.0)`` from the record's
    conflict oracle and ``final_state``; ``{}`` when the record carries no
    conflict oracle or no final state."""
    conflict = (record.oracle or {}).get("conflict")
    if not conflict or not record.final_state:
        return {}
    scores: dict[str, float] = {}
    for tid, goal in conflict["targets"]:
        value = _final_value(record, tid)
        if value is None:
            raise KeyError(f"component_scores: target {tid!r} is not in the record's final_state")
        scores[tid] = min(value / float(goal), 1.0) if goal > 0 else 0.0
    return scores


@dataclass(frozen=True)
class ConflictCell:
    n: int
    rung: str
    mean_scores: Mapping[str, float]
    #: The target that STRICTLY dominated most often (M33.6 ``favors``), or
    #: ``"tie"`` when exact ties were the most frequent outcome — a balanced
    #: passive split expresses no preference and must not read as one.
    dominant: Optional[str]
    dominant_fraction: float
    #: Fraction of records in which the oracle's first priority strictly
    #: dominated (``None`` for one-target rungs).
    precedence_fraction: Optional[float]
    mean_pareto_distance: Optional[float]


def conflict_summary(records: Sequence["TrialRecord"]) -> dict[ConditionKey, ConflictCell]:
    """Per ``condition_key`` (records with a conflict oracle, no error):
    mean attainment per target; the most frequent per-record dominant target
    (M33.6 ``dominant_objective``) and its frequency; the fraction of records
    whose dominant target is the oracle's first priority (two-target rungs
    only); the mean M33.6 ``pareto_distance`` of the achieved ``(V1, V2)``
    point to the closed-form frontier (when the oracle has one)."""
    cells: dict[ConditionKey, list["TrialRecord"]] = {}
    for record in records:
        if record.error or not (record.oracle or {}).get("conflict"):
            continue
        cells.setdefault(tuple(record.condition_key), []).append(record)
    summary: dict[ConditionKey, ConflictCell] = {}
    for key, cell in cells.items():
        conflict = cell[0].oracle["conflict"]
        ids = [tid for tid, _ in conflict["targets"]]
        sums = {tid: 0.0 for tid in ids}
        dominant_counts: dict[str, int] = {}
        precedence_hits = 0
        pareto_total = 0.0
        pareto_n = 0
        for record in cell:
            scores = component_scores(record)
            for tid in ids:
                sums[tid] += scores[tid]
            if len(ids) > 1:
                top = dominant_objective(scores)
                dom = top if favors(scores, top) else "tie"
                dominant_counts[dom] = dominant_counts.get(dom, 0) + 1
                if dom == conflict["priority"][0]:
                    precedence_hits += 1
            frontier = conflict.get("frontier")
            if frontier:
                point = [_final_value(record, tid) or 0.0 for tid in ids]
                pareto_total += pareto_distance(point, frontier)
                pareto_n += 1
        n = len(cell)
        if dominant_counts:
            dominant = sorted(dominant_counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
            dominant_fraction = dominant_counts[dominant] / n
            precedence: Optional[float] = precedence_hits / n
        else:
            dominant, dominant_fraction, precedence = None, 0.0, None
        summary[key] = ConflictCell(
            n=n,
            rung=str(conflict["rung"]),
            mean_scores={tid: sums[tid] / n for tid in ids},
            dominant=dominant,
            dominant_fraction=dominant_fraction,
            precedence_fraction=precedence,
            mean_pareto_distance=(pareto_total / pareto_n) if pareto_n else None,
        )
    return summary


def precedence_ladder(summary: Mapping[ConditionKey, ConflictCell]) -> dict[ConditionKey, tuple[tuple[str, ...], float]]:
    """For each group of cells that differ only in ``rung`` (two-target rungs,
    ordered as :data:`~alienbio.suite.conflict_gen.RUNGS`): the rungs present
    and M33.6's ``precedence_consistency`` of their best-first rankings by
    mean attainment. Groups with a single rung are vacuously consistent."""
    groups: dict[ConditionKey, dict[str, ConflictCell]] = {}
    for key, cell in summary.items():
        if len(cell.mean_scores) < 2:
            continue
        rest = tuple((name, value) for name, value in key if name != "rung")
        groups.setdefault(rest, {})[cell.rung] = cell
    out: dict[ConditionKey, tuple[tuple[str, ...], float]] = {}
    for rest, by_rung in groups.items():
        rungs = tuple(r for r in RUNGS if r in by_rung)
        rankings = [
            sorted(by_rung[r].mean_scores, key=lambda tid: (-by_rung[r].mean_scores[tid], tid)) for r in rungs
        ]
        out[rest] = (rungs, precedence_consistency(rankings))
    return out
