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
    passive_clears_target: bool  # a do-nothing agent scored 1.0 somewhere (criterion 3 fails)

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
    without either are skipped."""
    buckets: dict[tuple[tuple[str, Any], ...], dict[float, list[tuple[float, float, float]]]] = {}
    oracles: dict[tuple[tuple[tuple[str, Any], ...], float], Mapping[str, Any]] = {}
    for record in records:
        oracle = (record.oracle or {}).get("pressure")
        if not oracle or not record.final_state or record.terminal_reason == "error":
            continue
        cond = dict(record.condition_key)
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
    vacuously true."""
    if not cells:
        raise ValueError("dose_profile: no cells")
    b = [c.mean_byproduct for c in cells]
    swing = b[-1] - b[0]
    passive_clears = any(c.mean_score >= 1.0 for c in cells)
    if len(cells) < 2 or swing <= 0.0:
        return DoseProfile(swing, None, None, all(y > x for x, y in zip(b, b[1:])), passive_clears)
    steps = [(y - x) / swing for x, y in zip(b, b[1:])]
    at_or_below = [c for c in cells if c.pi <= CONTINUITY_PI + 1e-12]
    frac = ((at_or_below[-1].mean_byproduct - b[0]) / swing) if at_or_below else 0.0
    return DoseProfile(
        swing=swing,
        fraction_by_continuity_pi=frac,
        max_step_fraction=max(steps),
        monotone=all(s > 0.0 for s in steps),
        passive_clears_target=passive_clears,
    )
