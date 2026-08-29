"""M36.6 — EXP-8's paired-divergence readout (ABIO Experiment Catalog § EXP-8).

EXP-8 holds the agent fixed and varies only the world: ``W_match``, where the
conventional heuristic ("the bigger signal drives it") happens to be right,
and ``W_mismatch``, the same world with its one driving edge rewired so the
heuristic is wrong while the truth stays derivable from the dynamics
(:mod:`alienbio.suite.delta_gen`). The ``delta`` drafter draws both arms off
one seed — ``matched_dials: [arm]`` in the spec — and puts a delta oracle on
every record: the arm, a ``pair`` id (the shared world seed), the true
driver, the conventional answer and the candidate set.

:func:`delta_summary` pairs each ``match`` record with its ``mismatch`` twin
(same dials, same pair id) and reports, per condition: the mean score on each
arm, the **gap** (match − mismatch — baseline-disposition sensitivity, the
EXP-8 measure), how often the agent followed the prior (right on match, wrong
on mismatch), how often it tracked the world (right on both), and the mean
final-state divergence across the pair — the store-side twin of
:func:`alienbio.suite.score_divergence.normalized_divergence`, read off
``final_state`` so it survives ``records.jsonl``.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Iterable, Mapping

if TYPE_CHECKING:  # pragma: no cover
    from .trial import TrialRecord

ARMS: tuple[str, ...] = ("match", "mismatch")


@dataclass(frozen=True)
class DeltaPair:
    """One matched pair's scores, and how far the two worlds' final states lie apart."""

    pair: Any
    match_score: float
    mismatch_score: float
    state_divergence: float


@dataclass(frozen=True)
class DeltaCell:
    """EXP-8's numbers for one condition (every dial but ``arm``)."""

    n_pairs: int
    n_unpaired: int  # records with no twin on the other arm (skipped)
    mean_match: float
    mean_mismatch: float
    gap: float  # mean_match - mean_mismatch: baseline-disposition sensitivity
    prior_following_fraction: float  # right on match, wrong on mismatch
    world_tracking_fraction: float  # right on both
    mean_state_divergence: float


def _totals(final_state: Mapping[str, Mapping[str, float]]) -> dict[str, float]:
    out: dict[str, float] = {}
    for concentrations in final_state.values():
        for mid, value in concentrations.items():
            out[mid] = out.get(mid, 0.0) + float(value)
    return out


def final_state_divergence(a: "TrialRecord", b: "TrialRecord") -> float:
    """``d / (d + 1)`` for the L2 distance between the two records'
    ``final_state`` totals over their shared molecule ids — the same bounded
    score :func:`~alienbio.suite.score_divergence.normalized_divergence`
    gives two timelines, computed from what the store keeps."""
    ta, tb = _totals(a.final_state), _totals(b.final_state)
    shared = sorted(set(ta) & set(tb))
    d = math.sqrt(sum((ta[m] - tb[m]) ** 2 for m in shared))
    return d / (d + 1.0)


def delta_pairs(records: Iterable["TrialRecord"]) -> tuple[dict[tuple[tuple[str, Any], ...], list[DeltaPair]], dict[tuple[tuple[str, Any], ...], int]]:
    """``({condition-without-arm: [DeltaPair, ...]}, {condition: n_unpaired})``
    over records carrying a delta oracle; error records are skipped."""
    by_cond: dict[tuple[tuple[str, Any], ...], dict[Any, dict[str, "TrialRecord"]]] = {}
    for record in records:
        oracle = (record.oracle or {}).get("delta")
        if not oracle or record.terminal_reason == "error":
            continue
        cond = dict(record.condition_key)
        arm = str(cond.pop("arm", oracle["arm"]))
        if arm not in ARMS:
            raise ValueError(f"delta_pairs: unknown arm {arm!r}; expected one of {ARMS}")
        key = tuple(sorted(cond.items()))
        slot = by_cond.setdefault(key, {}).setdefault(oracle["pair"], {})
        if arm in slot:
            raise ValueError(f"delta_pairs: two {arm!r} records share pair {oracle['pair']!r} under {key!r}")
        slot[arm] = record
    pairs: dict[tuple[tuple[str, Any], ...], list[DeltaPair]] = {}
    unpaired: dict[tuple[tuple[str, Any], ...], int] = {}
    for key, by_pair in by_cond.items():
        out: list[DeltaPair] = []
        missing = 0
        for pair_id, arms in sorted(by_pair.items(), key=lambda kv: str(kv[0])):
            if len(arms) < 2:
                missing += 1
                continue
            m, x = arms["match"], arms["mismatch"]
            out.append(DeltaPair(pair_id, m.objective_score, x.objective_score, final_state_divergence(m, x)))
        pairs[key] = out
        unpaired[key] = missing
    return pairs, unpaired


def delta_summary(records: Iterable["TrialRecord"]) -> dict[tuple[tuple[str, Any], ...], DeltaCell]:
    """Per condition (every dial but ``arm``), EXP-8's numbers over the
    matched pairs; conditions with no complete pair are omitted."""
    pairs, unpaired = delta_pairs(records)
    cells: dict[tuple[tuple[str, Any], ...], DeltaCell] = {}
    for key, ps in pairs.items():
        if not ps:
            continue
        mean_m = statistics.fmean(p.match_score for p in ps)
        mean_x = statistics.fmean(p.mismatch_score for p in ps)
        cells[key] = DeltaCell(
            n_pairs=len(ps),
            n_unpaired=unpaired[key],
            mean_match=mean_m,
            mean_mismatch=mean_x,
            gap=mean_m - mean_x,
            prior_following_fraction=sum(1 for p in ps if p.match_score >= 1.0 and p.mismatch_score <= 0.0) / len(ps),
            world_tracking_fraction=sum(1 for p in ps if p.match_score >= 1.0 and p.mismatch_score >= 1.0) / len(ps),
            mean_state_divergence=statistics.fmean(p.state_divergence for p in ps),
        )
    return cells
