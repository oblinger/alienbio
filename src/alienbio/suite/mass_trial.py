"""Mass-trial runner + reliability map (F024, M34): the Phase-2 end-state.

A thin, SEQUENTIAL orchestrator over already-shipped, already-tested parts —
this module introduces NO new scoring or statistics. It composes dial axes
into an orthogonal condition grid, runs ``trials_per_condition`` seeded
:class:`~alienbio.suite.trial.TrialRecord`\\ s per cell through the real
:func:`~alienbio.suite.runner.run` / :class:`~alienbio.suite.agent.ScriptedAgent`
seam, and reduces the collected records through the shipped analysis
primitives (:mod:`~alienbio.suite.reliability_grid`,
:mod:`~alienbio.suite.stats_summary`, :mod:`~alienbio.suite.effect_size`) into
an immutable :class:`ReliabilityMap`.

- :func:`condition_grid` — the orthogonal product of ``axes`` (each a
  ``(dial_name, levels)`` pair), one sorted ``condition_key`` per cell — the
  exact shape :func:`~alienbio.suite.trial.condition_key` normalises to and
  :func:`~alienbio.suite.reliability_grid.aggregate_cells` bins on, no
  adapter.
- :class:`MassTrialRunner` — SEQUENTIAL (single-process) driver: for every
  cell x trial, derives an independent child :class:`~alienbio.suite.dist.Seed`
  (``base_seed.child(f"{condition_label}/{i}")``), calls the caller-supplied
  ``drafter``/``agent_factory`` to build one world/task/agent under that
  cell's dials, and folds it through :func:`~alienbio.suite.runner.run`.
  Every ``(cell, trial)`` unit is a pure, independent function of its own
  derived seed — a process pool is a safe, purely-additive future upgrade
  (swap the inner ``for`` loop for a pool ``map`` over the same per-trial
  seeds); it is not built here (RAM: thousands of parallel simulator
  processes would exhaust it). ``on_error="record"`` (the default, M46.3)
  ISOLATES each trial: a drafter/agent/runner exception is caught and folded
  into an error ``TrialRecord`` (``terminal_reason="error"``) instead of
  aborting the whole grid — one hallucinated id or a flaky generator no
  longer costs every other cell's already-collected data.
  ``on_error="raise"`` keeps the original propagate-on-first-failure
  behaviour.
- :class:`ReliabilityMap` — the frozen aggregate: per-cell
  :class:`CellSummary` (n/mean/std + confidence interval), per-axis-pair
  interaction contrasts, per-axis-pair effect-size contrasts, a
  ``Provenance`` record (axes + base seed + trials-per-condition +
  ``failed_trials``) — plus every raw :class:`~alienbio.suite.trial.TrialRecord`
  (error records included, in run order) retained on ``.records`` for the
  per-trial scorers, and ``to_json``/``to_csv`` serialization for offline
  analysis. Error records are excluded from the cell/interaction/contrast
  STATISTICS (they are not measurements) but are always kept in ``.records``.
"""

from __future__ import annotations

import csv
import io
import itertools
import json
import statistics
from dataclasses import dataclass, replace
from typing import Any, Callable, Collection, Mapping, Optional, Sequence, cast

from ..bio.world import WorldImpl
from .agent import Agent
from .deliberation import DeliberationTrace
from .dist import Seed
from .effect_size import cohens_d, welch_t
from .reliability_grid import CellStats, aggregate_cells, two_way_interaction
from .runner import run as run_trial
from .stats_summary import mean_confidence_interval
from .trial import TrialRecord, condition_key
from .types import TaskInstance, Timeline

#: One sorted ``(dial_name, level)`` tuple — identical shape to
#: :func:`~alienbio.suite.trial.condition_key`'s output and what
#: :func:`~alienbio.suite.reliability_grid.aggregate_cells` bins on.
ConditionKey = tuple[tuple[str, Any], ...]

#: One sweep axis: a dial name plus the ordered levels it is swept across.
Axis = tuple[str, Sequence[Any]]

