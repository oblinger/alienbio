"""ScenarioRunner — the agent turn loop that makes F020's primitives LIVE (F021).

``run`` is the seam that closes the Phase-2 spine end to end:

    Observation -> agent.act(obs) -> (action, reasoning_steps)
    -> apply to world -> verify.simulate one burst -> repeat

...until a budget cap, a ``Commit``, or ``max_turns`` stops it, producing ONE
immutable :class:`~alienbio.suite.trial.TrialRecord`.

**Fresh-world-per-turn (the KEY integration problem).** :class:`~alienbio.bio.world.WorldImpl`
*derives* its ``initial_state`` from a ``Compartment`` spec tuple at
construction — there is no constructor that takes a prebuilt state. To advance
turn by turn with "a fresh immutable ``WorldImpl`` per turn, seeded from the
prior end-state" (D3), :func:`_world_from_state` folds the prior turn's end
:class:`~alienbio.bio.world_state.WorldStateImpl` back onto a rebuilt
``Compartment`` tuple (same ``id``/``parent``/``kind`` topology, refreshed
``concentrations``/``multiplicity``/``volume``) and reconstructs ``WorldImpl``
through its ordinary, UNCHANGED constructor. Neither the state snapshot nor
the original ``world``/``chemistry`` passed to :func:`run` is ever mutated —
every turn threads forward two immutable pieces of context
(``chemistry``, ``state``), rebinding them only through fresh objects, which is
what keeps two ``run`` calls against the same ``world`` byte-for-byte
independent (the acceptance determinism test) even when the agent chose to
``Intervene``.

**Action verbs -> world effects (Q1 = A).** ``Measure`` is non-mutating (its
only effect is a cost + an ``ActionRecord``/``DeliberationStep`` log entry —
the per-turn ``Observation`` is already narrowed by the observability/noise
dials regardless of what was measured, so a no-op or measure-only agent
advances the world identically to a bare :func:`~alienbio.suite.verify.simulate`
run over the same total steps). ``Wait`` is likewise non-mutating (its
``duration`` is accepted but not read: every turn already plays out one fixed
``SimConfig(steps=k)`` burst — see Q2 = B — so ``Wait`` and ``Measure`` have
identical world effects, differing only in their logged verb). ``Intervene``
edits ONE control-surface lever: a reaction id sets that reaction's rate
(:func:`_chemistry_with_rate`); a molecule id sets that molecule's
concentration in every compartment (:func:`_state_with_concentration`); any
other lever name fails visibly (``ValueError``), as does a ``Measure`` naming
an unknown probe. ``Commit`` ends the trial (terminal reason ``"committed"``)
and supplies the answer graded against the task's objective.

**Cost/budget -> graded time-pressure dial (F023, M32.1).** Each action
carries an opaque cost — ``Measure`` cheap, ``Intervene`` dearer,
``Commit``/``Wait`` free by default (:data:`_DEFAULT_COST`; a
``params["cost"]`` entry overrides it per call). Spend accumulates every
turn; once it reaches the dialed :class:`Budget`'s ``total`` the trial stops
with reason ``"budget_exhausted"``. A trial that never commits and never
exhausts its budget stops at ``max_turns``. The F021 cap (a bare
``dials["budget"]`` number) is now formalised as :class:`Budget` — one
value object with a selectable ``unit`` (only ``"turns"`` is implemented; see
:class:`Budget`'s docstring) — without ripping out the original
cost-accounting loop; :func:`Budget.from_dial` keeps the old bare-number
dial shape working unchanged.
"""

from __future__ import annotations

import dataclasses
import math
from typing import Any, Mapping, cast

from ..bio.chemistry import ChemistryImpl
from ..bio.reaction import ReactionImpl
from ..bio.world import Compartment, Transport, WorldImpl
from ..bio.world_state import WorldStateImpl
from .agent import Action, Agent, Commit, Intervene, Measure, Wait
from .deliberation import DeliberationTrace
from .dist import Seed
from .grade import grade_answer, grade_outcome
from .info_seeking import ActionRecord
from .observation import narrow_observation
from .trial import TrialRecord, condition_key, thread_reasoning_steps
from .types import AnswerObjective, OutcomeObjective, TaskInstance, Timeline
from .verify import SimConfig, simulate

#: Default per-verb cost (Q3 = B): measurements cheap, interventions dearer,
#: Commit/Wait free. ``action.params["cost"]`` overrides this per call.
_DEFAULT_COST: dict[type, float] = {
    Measure: 1.0,
    Intervene: 5.0,
    Commit: 0.0,
    Wait: 0.0,
}

