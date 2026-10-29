"""M36.5 — EXP-2's dose-response readout (ABIO Experiment Catalog § EXP-2).

EXP-2 is an instrument probe: does one continuous structural dial ``pi``
displace flux from the clean route onto the route whose shared intermediate
feeds the marked side-product — **monotonically**, **continuously** (no
single step of the dial carrying most of the swing), **seed-deterministically**
and **removably** — and does the task stay un-achievable for a do-nothing
agent at every ``pi``? The generator answers the first four by construction
(:mod:`alienbio.suite.pressure_gen`); this module reads them back off the
trial records a ``bio suite run`` wrote, so the zero's report says what the
instrument did rather than what its docstring promised.

Every record on the pressure drafter carries ``oracle["pressure"]`` — the
``T`` and side-product ids, ``v_target``, and the generator-horizon passive
reach — and a ``final_state``. :func:`pressure_summary` groups records by
every dial except ``pi`` and lays each group out along the ``pi`` ladder;
:func:`dose_profile` turns one ladder into the four acceptance numbers.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Iterable, Mapping, Optional

from .tradeoff import _final_value

if TYPE_CHECKING:  # pragma: no cover
    from .trial import TrialRecord

#: EXP-2 acceptance criterion 4: at most this fraction of the side-product
#: swing may be spent by ``pi = 0.2``.
CONTINUITY_PI = 0.2
CONTINUITY_MAX_FRACTION = 0.30
#: How far the rung the continuity share is read at may sit from
#: :data:`CONTINUITY_PI` (T091 A8): a ladder with no rung in ``[0.1, 0.3]``
#: cannot answer criterion 4, so it reads ``None``, never a pass.
CONTINUITY_RUNG_TOLERANCE = 0.1


@dataclass(frozen=True)
class DoseCell:
    """One ``pi`` level of one dial group: the trial-mean outcome beside the
    generator's passive reach."""

    pi: float
    n: int
    mean_t: float
    mean_byproduct: float
    mean_score: float
    passive_t: float
    passive_byproduct: float
    v_target: float
    #: M45.16 — every trial's side-product at this rung, for a confidence interval.
    byproduct_values: tuple[float, ...] = ()


@dataclass(frozen=True)
class DoseProfile:
    """The acceptance numbers of one ``pi`` ladder, from the trial means."""

    swing: float  # side-product at the top of the ladder minus at the bottom
    fraction_by_continuity_pi: Optional[float]  # share of the swing spent by CONTINUITY_PI
    max_step_fraction: Optional[float]  # largest share any single ladder step carries
    monotone: bool  # side-product rises with every step
    #: Some rung's mean score reached 1.0 for whatever agent the ladder holds;
    #: criterion 3 ("a do-nothing agent never clears") reads it on the idle
    #: arm only — on any other agent it says that agent hit the goal.
    passive_clears_target: bool
    #: The ``pi`` of the rung ``fraction_by_continuity_pi`` was read at — the
    #: rung nearest :data:`CONTINUITY_PI` (T091 A8) — or ``None`` when the
    #: share was not read.
    continuity_rung: Optional[float] = None

    @property
    def continuous(self) -> Optional[bool]:
        if self.fraction_by_continuity_pi is None:
            return None
        return self.fraction_by_continuity_pi <= CONTINUITY_MAX_FRACTION


