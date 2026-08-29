"""``TrialRecord`` — the frozen unit of observation one agent-run emits (F020, D2).

Distilled, not the raw simulation log: one immutable record per agent-run,
carrying the core the M34 mass-trial stats and the PR#155 scorers read.
``objective_score`` is frozen in (it is on the hot path of every
``reliability_grid`` / ``effect_size`` aggregation); the heavier diagnostic
scorers stay lazily recomputed over the frozen core, so a scorer revision
never invalidates an already-collected batch.

- :func:`condition_key` — normalises a dial-vector mapping into the sorted
  ``tuple[tuple[str, Any], ...]`` shape ``reliability_grid.aggregate_cells``
  bins on directly, with no adapter.
- :class:`TrialRecord` — the frozen record itself, plus lazy diagnostic-scorer
  accessors over its ``action_log`` / ``deliberation_trace``.
- :func:`thread_reasoning_steps` — the small adapter that turns an agent
  turn's ``reasoning_steps`` into ``DeliberationStep`` entries appended to a
  trace, 1:1, tagged with the turn index and the action's type.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property
from typing import Any, Collection, Mapping, Optional, Sequence

from .agent import Action, ReasoningStep
from .brief import TaskBrief
from .deliberation import DeliberationStep, DeliberationTrace
from .info_seeking import ActionRecord
from .info_seeking import actions_before_commit as _actions_before_commit
from .info_seeking import destructive_rate as _destructive_rate
from .info_seeking import info_seeking_ratio as _info_seeking_ratio
from .types import Timeline


def condition_key(dials: Mapping[str, Any]) -> tuple[tuple[str, Any], ...]:
    """Normalise a dial-vector mapping to a sorted ``(dial, level)`` tuple.

    Sorted by dial name so two dicts with the same entries in any order
    normalise to the identical, hashable key —
    ``reliability_grid.aggregate_cells`` bins :class:`TrialRecord` observations
    on this key directly, with no adapter.
    """
    return tuple(sorted(dials.items(), key=lambda kv: kv[0]))


def thread_reasoning_steps(
    trace: DeliberationTrace,
    turn: int,
    action: Action,
    reasoning_steps: Sequence[ReasoningStep],
) -> DeliberationTrace:
    """Append ``reasoning_steps`` into ``trace`` as ``DeliberationStep``s, 1:1.

    Each new step carries ``turn`` and the fired ``action``'s type name
    (lower-cased, e.g. ``"measure"``/``"intervene"``/``"commit"``/``"wait"``)
    appended to its ``refs`` — the turn/action tagging the deliberation-trace
    scorer reads. ``trace`` is unchanged; a new trace is returned (per
    ``DeliberationTrace``'s own immutable-``extend`` contract).
    """
    action_tag = type(action).__name__.lower()
    new_steps = tuple(
        DeliberationStep(
            turn=turn,
            kind=step.kind,
            content=step.content,
            refs=step.refs + (action_tag,),
        )
        for step in reasoning_steps
    )
    return trace.extend(new_steps)


@dataclass(frozen=True)
class TrialRecord:
    """The immutable unit of observation one agent-run emits (Q3 = C).

    Core fields are the recompute source of truth for every lazy diagnostic
    accessor below: ``final_timeline`` + ``deliberation_trace`` + ``action_log``.
    ``objective_score`` is the one exception frozen in eagerly, since it comes
    free from the grader at run time and every ``reliability_grid`` /
    ``effect_size`` aggregation needs it.

    ``terminal_reason`` (F021, Q3 = B) is why the run stopped: ``"committed"``
    / ``"budget_exhausted"`` / ``"max_turns"`` for a record built by
    ``suite.runner.run``. It defaults to ``""`` (not recorded) so every
    existing hand-built fixture (this module's own tests included)
    constructs unchanged.

    ``budget``/``spent``/``remaining`` (F023, M32.1) are the resolved
    ``suite.runner.Budget.total``, the cumulative per-action cost spent, and
    ``budget - spent`` at the moment the trial stopped. They default to an
    unlimited, unspent budget (``float("inf")``/``0.0``/``float("inf")``) so
    every existing hand-built fixture constructs unchanged.

    ``illegal_actions``/``turns``/``brief``/``error`` (M46.1/M46.3) are the
    count of rejected (illegal-but-not-raised) actions, the number of loop
    iterations the trial actually ran, the trial's
    :class:`~alienbio.suite.brief.TaskBrief` (``None`` for a hand-built
    fixture that never went through ``suite.runner.run``), and — for a
    :class:`~alienbio.suite.mass_trial.MassTrialRunner` error record —
    ``f"{type(exc).__name__}: {exc}"``. All four default so every existing
    hand-built fixture constructs unchanged.

    ``usage``/``wall_time_s`` (M45.5) are the agent's real provider-usage
    snapshot (``getattr(agent, "usage", None)`` — ``None`` for a
    ``ScriptedAgent``, which has none) and the wall-clock seconds
    ``suite.runner.run`` spent end to end. Both default so every existing
    hand-built fixture constructs unchanged.
    """

    task_id: str
    condition_key: tuple[tuple[str, Any], ...]
    final_timeline: Timeline
    deliberation_trace: DeliberationTrace
    action_log: tuple[ActionRecord, ...]
    objective_score: float
    terminal_reason: str = ""
    budget: float = float("inf")
    spent: float = 0.0
    remaining: float = float("inf")
    illegal_actions: int = 0
    turns: int = 0
    brief: Optional[TaskBrief] = None
    error: str = ""
    taint_hits: tuple[str, ...] = ()
    usage: Optional[Mapping[str, Any]] = None
    wall_time_s: float = 0.0
    oracle: Mapping[str, Any] = field(default_factory=dict)
    #: M36.4 — ``{compartment_id: {molecule_id: value}}`` at the end of the
    #: trial, read off the final self-describing state. Survives the JSON
    #: store (``final_timeline`` does not), so outcome scorers can run on a
    #: reloaded record (``bio suite report``) exactly as on a live one.
    final_state: Mapping[str, Mapping[str, float]] = field(default_factory=dict)
    #: M36.7 — the committed :class:`~alienbio.suite.types.Answer` as
    #: ``{"value", "kind"}`` (``None`` when the trial never committed), so a
    #: reloaded record can still tell an abstention (empty value) from a
    #: wrong answer (M33.8's "I don't know" vs false-positive split).
    answer: Optional[Mapping[str, Any]] = None

    @cached_property
    def deliberation_depth(self) -> int:
        """Lazily-cached step count of ``deliberation_trace`` (PR#155 diagnostic)."""
        return self.deliberation_trace.depth()

    def info_seeking_ratio(self, investigative_kinds: Collection[str]) -> float:
        """Lazily recomputed :func:`~alienbio.suite.info_seeking.info_seeking_ratio`
        over ``action_log`` (caller supplies which ``ActionRecord.kind`` values
        count as investigative for this scenario)."""
        return _info_seeking_ratio(self.action_log, investigative_kinds)

    def destructive_rate(self) -> float:
        """Lazily recomputed :func:`~alienbio.suite.info_seeking.destructive_rate`
        over ``action_log``."""
        return _destructive_rate(self.action_log)

    def actions_before_commit(self, commit_kinds: Collection[str]) -> int:
        """Lazily recomputed :func:`~alienbio.suite.info_seeking.actions_before_commit`
        over ``action_log``."""
        return _actions_before_commit(self.action_log, commit_kinds)


def final_state_dict(state: Any) -> dict[str, dict[str, float]]:
    """``{compartment_id: {molecule_id: value}}`` read off a self-describing
    ``WorldStateImpl`` — ``{}`` for a pure-int state (no id axes to read)."""
    comp_ids = getattr(state, "compartment_ids", None)
    mol_ids = getattr(state, "molecule_ids", None)
    if comp_ids is None or mol_ids is None:
        return {}
    return {
        comp_ids[ci]: {mol_ids[mj]: float(state.get(ci, mj)) for mj in range(len(mol_ids))}
        for ci in range(len(comp_ids))
    }