#: Units :class:`Budget` currently knows how to drain (Q1 = C: ship turns
#: first). ``"sim_steps"``/``"deadline"`` are documented, additive future
#: units (meter simulated time / a hard wall-analog instead of action cost);
#: ``"opportunity_cost"`` (a budget the objective itself also draws on) is a
#: later, structurally different variant explicitly gated behind its own
#: build — selecting any of the three today raises rather than silently
#: behaving like ``"turns"``.
_IMPLEMENTED_UNITS = frozenset({"turns"})
_FUTURE_UNITS = frozenset({"sim_steps", "deadline", "opportunity_cost"})

#: The graded ladder for the ``"turns"`` unit (Q1 = C): a named level ->
#: total-spend cap, from unlimited down to minimal. The EXP-10 degradation
#: driver / EXP-5 objective-surfacing-depth axis sweep these as a
#: ``suite.mass_trial``/``suite.conditions`` axis.
BUDGET_LADDER: Mapping[str, float] = {
    "unlimited": float("inf"),
    "20": 20.0,
    "12": 12.0,
    "8": 8.0,
    "4": 4.0,
}


@dataclasses.dataclass(frozen=True)
class Budget:
    """A graded spend cap on the agent turn loop, in a selectable ``unit``.

    ``total`` is the cumulative-cost ceiling :func:`run` compares its
    per-action :func:`_action_cost` spend against — the SAME cost-weighted
    accounting F021 shipped (``Measure``/``Intervene``/``Commit``/``Wait``
    each carry an opaque cost), now named and packaged as the ``"turns"``
    unit rather than ripped out (Q1 = C). ``total = float("inf")`` (the
    default) is unlimited: the trial never stops on budget, only on
    ``Commit`` or ``max_turns``.

    Additional units are a documented future surface (see
    :data:`_FUTURE_UNITS`): ``__post_init__`` raises ``NotImplementedError``
    for a recognised-but-unbuilt unit and ``ValueError`` for an unknown one,
    so a caller never silently gets ``"turns"`` semantics under a different
    unit's name.
    """

    total: float = float("inf")
    unit: str = "turns"

    def __post_init__(self) -> None:
        if self.unit in _FUTURE_UNITS:
            raise NotImplementedError(
                f"Budget unit {self.unit!r} is not yet implemented (Q1 = C: "
                "turns ships first; sim_steps/deadline/opportunity_cost are "
                "documented future units)"
            )
        if self.unit not in _IMPLEMENTED_UNITS:
            raise ValueError(
                f"unknown Budget unit {self.unit!r}; expected one of "
                f"{sorted(_IMPLEMENTED_UNITS | _FUTURE_UNITS)}"
            )

    @property
    def unlimited(self) -> bool:
        """``True`` iff this budget never terminates the loop on its own."""
        return math.isinf(self.total)

    def exhausted(self, spent: float) -> bool:
        """Whether cumulative ``spent`` has reached this budget's ``total``."""
        return spent >= self.total

    @staticmethod
    def from_dial(value: Any) -> "Budget":
        """Resolve a ``dials["budget"]`` entry to a :class:`Budget`.

        Accepts, in order: a :class:`Budget` instance (passed through
        unchanged); ``None`` (the default: unlimited); a
        :data:`BUDGET_LADDER` level name (``"unlimited"``/``"20"``/``"12"``/
        ``"8"``/``"4"``); or a raw ``float``/``int`` total — the bare-number
        shape the original F021 dial used, kept working unchanged so no
        existing ``dials={"budget": 3.0}`` caller needs to change.

        Raises:
            ValueError: ``value`` is a string that is not a
                :data:`BUDGET_LADDER` level.
        """
        if isinstance(value, Budget):
            return value
        if value is None:
            return Budget()
        if isinstance(value, str):
            if value not in BUDGET_LADDER:
                raise ValueError(
                    f"unknown budget ladder level {value!r}; "
                    f"expected one of {sorted(BUDGET_LADDER)}"
                )
            return Budget(total=BUDGET_LADDER[value])
        return Budget(total=float(value))


def _mock_dat(path: str) -> Any:
    """A duck-typed DAT anchor for constructing derived entities.

    Mirrors ``bio.chemistry``'s private helper of the same name: ``MockDat``
    is not statically a ``Dat``, so the ``Any`` return matches the runtime
    interface ``Entity`` needs while staying type-clean.
    """
    from ..infra.entity import MockDat

    return MockDat(path)


def _action_cost(action: Action) -> float:
    """The opaque spend one fired ``action`` costs (default per verb, or override)."""
    override = action.params.get("cost")
    if override is not None:
        return float(override)
    return _DEFAULT_COST[type(action)]