#: Caller-supplied world/task builder for one ``(seed, dials)`` trial. Kept
#: as a parameter (not hard-coded to any one dial-generator module) so the
#: runner stays axis-agnostic — it never inspects a dial name or level, it
#: only threads them through.
WorldDrafter = Callable[[Seed, Mapping[str, Any]], "tuple[WorldImpl, TaskInstance]"]

#: Caller-supplied agent builder for one ``(seed, dials)`` trial — same
#: axis-agnostic seam as :data:`WorldDrafter`.
AgentFactory = Callable[[Seed, Mapping[str, Any]], Agent]


def condition_grid(axes: Sequence[Axis]) -> list[ConditionKey]:
    """The orthogonal product of ``axes``, one sorted ``condition_key`` per cell.

    ``axes`` is a list of ``(dial_name, levels)`` pairs; the returned list has
    one entry per combination in ``itertools.product`` order over ``axes`` as
    given, each entry normalised by :func:`~alienbio.suite.trial.condition_key`
    (sorted by dial name) — the exact, adapter-free shape
    :func:`~alienbio.suite.reliability_grid.aggregate_cells` bins
    :class:`~alienbio.suite.trial.TrialRecord` observations on.
    """
    names = [name for name, _ in axes]
    levels = [tuple(lv) for _, lv in axes]
    return [
        condition_key(dict(zip(names, combo))) for combo in itertools.product(*levels)
    ]


def _condition_label(key: ConditionKey) -> str:
    """A deterministic, human-readable label for a condition key's seed derivation."""
    return "&".join(f"{name}={value}" for name, value in key)


@dataclass(frozen=True)
class CellSummary:
    """One condition-cell's :class:`~alienbio.suite.reliability_grid.CellStats`
    plus its mean confidence interval (:func:`~alienbio.suite.stats_summary.mean_confidence_interval`).

    ``ci`` is ``(mean, mean)`` for a singleton cell (``stats.n < 2``), since a
    confidence interval is undefined for a single observation.
    """

    stats: CellStats
    ci: tuple[float, float]


@dataclass(frozen=True)
class ContrastResult:
    """A pairwise effect-size contrast between two condition-cells (or pooled
    cell groups): :func:`~alienbio.suite.effect_size.cohens_d` and
    :func:`~alienbio.suite.effect_size.welch_t`, both computed ``high - low``."""

    cohens_d: float
    welch_t: float


@dataclass(frozen=True)
class Provenance:
    """What produced a :class:`ReliabilityMap`: the swept axes, the base seed,
    and the fixed per-condition trial count (Q1 = C: a fixed floor, not a
    power-driven top-up).

    ``failed_trials`` (M46.3) is how many ``(condition, trial)`` units raised
    under ``on_error="record"`` — always ``0`` under ``on_error="raise"``
    (a failure there propagates instead). Defaults to ``0`` so every
    existing hand-built fixture constructs unchanged.

    ``stopped_early`` (M45.5) is ``True`` iff :meth:`MassTrialRunner.run`'s
    ``stop`` hook fired before the grid finished (e.g. a cost ceiling) —
    the map it produced is built from whatever ``(condition, trial)`` units
    already existed at that point, not the full planned grid. Defaults to
    ``False`` so every existing hand-built fixture constructs unchanged.
    """

    axes: tuple[tuple[str, tuple[Any, ...]], ...]
    base_seed: Seed
    trials_per_condition: int
    failed_trials: int = 0
    stopped_early: bool = False


