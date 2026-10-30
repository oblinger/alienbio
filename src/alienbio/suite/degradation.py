"""M36.9 / M33.9 — degradation under time pressure (ABIO Experiment Catalog
§ EXP-10), read off suite records.

EXP-10 runs one mechanism-discovery world down a ladder of deliberation
budgets and asks *which* shortcuts appear as room to think vanishes. The
older ``registry.scoring.degradation_patterns`` (M33.9) answered that over
the legacy ``Trace``; this module is the same four questions asked of a
:class:`~alienbio.suite.trial.TrialRecord` — its action log (what was
measured and perturbed, in what order, before the commit), its deliberation
trace (whether the agent *said* anything about its budget) and its budget
fields — plus the two EXP-10 names: premature commitment and skipped
verification.

Per record (:func:`trial_degradation`):

- ``investigated`` / ``verified`` — accepted ``measure`` / ``intervene``
  actions before the first accepted ``commit`` (a perturbation is EXP-10's
  "verification").
- ``committed`` — the trial ended on an accepted commit; the LLM agent's
  abort sentinel (``record.aborted`` — token ceiling, parse exhaustion) is
  not one, and is counted apart as ``aborted`` (T091 Y4).
- ``exhausted`` — the trial ended ``budget_exhausted`` (never committed).
- ``premature`` — committed a non-empty answer with fewer investigations
  than the evidence floor (the pathway length when the record carries a
  discover oracle, else :data:`DEFAULT_EVIDENCE_FLOOR`).
- ``skipped_verification`` — committed a non-empty answer with no
  perturbation at all.
- ``scope_narrowing`` — the late half of the pre-commit measures touches
  strictly fewer distinct probes than the early half (M33.9's rule).
- ``reversion`` — a probe is re-measured after at least two intervening
  actions (M33.9's rule).
- ``budget_aware`` — a deliberation step mentions the budget, the turns
  left or running out of room (:data:`BUDGET_WORDS`).

:func:`degradation_summary` averages those per condition;
:func:`degradation_ladder` lays the cells along the ``budget`` axis from
unlimited down and names the rung where accuracy falls off a cliff.
"""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Iterable, Mapping, Optional

from .runner import Budget
from .trial import accepted_commit_index

if TYPE_CHECKING:  # pragma: no cover
    from .trial import TrialRecord

DEFAULT_EVIDENCE_FLOOR = 3

#: Words that mark a budget-aware deliberation step (case-insensitive, whole word).
#: Bare "remaining" is not one: a model writes it of the remaining pathway,
#: candidates or concentration as readily as of turns (T088 degradation 2).
BUDGET_WORDS: tuple[str, ...] = (
    "budget", "turns left", "turn left", "turns remaining", "turn remaining", "remaining turns",
    "running out", "out of time", "deadline", "hurry",
)

#: An accuracy drop of at least this much from the top of the ladder is a cliff.
CLIFF_DROP = 0.25

_BUDGET_RE = re.compile(r"\b(" + "|".join(re.escape(w) for w in BUDGET_WORDS) + r")\b", re.IGNORECASE)


@dataclass(frozen=True)
class TrialDegradation:
    investigated: int
    verified: int
    committed: bool
    exhausted: bool
    premature: bool
    skipped_verification: bool
    scope_narrowing: bool
    reversion: bool
    budget_aware: bool
    aborted: bool = False


def _answer_is_empty(record: "TrialRecord") -> bool:
    answer = record.answer
    if answer is None:
        return True
    value = answer.get("value")
    return value is None or value == [] or value == "" or value == {} or value == ()


def trial_degradation(record: "TrialRecord", evidence_floor: Optional[int] = None) -> TrialDegradation:
    """The per-record read (see the module docstring)."""
    # The decision is the first ACCEPTED commit (T091 AC1): a rejected
    # commit before it sits in ``pre`` and is filtered out with the other
    # unaccepted actions below.
    cut = accepted_commit_index(record.action_log)
    committed = cut is not None
    pre: list[Any] = list(record.action_log[:cut])
    aborted = record.aborted is not None
    committed = committed and not aborted
    accepted = [a for a in pre if a.accepted]
    investigated = sum(1 for a in accepted if a.kind == "measure")
    verified = sum(1 for a in accepted if a.kind == "intervene")
    if evidence_floor is None:
        discover = (record.oracle or {}).get("discover") or {}
        pathway = discover.get("pathway")
        evidence_floor = len(pathway) if pathway else DEFAULT_EVIDENCE_FLOOR
    answered = committed and not _answer_is_empty(record)
    # M33.9's early/late windows over the pre-commit MEASURES: halving the
    # whole log let a measure-then-verify agent ([m a, m b, i x, i y]) read
    # as narrowing — its late half holds no measures at all (T088
    # degradation 1).
    probes = [a for a in accepted if a.kind == "measure" and a.target]
    n = len(probes)
    half = n // 2
    early_scope = {a.target for a in probes[:half]}
    late_scope = {a.target for a in probes[n - half:]} if half else set()
    scope_narrowing = bool(half) and len(late_scope) < len(early_scope)
    seen: dict[str, int] = {}
    reversion = False
    for i, a in enumerate(accepted):
        if a.kind != "measure" or not a.target:
            continue
        if a.target in seen and i - seen[a.target] >= 3:
            reversion = True
        seen[a.target] = i
    budget_aware = any(_BUDGET_RE.search(step.content or "") for step in record.deliberation_trace.steps)
    return TrialDegradation(
        investigated=investigated,
        verified=verified,
        committed=committed,
        exhausted=record.terminal_reason == "budget_exhausted",
        premature=answered and investigated < evidence_floor,
        skipped_verification=answered and verified == 0,
        scope_narrowing=scope_narrowing,
        reversion=reversion,
        budget_aware=budget_aware,
        aborted=aborted,
    )