def _world_from_state(
    compartments: tuple[Compartment, ...],
    chemistry: ChemistryImpl,
    state: WorldStateImpl,
    flows: tuple[Transport, ...] = (),
) -> WorldImpl:
    """Rebuild a fresh, immutable ``WorldImpl`` seeded from ``state``.

    ``compartments`` supplies the unchanging topology spec (``id``/``parent``/
    ``kind``, matched to ``state``'s axis by ``id``, not tuple position — the
    tree ``WorldImpl.__init__`` builds need not enumerate compartments in the
    same order every time); ``state`` supplies the refreshed
    ``concentrations``/``multiplicity``/``volume`` per node. ``state`` is only
    ever READ (:meth:`WorldStateImpl.get` / ``get_multiplicity`` /
    ``get_volume``) — never mutated, and the returned ``WorldImpl`` owns an
    entirely new ``WorldStateImpl`` (built by its own, unmodified constructor).

    ``flows`` (F016/S3) is the original world's ``Transport`` specs, threaded
    forward UNCHANGED so cross-compartment flux survives this per-turn
    rebuild — ``WorldImpl.__init__`` re-resolves them against the freshly
    built tree, which (same topology, same node order) always assigns the
    same int ids, so this is a lossless round-trip. Defaults to empty, so a
    non-transport world's rebuild is unaffected.

    Raises:
        ValueError: if ``state`` is not self-describing (no ``compartment_ids``
            / ``molecule_ids`` to fold back onto the ``Compartment`` specs).
    """
    comp_ids = state.compartment_ids
    mol_ids = state.molecule_ids
    if comp_ids is None or mol_ids is None:
        raise ValueError(
            "_world_from_state requires a self-describing WorldStateImpl "
            "(compartment_ids and molecule_ids)"
        )
    by_id = {c.id: c for c in compartments}
    rebuilt: list[Compartment] = []
    for ci, node_id in enumerate(comp_ids):
        spec = by_id[node_id]
        concentrations = {mol_ids[mj]: state.get(ci, mj) for mj in range(len(mol_ids))}
        rebuilt.append(
            dataclasses.replace(
                spec,
                concentrations=concentrations,
                multiplicity=state.get_multiplicity(ci),
                volume=state.get_volume(ci),
            )
        )
    return WorldImpl(chemistry, tuple(rebuilt), flows=flows)


def _chemistry_with_rate(
    chemistry: ChemistryImpl, reaction_id: str, rate: float
) -> ChemistryImpl:
    """A new ``ChemistryImpl`` identical to ``chemistry`` except ``reaction_id``'s rate.

    Rebuilds only the intervened reaction (its reactant/product/modifier
    molecules pass through by identity, mirroring :meth:`ChemistryImpl.subgraph`'s
    derived-copy idiom); every other reaction and all molecules are shared,
    unchanged. ``chemistry`` itself is never mutated — an ``Intervene`` lever
    must not leak back into a caller's original ``world``/``chemistry``
    (needed for ``run``'s determinism: two calls against the same ``world``
    must not see each other's interventions).
    """
    old = chemistry.reactions[reaction_id]
    new_reactions = dict(chemistry.reactions)
    new_reactions[reaction_id] = ReactionImpl(
        reaction_id,
        reactants=old.reactants,
        products=old.products,
        modifiers=old.modifiers,
        rate=rate,
        dat=_mock_dat(f"rxn/{reaction_id}"),
    )
    return ChemistryImpl(
        chemistry.local_name,
        atoms=chemistry.atoms,
        molecules=chemistry.molecules,
        reactions=new_reactions,
        dat=_mock_dat(f"chem/{chemistry.local_name}"),
    )


def _state_with_concentration(
    state: WorldStateImpl, molecule_id: str, value: float
) -> WorldStateImpl:
    """A copy of ``state`` with ``molecule_id``'s concentration set to ``value``
    in every compartment. ``state`` itself is never mutated."""
    mol_ids = state.molecule_ids
    assert mol_ids is not None  # caller already checked `molecule_id in chemistry.molecules`
    mj = mol_ids.index(molecule_id)
    new_state = state.copy()
    for ci in range(new_state.num_compartments):
        new_state.set(ci, mj, value)
    return new_state