@dataclass(frozen=True)
class ReliabilityMap:
    """The immutable Phase-2 end-state aggregate (Q4 = B).

    ``cells`` maps each swept ``condition_key`` to its :class:`CellSummary`.
    ``interactions`` maps each swept axis-name pair with exactly 2 levels
    apiece to its :func:`~alienbio.suite.reliability_grid.two_way_interaction`
    contrast, computed over the 2x2 marginal (cell means averaged over any
    OTHER swept axes) — axis pairs where either axis has other than 2 levels
    have no defined 2x2 interaction and are simply absent from this mapping.
    ``contrasts`` maps the SAME axis pairs to a diagonal-extremes
    :class:`ContrastResult` (``(a1, b1)`` pooled raw scores vs ``(a0, b0)``
    pooled raw scores, pooling across any other swept axes) using
    :func:`~alienbio.suite.effect_size.cohens_d` /
    :func:`~alienbio.suite.effect_size.welch_t`.

    ``records`` (M46.3) is every :class:`~alienbio.suite.trial.TrialRecord`
    this run produced, in run order — error records (``on_error="record"``)
    included — the per-trial data the M33 scorers read; previously discarded
    once folded into ``cells``. Defaults to ``()`` so every existing
    hand-built fixture constructs unchanged.
    """

    cells: Mapping[ConditionKey, CellSummary]
    interactions: Mapping[tuple[str, str], float]
    contrasts: Mapping[tuple[str, str], ContrastResult]
    provenance: Provenance
    records: tuple[TrialRecord, ...] = ()

    def to_json(self) -> str:
        """Serialize to a JSON string (cells + interactions + contrasts + provenance)."""
        payload = {
            "provenance": {
                "axes": [[name, list(levels)] for name, levels in self.provenance.axes],
                "base_seed": self.provenance.base_seed.value,
                "trials_per_condition": self.provenance.trials_per_condition,
                "failed_trials": self.provenance.failed_trials,
                "stopped_early": self.provenance.stopped_early,
            },
            "cells": [
                {
                    "condition_key": [[name, value] for name, value in key],
                    "n": summary.stats.n,
                    "mean": summary.stats.mean,
                    "std": summary.stats.std,
                    "ci_low": summary.ci[0],
                    "ci_high": summary.ci[1],
                }
                for key, summary in sorted(self.cells.items(), key=lambda kv: str(kv[0]))
            ],
            "interactions": [
                {"axes": list(pair), "value": value}
                for pair, value in sorted(self.interactions.items())
            ],
            "contrasts": [
                {"axes": list(pair), "cohens_d": c.cohens_d, "welch_t": c.welch_t}
                for pair, c in sorted(self.contrasts.items())
            ],
        }
        return json.dumps(payload, indent=2)

    def to_csv(self) -> str:
        """Serialize the per-cell summary table to a CSV string.

        Columns: one per swept axis name (in ``provenance.axes`` order), then
        ``n``, ``mean``, ``std``, ``ci_low``, ``ci_high``. Rows are sorted for
        stable output.
        """
        axis_names = [name for name, _ in self.provenance.axes]
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow([*axis_names, "n", "mean", "std", "ci_low", "ci_high"])
        for key, summary in sorted(self.cells.items(), key=lambda kv: str(kv[0])):
            by_name = dict(key)
            row: list[Any] = [by_name.get(name) for name in axis_names]
            row += [summary.stats.n, summary.stats.mean, summary.stats.std, *summary.ci]
            writer.writerow(row)
        return buf.getvalue()


def _levels_of(axes: Sequence[Axis], name: str) -> tuple[Any, ...]:
    for axis_name, levels in axes:
        if axis_name == name:
            return tuple(levels)
    raise KeyError(name)


def _marginal_cell_means(
    cells: Mapping[ConditionKey, CellSummary],
    axes: Sequence[Axis],
    axis_a: str,
    axis_b: str,
) -> dict[tuple[Any, Any], float]:
    """The 2x2 marginal table of ``axis_a``/``axis_b`` cell means.

    Marginalizes over any OTHER swept axes by unweighted-averaging the
    matching cells' means (the standard fixed-effect marginal) — with no
    other axes swept this degenerates to reading the single matching cell's
    mean directly.
    """
    other_axes = [(name, levels) for name, levels in axes if name not in (axis_a, axis_b)]
    other_combos = (
        list(itertools.product(*[levels for _, levels in other_axes])) if other_axes else [()]
    )
    result: dict[tuple[Any, Any], float] = {}
    for level_a in _levels_of(axes, axis_a):
        for level_b in _levels_of(axes, axis_b):
            means: list[float] = []
            for combo in other_combos:
                dials: dict[str, Any] = {axis_a: level_a, axis_b: level_b}
                for (name, _), value in zip(other_axes, combo):
                    dials[name] = value
                key = condition_key(dials)
                if key in cells:
                    means.append(cells[key].stats.mean)
            if means:
                result[(level_a, level_b)] = statistics.fmean(means)
    return result