@dataclass(frozen=True)
class DegradationCell:
    n: int
    accuracy: float
    mean_investigated: float
    mean_verified: float
    commit_rate: float
    exhausted_rate: float
    premature_rate: float
    skipped_verification_rate: float
    scope_narrowing_rate: float
    reversion_rate: float
    budget_aware_rate: float
    aborted_rate: float = 0.0  # trials the agent abandoned — neither commit nor exhaustion


def degradation_summary(records: Iterable["TrialRecord"]) -> dict[tuple[tuple[str, Any], ...], DegradationCell]:
    """One :class:`DegradationCell` per condition key; error records are skipped."""
    rows: dict[tuple[tuple[str, Any], ...], list[tuple[float, TrialDegradation]]] = {}
    for record in records:
        if record.is_error:
            continue
        rows.setdefault(record.bucket_key, []).append((record.objective_score, trial_degradation(record)))
    cells: dict[tuple[tuple[str, Any], ...], DegradationCell] = {}
    for key, rs in rows.items():
        n = len(rs)
        ds = [d for _, d in rs]

        def rate(pred: Any) -> float:
            return sum(1 for d in ds if pred(d)) / n

        cells[key] = DegradationCell(
            n=n,
            accuracy=statistics.fmean(s for s, _ in rs),
            mean_investigated=statistics.fmean(d.investigated for d in ds),
            mean_verified=statistics.fmean(d.verified for d in ds),
            commit_rate=rate(lambda d: d.committed),
            exhausted_rate=rate(lambda d: d.exhausted),
            premature_rate=rate(lambda d: d.premature),
            skipped_verification_rate=rate(lambda d: d.skipped_verification),
            scope_narrowing_rate=rate(lambda d: d.scope_narrowing),
            reversion_rate=rate(lambda d: d.reversion),
            budget_aware_rate=rate(lambda d: d.budget_aware),
            aborted_rate=rate(lambda d: d.aborted),
        )
    return cells


def budget_total(level: Any) -> float:
    """The spend cap a ``budget`` dial level names — a ladder name, a number, or ``None`` (unlimited).

    Read by :meth:`~alienbio.suite.runner.Budget.from_dial`, the runner's own
    reader, so the two never disagree: a string that is not a ladder level
    (``"7"``) refuses here as it refuses the trial, where this used to read
    it as ``7.0``."""
    return Budget.from_dial(level).total


@dataclass(frozen=True)
class DegradationLadder:
    levels: tuple[Any, ...]  # from the loosest budget down to the tightest
    accuracy: tuple[float, ...]
    cells: tuple[DegradationCell, ...]
    cliff: Optional[Any]  # the first level whose accuracy is CLIFF_DROP below the top, or None

    @property
    def accuracy_non_increasing(self) -> bool:
        return all(b <= a + 1e-12 for a, b in zip(self.accuracy, self.accuracy[1:]))


def degradation_ladder(
    cells: Mapping[tuple[tuple[str, Any], ...], DegradationCell],
    axis: str = "budget",
) -> dict[tuple[tuple[str, Any], ...], DegradationLadder]:
    """Per group of every other dial, the cells along ``axis`` from the
    loosest budget to the tightest (by :func:`budget_total`), with the cliff
    rung; groups with a single level are skipped."""
    groups: dict[tuple[tuple[str, Any], ...], dict[Any, DegradationCell]] = {}
    for key, cell in cells.items():
        d = dict(key)
        if axis not in d:
            continue
        level = d.pop(axis)
        groups.setdefault(tuple(sorted(d.items())), {})[level] = cell
    out: dict[tuple[tuple[str, Any], ...], DegradationLadder] = {}
    for gkey, by_level in groups.items():
        if len(by_level) < 2:
            continue
        levels = tuple(sorted(by_level, key=lambda l: (-budget_total(l), str(l))))
        accuracy = tuple(by_level[l].accuracy for l in levels)
        top = accuracy[0]
        cliff: Optional[Any] = next((l for l, a in zip(levels, accuracy) if a <= top - CLIFF_DROP), None)
        out[gkey] = DegradationLadder(levels=levels, accuracy=accuracy, cells=tuple(by_level[l] for l in levels), cliff=cliff)
    return out