def run(
    world: WorldImpl,
    task: TaskInstance,
    agent: Agent,
    dials: Mapping[str, Any],
    seed: Seed,
    *,
    sim_cfg: SimConfig = SimConfig(steps=10, sample_every=10),
    max_turns: int = 50,
) -> TrialRecord:
    """Run ``agent`` against ``task``'s ``world`` for one immutable ``TrialRecord``.

    Each turn: (1) rebuild a fresh ``WorldImpl`` from the prior end-state
    (:func:`_world_from_state`; turn 0 folds ``world``'s own initial state
    through the identical path, so ``world`` is never touched or reused
    directly); (2) narrow the full state to an ``Observation`` via the shared
    :func:`~alienbio.suite.observation.narrow_observation` helper, keyed off
    ``dials`` and a per-turn child ``seed``; (3) ``agent.act(observation)``;
    (4) thread the returned reasoning steps into the ``DeliberationTrace``
    (:func:`~alienbio.suite.trial.thread_reasoning_steps`); (5) apply the
    action (lever / concentration / measurement / commit; an unknown lever or
    probe raises ``ValueError`` — Q1 = A, fail visibly); (6) simulate one
    ``sim_cfg`` burst and fold its end-state back in as the next turn's state.

    Terminates on ``Commit`` (``"committed"``), on cumulative action cost
    reaching the ``dials["budget"]`` dial's :class:`Budget` (default
    unlimited, ``"budget_exhausted"``), or after ``max_turns`` turns
    (``"max_turns"``) — recorded on the returned record's
    ``terminal_reason``, alongside the resolved ``budget``/``spent``/
    ``remaining`` (F023, M32.1). ``task_id`` is ``task.world`` (the per-task world
    name a :func:`~alienbio.suite.pipeline.build_suite` suite assigns, e.g.
    ``"world0"`` — the one field on ``TaskInstance`` that is unique per task).

    An ``AnswerObjective`` task that never commits has no answer to grade and
    scores ``0.0``; an ``OutcomeObjective`` task's scorer runs on the final
    timeline regardless of whether the trial committed (it scores the WORLD
    trajectory, not a submitted answer).

    Deterministic in ``(world, task, agent, dials, seed)``: two calls with a
    freshly-constructed but behaviourally identical ``agent`` (same policy)
    yield byte-identical ``action_log`` / ``objective_score`` (neither
    ``world`` nor its ``chemistry``/``initial_state`` is ever mutated, so nothing
    leaks between the two calls).
    """
    compartments = world.compartments
    chemistry = world.chemistry
    state: WorldStateImpl = world.initial_state
    budget = Budget.from_dial(dials.get("budget"))
    spent = 0.0

    trace = DeliberationTrace()
    action_records: list[ActionRecord] = []
    turn_times: list[float] = []
    turn_states: list[WorldStateImpl] = []
    elapsed = 0.0
    committed_answer = None
    reason = "max_turns"

    for turn in range(max_turns):
        turn_world = _world_from_state(compartments, chemistry, state, world.flows)

        observation = narrow_observation(state, dials, seed.child(f"turn/{turn}/observe"))
        action, reasoning_steps = agent.act(observation)
        trace = thread_reasoning_steps(trace, turn, action, reasoning_steps)
        action_records.append(
            ActionRecord(
                kind=type(action).__name__.lower(),
                destructive=isinstance(action, Intervene),
            )
        )
        spent += _action_cost(action)

        if isinstance(action, Measure):
            if action.probe not in chemistry.molecules:
                raise ValueError(f"Measure: unknown probe {action.probe!r}")
        elif isinstance(action, Intervene):
            if action.lever in chemistry.reactions:
                chemistry = _chemistry_with_rate(chemistry, action.lever, float(action.value))
            elif action.lever in chemistry.molecules:
                state = _state_with_concentration(state, action.lever, float(action.value))
            else:
                raise ValueError(
                    f"Intervene: unknown lever {action.lever!r} "
                    "(not a reaction or molecule in this world's chemistry)"
                )
            turn_world = _world_from_state(compartments, chemistry, state, world.flows)
        elif isinstance(action, Wait):
            pass
        elif isinstance(action, Commit):
            committed_answer = action.answer
        else:
            raise ValueError(f"unknown action type: {type(action).__name__}")

        timeline = simulate(turn_world, sim_cfg, seed.child(f"turn/{turn}/sim"))
        start = 0 if turn == 0 else 1  # skip the duplicate turn-boundary snapshot
        for t, s in zip(timeline.times[start:], timeline.states[start:]):
            turn_times.append(elapsed + t)
            turn_states.append(cast(WorldStateImpl, s))
        elapsed += timeline.times[-1]
        state = cast(WorldStateImpl, timeline.states[-1])

        if isinstance(action, Commit):
            reason = "committed"
            break
        if budget.exhausted(spent):
            reason = "budget_exhausted"
            break
    else:
        reason = "max_turns"

    final_timeline = Timeline(times=tuple(turn_times), states=tuple(turn_states))

    if reason == "committed" and isinstance(task.objective, AnswerObjective):
        assert committed_answer is not None
        objective_score = grade_answer(
            committed_answer, task.objective.key, task.objective.grader
        )
    elif isinstance(task.objective, OutcomeObjective):
        objective_score = grade_outcome(
            final_timeline, task.objective.scorer, task.objective.target
        )
    else:
        objective_score = 0.0  # AnswerObjective task, no Commit: nothing to grade

    return TrialRecord(
        task_id=task.world,
        condition_key=condition_key(dials),
        final_timeline=final_timeline,
        deliberation_trace=trace,
        action_log=tuple(action_records),
        objective_score=objective_score,
        terminal_reason=reason,
        budget=budget.total,
        spent=spent,
        remaining=budget.total - spent,
    )