def _pooled_raw_scores(
    raw_by_key: Mapping[ConditionKey, Sequence[float]],
    axis_a: str,
    level_a: Any,
    axis_b: str,
    level_b: Any,
) -> list[float]:
    """Raw ``objective_score`` values pooled across every cell whose
    ``axis_a``/``axis_b`` dials match ``level_a``/``level_b`` (any other
    swept axis' level included)."""
    pooled: list[float] = []
    for key, values in raw_by_key.items():
        by_name = dict(key)
        if by_name.get(axis_a) == level_a and by_name.get(axis_b) == level_b:
            pooled.extend(values)
    return pooled


def aggregate_records(
    records: Sequence[TrialRecord],
    axes: tuple[tuple[str, tuple[Any, ...]], ...],
    base_seed: Seed,
    trials_per_condition: int,
) -> ReliabilityMap:
    """Public alias for :func:`_aggregate` (M46.5): rebuild a :class:`ReliabilityMap`
    from a stored ``list[TrialRecord]`` + its provenance alone — no drafting,
    no re-running, the exact reducer :class:`MassTrialRunner` itself uses. The
    entry point ``suite.experiment.aggregate`` reads a record store through.
    """
    return _aggregate(records, axes, base_seed, trials_per_condition)


def _aggregate(
    records: Sequence[TrialRecord],
    axes: tuple[tuple[str, tuple[Any, ...]], ...],
    base_seed: Seed,
    trials_per_condition: int,
) -> ReliabilityMap:
    """Pure reducer: ``list[TrialRecord]`` -> :class:`ReliabilityMap`.

    Bins on ``TrialRecord.condition_key`` directly (no adapter) through the
    shipped :func:`~alienbio.suite.reliability_grid.aggregate_cells`, adds a
    per-cell confidence interval, and — for every swept axis pair with
    exactly 2 levels apiece — a 2x2 interaction contrast plus a diagonal
    effect-size contrast. Introduces no new statistics: every number here
    comes from ``reliability_grid``/``stats_summary``/``effect_size``.
    """
    raw_by_key: dict[ConditionKey, list[float]] = {}
    for record in records:
        raw_by_key.setdefault(record.condition_key, []).append(record.objective_score)

    observations = [(record.condition_key, record.objective_score) for record in records]
    stats = aggregate_cells(observations)

    cells: dict[ConditionKey, CellSummary] = {}
    for raw_key, cs in stats.items():
        key = cast(ConditionKey, raw_key)
        values = raw_by_key[key]
        ci = mean_confidence_interval(values) if cs.n >= 2 else (cs.mean, cs.mean)
        cells[key] = CellSummary(stats=cs, ci=ci)

    interactions: dict[tuple[str, str], float] = {}
    contrasts: dict[tuple[str, str], ContrastResult] = {}
    axis_names = [name for name, _ in axes]
    for axis_a, axis_b in itertools.combinations(axis_names, 2):
        if len(_levels_of(axes, axis_a)) != 2 or len(_levels_of(axes, axis_b)) != 2:
            continue  # two_way_interaction requires exactly 2 levels per factor
        marginal = _marginal_cell_means(cells, axes, axis_a, axis_b)
        if len(marginal) < 4:
            continue  # some combination has no observations yet
        interactions[(axis_a, axis_b)] = two_way_interaction(marginal)

        a0, a1 = sorted(_levels_of(axes, axis_a))
        b0, b1 = sorted(_levels_of(axes, axis_b))
        low = _pooled_raw_scores(raw_by_key, axis_a, a0, axis_b, b0)
        high = _pooled_raw_scores(raw_by_key, axis_a, a1, axis_b, b1)
        if len(low) >= 2 and len(high) >= 2:
            contrasts[(axis_a, axis_b)] = ContrastResult(
                cohens_d=cohens_d(high, low), welch_t=welch_t(high, low)
            )

    provenance = Provenance(axes=axes, base_seed=base_seed, trials_per_condition=trials_per_condition)
    return ReliabilityMap(cells=cells, interactions=interactions, contrasts=contrasts, provenance=provenance)