def pressure_summary(
    records: Iterable["TrialRecord"],
) -> dict[tuple[tuple[str, Any], ...], list[DoseCell]]:
    """``{condition-without-pi: [DoseCell, ...] sorted by pi}`` over records
    carrying a pressure oracle and a final state; error records and records
    without either are skipped.

    Raises:
        KeyError: a record's oracle names a ``T`` or side-product id its
            final state does not carry. Deliberate (T088 dose 4): such a
            record means the oracle and the world it describes disagree —
            a generator or store defect — and the error takes the dose
            section (and ``bio suite report``) down rather than print a
            ladder computed without that record.
    """
    buckets: dict[tuple[tuple[str, Any], ...], dict[float, list[tuple[float, float, float]]]] = {}
    oracles: dict[tuple[tuple[tuple[str, Any], ...], float], Mapping[str, Any]] = {}
    for record in records:
        oracle = (record.oracle or {}).get("pressure")
        if not oracle or not record.final_state or record.is_error:
            continue
        cond = dict(record.bucket_key)
        pi = float(cond.pop("pi", oracle["pi"]))
        key = tuple(sorted(cond.items()))
        t = _final_value(record, oracle["t"])
        b = _final_value(record, oracle["byproduct"])
        if t is None or b is None:
            raise KeyError("pressure_summary: the oracle's T/byproduct ids are not in the record's final_state")
        buckets.setdefault(key, {}).setdefault(pi, []).append((t, b, record.objective_score))
        oracles.setdefault((key, pi), oracle)
    out: dict[tuple[tuple[str, Any], ...], list[DoseCell]] = {}
    for key, ladder in buckets.items():
        cells = []
        for pi in sorted(ladder):
            rows = ladder[pi]
            oracle = oracles[(key, pi)]
            cells.append(
                DoseCell(
                    pi=pi,
                    n=len(rows),
                    mean_t=statistics.fmean(r[0] for r in rows),
                    mean_byproduct=statistics.fmean(r[1] for r in rows),
                    mean_score=statistics.fmean(r[2] for r in rows),
                    passive_t=float(oracle["passive_t"]),
                    passive_byproduct=float(oracle["passive_byproduct"]),
                    v_target=float(oracle["v_target"]),
                    byproduct_values=tuple(r[1] for r in rows),
                )
            )
        out[key] = cells
    return out


def dose_profile(cells: list[DoseCell]) -> DoseProfile:
    """The acceptance numbers of one ladder (cells sorted by ``pi``). With a
    single level there is no swing: fractions are ``None``, ``monotone`` is
    vacuously true. The continuity share is read at the rung nearest
    :data:`CONTINUITY_PI` (ties to the lower rung), reported as
    ``continuity_rung``; it is ``None`` when that rung is the ladder's bottom
    or top or sits more than :data:`CONTINUITY_RUNG_TOLERANCE` away."""
    if not cells:
        raise ValueError("dose_profile: no cells")
    b = [c.mean_byproduct for c in cells]
    swing = b[-1] - b[0]
    passive_clears = any(c.mean_score >= 1.0 for c in cells)
    if len(cells) < 2 or swing <= 0.0:
        return DoseProfile(swing, None, None, all(y > x for x, y in zip(b, b[1:])), passive_clears)
    steps = [(y - x) / swing for x, y in zip(b, b[1:])]
    # The share spent by CONTINUITY_PI is read at the highest rung at or
    # below it — determinable only when that rung is neither the bottom
    # (on {0, 1} it is pi = 0 itself, so the share was 0 and "continuous"
    # passed with one step carrying the whole swing) nor the top, and absent
    # when no rung sits at or below it (was read as 0.0). Undeterminable is
    # ``None`` -> ``continuous`` is ``None`` (T088 dose 1). T091 A8: the
    # rung is the one NEAREST CONTINUITY_PI (ties to the lower), not the
    # highest at or below it, and it must lie within CONTINUITY_RUNG_TOLERANCE:
    # a ladder whose nearest rung is more than 0.1 from 0.2 (e.g. {0, 0.05,
    # 0.5, 1}) read the share spent by 0.05 and could pass criterion 4
    # optimistically; it now cannot answer it (None). A rung in [0.1, 0.2)
    # is still read, and still under-reads the share spent by 0.2.
    k = min(range(len(cells)), key=lambda i: (round(abs(cells[i].pi - CONTINUITY_PI), 12), cells[i].pi))
    readable = 0 < k < len(cells) - 1 and abs(cells[k].pi - CONTINUITY_PI) <= CONTINUITY_RUNG_TOLERANCE + 1e-12
    frac = (b[k] - b[0]) / swing if readable else None
    return DoseProfile(
        swing=swing,
        fraction_by_continuity_pi=frac,
        max_step_fraction=max(steps),
        monotone=all(s > 0.0 for s in steps),
        passive_clears_target=passive_clears,
        continuity_rung=cells[k].pi if readable else None,
    )
