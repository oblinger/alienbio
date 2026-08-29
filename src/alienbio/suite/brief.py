"""``TaskBrief`` — the task-grounded context a live agent needs (M46.1).

Today a live model driving ``suite.runner.run`` gets only ``{"turn": n,
"compartments": [...]}`` and a generic directive: it is never told the
question it must answer, what answer kind is expected, what it may measure
or intervene on, its budget, or the constitution. This module closes that
gap with a small, pure, taint-safe briefing object built once per trial
(before turn 0) from exactly the same dial-narrowed inputs the runner
already threads through the turn loop — nothing hidden by the observability
dial, and nothing off the answer key/outcome target/oracle, ever reaches it.

- :class:`Affordances` — the probe ids a ``Measure`` may name and the lever
  ids an ``Intervene`` may name, both derived from what is actually visible/
  allowlisted for THIS trial.
- :class:`TaskBrief` — the frozen briefing: question, question/objective/
  answer kinds, constitution (if dialed), affordances, budget, per-verb
  costs, ``max_turns``, and ``sim_steps``.
- :func:`build_brief` — the pure constructor, called once by
  :func:`~alienbio.suite.runner.run` before turn 0.
- :func:`render_brief` — a plain-text rendering for a live agent's system
  prompt (:mod:`~alienbio.suite.llm_agent`).
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Mapping, Optional

from .types import AnswerObjective, TaskInstance

if TYPE_CHECKING:
    from ..bio.chemistry import ChemistryImpl
    from .observation import Observation
    from .runner import Budget
    from .verify import SimConfig

#: Default per-verb action cost, keyed by lower-cased ``Action`` type name
#: (Q3 = B, moved here from ``suite.runner`` so both ``brief.py`` and
#: ``runner.py`` can read one shared table without a circular import —
#: ``runner._action_cost`` reads this directly). ``Measure`` cheap,
#: ``Intervene`` dearer, ``Commit``/``Wait`` free by default;
#: ``action.params["cost"]`` overrides this per call.
DEFAULT_ACTION_COSTS: Mapping[str, float] = {
    "measure": 1.0,
    "intervene": 5.0,
    "commit": 0.0,
    "wait": 0.0,
}


@dataclass(frozen=True)
class Affordances:
    """What a ``Measure``/``Intervene`` may legally name in this trial.

    ``probes`` is the sorted union of ids actually present in the turn-0
    (dial-narrowed) observation — a hidden molecule (per the
    ``"observability"`` dial) never appears here, which is the taint
    property this class exists to hold. ``levers`` is either an explicit
    per-trial allowlist (``dials["levers"]``) or, by default, every reaction
    id plus the same visible probes.
    """

    probes: tuple[str, ...]
    levers: tuple[str, ...]


@dataclass(frozen=True)
class TaskBrief:
    """The task-grounded context handed to an agent before turn 0.

    ``question``/``question_kind`` are ``task.question`` verbatim (the
    agent-facing question is never taint — it is what the agent is being
    asked to answer). ``answer_kind`` is the KIND only (``AnswerObjective.key.kind``,
    e.g. ``"ordered_path"``) — never the key's ``value``, which stays
    strictly off this object. ``constitution`` is ``dials["constitution"]``
    when it is a plain string (M30.1's injected directive), else ``None``.
    """

    question: Any
    question_kind: str
    objective_kind: str
    answer_kind: Optional[str]
    constitution: Optional[str]
    affordances: Affordances
    budget_total: float
    budget_unit: str
    action_costs: Mapping[str, float]
    max_turns: int
    sim_steps: int
    sim_dt: float = 0.1


def build_brief(
    task: TaskInstance,
    chemistry: "ChemistryImpl",
    first_observation: "Observation",
    dials: Mapping[str, Any],
    budget: "Budget",
    max_turns: int,
    sim_cfg: "SimConfig",
) -> TaskBrief:
    """Build the one ``TaskBrief`` for a trial (pure function of its inputs).

    ``probes`` is the sorted union of every id in every compartment dict of
    ``first_observation`` — this MUST be the dial-narrowed turn-0
    observation (never a raw/full ground-truth read), so a hidden molecule
    is simply absent, not merely unlisted.

    ``levers`` is ``tuple(dials["levers"])`` when ``"levers"`` is present in
    ``dials`` — an explicit per-trial allowlist (every entry validated to be
    a ``str``, else ``ValueError``) for a drafter whose task would otherwise
    be leaked by the reaction-id vocabulary itself. Otherwise it defaults to
    every reaction id in ``chemistry`` (the world's declared control
    surface) plus the same visible ``probes`` (a molecule lever is only
    offered if it is already visible).
    """
    probes = tuple(sorted({obs_id for compartment in first_observation for obs_id in compartment}))

    levers_dial = dials.get("levers")
    if levers_dial is not None:
        levers_list = list(levers_dial)
        for entry in levers_list:
            if not isinstance(entry, str):
                raise ValueError(
                    f"build_brief: dials['levers'] entries must all be str; got {entry!r}"
                )
        levers = tuple(levers_list)
    else:
        levers = tuple(sorted(chemistry.reactions)) + probes

    objective = task.objective
    if isinstance(objective, AnswerObjective):
        objective_kind = "answer"
        answer_kind: Optional[str] = objective.key.kind
    else:
        objective_kind = "outcome"
        answer_kind = None

    constitution_dial = dials.get("constitution")
    constitution = constitution_dial if isinstance(constitution_dial, str) else None

    return TaskBrief(
        question=task.question.structured,
        question_kind=task.question.kind,
        objective_kind=objective_kind,
        answer_kind=answer_kind,
        constitution=constitution,
        affordances=Affordances(probes=probes, levers=levers),
        budget_total=budget.total,
        budget_unit=budget.unit,
        action_costs=dict(DEFAULT_ACTION_COSTS),
        max_turns=max_turns,
        sim_steps=sim_cfg.steps,
        sim_dt=sim_cfg.dt,
    )


def render_brief(brief: TaskBrief) -> str:
    """Render ``brief`` to plain, labelled text for a live agent's system prompt.

    No world internals ever appear: only the question, kinds, constitution,
    affordance ids, budget/costs, ``max_turns``, and ``sim_steps`` — exactly
    ``brief``'s own fields, nothing recomputed from the world.
    """
    lines = [f"Question: {json.dumps(brief.question, sort_keys=True, default=repr)}"]

    if brief.objective_kind == "answer":
        lines.append(f"Expected answer kind: {brief.answer_kind}")
    else:
        lines.append("This task is scored on the world's outcome, not on a submitted answer.")

    if brief.constitution:
        lines.append(f"Constitution: {brief.constitution}")

    lines.append(f"Probes (Measure may name): {', '.join(brief.affordances.probes)}")
    lines.append(f"Levers (Intervene may name): {', '.join(brief.affordances.levers)}")

    budget_str = "unlimited" if math.isinf(brief.budget_total) else f"{brief.budget_total} {brief.budget_unit}"
    cost_str = ", ".join(f"{verb}={cost}" for verb, cost in sorted(brief.action_costs.items()))
    lines.append(f"Budget: {budget_str} (per-action costs: {cost_str})")
    lines.append(f"Max turns: {brief.max_turns}")
    lines.append(f"Simulation steps per turn: {brief.sim_steps}")

    return "\n".join(lines)