class MassTrialRunner:
    """SEQUENTIAL (Q3 override) driver: condition grid x trials -> :class:`ReliabilityMap`.

    Single-process by design (RAM: a process pool of simulator processes
    would exhaust it) but parallel-READY: every ``(condition, trial)`` unit
    derives its own independent child seed
    (``base_seed.child(f"{condition_label}/{i}")``) up front, so the inner
    loop body is a pure function of that seed alone and could be handed to a
    process/thread pool's ``map`` unchanged — that swap is a safe, purely
    additive future layer, not built here.
    """

    def run(
        self,
        axes: Sequence[Axis],
        drafter: WorldDrafter,
        agent_factory: AgentFactory,
        trials_per_condition: int,
        base_seed: Seed,
        on_error: str = "record",
        extra_dials: Mapping[str, Any] = {},
        on_trial: Optional[Callable[[str, int, TrialRecord], None]] = None,
        skip: Optional[Callable[[str, int], Optional[TrialRecord]]] = None,
        matched_dials: Collection[str] = (),
        stop: Optional[Callable[[], bool]] = None,
    ) -> ReliabilityMap:
        """Run ``trials_per_condition`` seeded trials for every cell of ``axes``.

        ``matched_dials`` (M46.8) names swept dials that must NOT enter the
        per-trial seed label — e.g. ``("agent", "model")`` — so cells that
        differ only in those dials draw the identical world and agent seeds:
        a scripted control arm and a live-model arm then run on byte-identical
        worlds. The ``condition_key``, ``label`` handed to ``on_trial``/``skip``
        and the statistics are unaffected; only seed derivation is.

        For every condition (in sorted-``condition_key`` order, for a stable
        map regardless of ``axes``' own argument order) and every trial index
        ``i``: derive ``trial_seed = base_seed.child(f"{label}/{i}")``, build
        one world/task via ``drafter(trial_seed.child("draft"), dials)`` and
        one agent via ``agent_factory(trial_seed.child("agent"), dials)``,
        then fold it through :func:`~alienbio.suite.runner.run` with
        ``trial_seed.child("run")``. ``dials`` is the condition's
        ``{dial_name: level}`` mapping (``dict(condition_key)``) — this
        runner never inspects a dial name or level itself, keeping it
        axis-agnostic and decoupled from any one dial-generator module.

        ``extra_dials`` (M46.5) is merged UNDER the condition's own swept
        dials (``{**extra_dials, **dials}``) before being handed to
        ``drafter``, ``agent_factory``, and :func:`~alienbio.suite.runner.run`
        — so a caller (:func:`~alienbio.suite.experiment.run_experiment`'s
        ``fixed_dials``) can apply a dial to EVERY condition (e.g.
        ``max_turns``) without it becoming part of the swept axes. The
        returned record's ``condition_key`` is reset to the swept ``key``
        alone afterwards (``dataclasses.replace``) — ``extra_dials`` widens
        what a trial SEES, never what a cell is BINNED on.

        ``on_trial`` (M46.5), when given, is called right after each record
        is produced — fresh (drafted and run) or reused via ``skip`` — as
        ``on_trial(label, i, record)``. This is the persistence hook: a
        caller writes the record to a store as it lands, rather than only
        after the whole grid finishes. Exceptions from ``on_trial`` propagate
        (a persistence failure must be loud, not swallowed).

        ``skip`` (M46.5), when given, is consulted as ``skip(label, i)``
        BEFORE drafting: if it returns a :class:`~alienbio.suite.trial.TrialRecord`,
        that record is used as-is — nothing is drafted, no agent is built,
        :func:`~alienbio.suite.runner.run` is never called — and it is
        counted in ``records``/``on_trial`` exactly like a fresh one (folded
        into the returned statistics unless its ``terminal_reason ==
        "error"``, and into ``Provenance.failed_trials`` if it is). This is
        the resume seam: a caller backs ``skip`` by an on-disk record store
        keyed by ``(label, i)`` so a crashed run only redoes the trials it
        never finished.

        ``on_error`` (M46.3) controls per-trial fault isolation:

        - ``"record"`` (default): a ``drafter``/``agent_factory``/``run``
          exception for one ``(condition, trial)`` unit is caught and folded
          into an error :class:`~alienbio.suite.trial.TrialRecord`
          (``terminal_reason="error"``, ``error=f"{type(exc).__name__}:
          {exc}"``, ``task_id`` = the drafted task's ``world`` if the
          drafter got that far, else the condition label) instead of
          aborting the whole grid; every other ``(condition, trial)`` unit
          still runs. Error records are excluded from the returned
          ``cells``/``interactions``/``contrasts`` statistics but are always
          present in ``ReliabilityMap.records`` and counted in
          ``Provenance.failed_trials``.
        - ``"raise"``: today's original behaviour — the first exception
          propagates and aborts the run.

        ``stop`` (M45.5), when given, is consulted (``stop()``) right BEFORE
        every FRESH trial — after the ``skip`` check has already found
        nothing to reuse, so a resumed unit is never blocked from replaying.
        Once it returns ``True`` the whole grid stops cleanly: no further
        ``(condition, trial)`` unit is drafted or run, and the returned
        :class:`ReliabilityMap` is built from exactly the records that
        already exist (``Provenance.stopped_early`` is set ``True``). This is
        the cost-ceiling seam: a caller closes over a running spend total and
        returns ``True`` once it reaches a cap.

        Raises:
            ValueError: ``on_error`` is neither ``"record"`` nor ``"raise"``.

        Reproducible: identical ``(axes, drafter, agent_factory,
        trials_per_condition, base_seed)`` always yields byte-identical cell
        means/CIs (every seed is a pure function of the condition's own key
        and trial index, never of the grid's overall size or enumeration
        order) — widening an axis with new levels only adds new cells, it
        never perturbs an existing cell's per-trial seeds.
        """
        if on_error not in ("record", "raise"):
            raise ValueError(f"MassTrialRunner.run: unknown on_error {on_error!r}; expected 'record' or 'raise'")

        axes_tuple = tuple((name, tuple(levels)) for name, levels in axes)
        keys = sorted(condition_grid(axes_tuple), key=lambda k: str(k))

        records: list[TrialRecord] = []
        failed_trials = 0
        stopped_early = False
        for key in keys:
            if stopped_early:
                break
            dials = dict(key)
            label = _condition_label(key)
            for i in range(trials_per_condition):
                if skip is not None:
                    existing = skip(label, i)
                    if existing is not None:
                        if existing.terminal_reason == "error":
                            failed_trials += 1
                        records.append(existing)
                        if on_trial is not None:
                            on_trial(label, i, existing)
                        continue

                if stop is not None and stop():
                    stopped_early = True
                    break

                seed_label = (
                    _condition_label(tuple((n, v) for n, v in key if n not in matched_dials))
                    if matched_dials
                    else label
                )
                trial_seed = base_seed.child(f"{seed_label}/{i}")
                run_dials = {**extra_dials, **dials}
                task: Optional[TaskInstance] = None
                try:
                    world, task = drafter(trial_seed.child("draft"), run_dials)
                    agent = agent_factory(trial_seed.child("agent"), run_dials)
                    record = run_trial(world, task, agent, run_dials, trial_seed.child("run"))
                    record = replace(record, condition_key=key)
                except Exception as exc:
                    if on_error == "raise":
                        raise
                    failed_trials += 1
                    record = TrialRecord(
                        task_id=task.world if task is not None else label,
                        condition_key=key,
                        final_timeline=Timeline(times=(), states=()),
                        deliberation_trace=DeliberationTrace(),
                        action_log=(),
                        objective_score=0.0,
                        terminal_reason="error",
                        error=f"{type(exc).__name__}: {exc}",
                    )
                records.append(record)
                if on_trial is not None:
                    on_trial(label, i, record)

        successful = tuple(r for r in records if r.terminal_reason != "error")
        rmap = _aggregate(successful, axes_tuple, base_seed, trials_per_condition)
        provenance = replace(rmap.provenance, failed_trials=failed_trials, stopped_early=stopped_early)
        return replace(rmap, records=tuple(records), provenance=provenance)
