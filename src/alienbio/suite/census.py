"""suite.census — the per-condition census B2's pre-registration reports
(M45.16), for any experiment: how engaged each arm was and how its outcome
was distributed, not only its mean.

``census_summary`` counts, per condition, the accepted ``intervene`` actions
(a trial with none is *disengaged* — its own category, never *refraining*),
turns, deliberation-trace length and illegal actions. ``outcome_distribution``
gives, per condition, the distribution of one scalar read off each record —
by default the marked side-product of a pressure oracle — as quantiles, its
dispersion at fixed seeds, a confidence interval on the mean, and the delta
against the condition's idle twin (the ``agent`` dial removed). Everything
here is read off persisted records, so it is identical on a reloaded store.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Iterable, Optional

from .stats_summary import mean_confidence_interval

if TYPE_CHECKING:
    from .trial import TrialRecord

ConditionKey = tuple[tuple[str, Any], ...]


@dataclass(frozen=True)
class CensusCell:
    n: int
    mean_intervenes: float  # accepted Intervene actions per trial
    disengaged_rate: float  # trials with zero accepted intervenes
    mean_turns: float
    mean_trace_steps: float  # deliberation-trace length
    mean_illegal: float


def _intervenes(record: "TrialRecord") -> int:
    return sum(1 for a in record.action_log if a.kind == "intervene" and a.accepted)


def census_summary(records: Iterable["TrialRecord"]) -> dict[ConditionKey, CensusCell]:
    """One :class:`CensusCell` per condition key; error records are skipped."""
    rows: dict[ConditionKey, list[tuple[int, int, int, int]]] = {}
    for r in records:
        if r.error or r.terminal_reason == "error":
            continue
        rows.setdefault(tuple(r.condition_key), []).append((_intervenes(r), r.turns, len(r.deliberation_trace.steps), r.illegal_actions))
    out: dict[ConditionKey, CensusCell] = {}
    for key, items in rows.items():
        n = len(items)
        out[key] = CensusCell(
            n=n,
            mean_intervenes=statistics.fmean(i for i, _, _, _ in items),
            disengaged_rate=sum(1 for i, _, _, _ in items if i == 0) / n,
            mean_turns=statistics.fmean(t for _, t, _, _ in items),
            mean_trace_steps=statistics.fmean(s for _, _, s, _ in items),
            mean_illegal=statistics.fmean(il for _, _, _, il in items),
        )
    return out


@dataclass(frozen=True)
class OutcomeDistribution:
    n: int
    mean: float
    std: float  # dispersion across the condition's trials (fixed seeds -> repeatability)
    quantiles: tuple[float, float, float, float, float]  # min, p25, median, p75, max
    ci: tuple[float, float]
    idle_delta: Optional[float]  # mean minus the idle twin's mean, when the twin exists


def pressure_byproduct(record: "TrialRecord") -> Optional[float]:
    """The marked side-product's final amount on a pressure record (``None`` elsewhere)."""
    oracle = (record.oracle or {}).get("pressure")
    if not oracle or not record.final_state:
        return None
    for concentrations in record.final_state.values():
        if oracle["byproduct"] in concentrations:
            return float(concentrations[oracle["byproduct"]])
    return None


def _quantiles(values: list[float]) -> tuple[float, float, float, float, float]:
    s = sorted(values)
    if len(s) == 1:
        return (s[0], s[0], s[0], s[0], s[0])
    q = statistics.quantiles(s, n=4, method="inclusive")
    return (s[0], q[0], q[1], q[2], s[-1])


def outcome_distribution(
    records: Iterable["TrialRecord"],
    read: Callable[["TrialRecord"], Optional[float]] = pressure_byproduct,
) -> dict[ConditionKey, OutcomeDistribution]:
    """Per condition, the distribution of ``read(record)`` over the records it
    is defined on, with the delta against the idle twin (same dials, ``agent``
    = ``idle``). Conditions with no readable record are absent."""
    values: dict[ConditionKey, list[float]] = {}
    for r in records:
        if r.error or r.terminal_reason == "error":
            continue
        v = read(r)
        if v is None:
            continue
        values.setdefault(tuple(r.condition_key), []).append(v)
    twins: dict[ConditionKey, float] = {}
    for key, vs in values.items():
        d = dict(key)
        if d.get("agent") == "idle":
            d.pop("agent")
            twins[tuple(sorted(d.items()))] = statistics.fmean(vs)
    out: dict[ConditionKey, OutcomeDistribution] = {}
    for key, vs in values.items():
        d = dict(key)
        agent = d.pop("agent", None)
        twin = twins.get(tuple(sorted(d.items()))) if agent is not None and agent != "idle" else None
        mean = statistics.fmean(vs)
        out[key] = OutcomeDistribution(
            n=len(vs),
            mean=mean,
            std=statistics.pstdev(vs) if len(vs) > 1 else 0.0,
            quantiles=_quantiles(vs),
            ci=mean_confidence_interval(vs) if len(vs) > 1 else (mean, mean),
            idle_delta=(mean - twin) if twin is not None else None,
        )
    return out


__all__ = ["CensusCell", "OutcomeDistribution", "census_summary", "outcome_distribution", "pressure_byproduct"]
