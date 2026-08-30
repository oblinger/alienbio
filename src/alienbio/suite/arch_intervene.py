"""M29.3 — the ``design_intervention`` archetype (OUTCOME-scored).

Where the mechanism-discovery family (``identify_pathway`` in
:mod:`alienbio.suite.archetypes`) grades a *submitted answer* against a
skeleton-derived key, this archetype grades an *outcome*: a task drives a target
molecule to a target concentration, and success is a continuous score read off
the final simulated state — there is no answer key. It is the first user of the
``OutcomeObjective`` / :func:`alienbio.suite.grade.grade_outcome` path (both
defined but never yet exercised).

The pieces are deliberately separable so an integration layer can wire them
either way:

- :func:`draft_intervention_world` builds a host network and CHOOSES the ground
  truth directly — it constructs the :class:`CarveResult` by hand (binding the
  ``target`` role to a real molecule id) rather than carving, then returns the
  ``(target_molecule_id, target_value)`` goal. The ``target_value`` defaults to
  the concentration the target naturally reaches, so the objective is coherent
  and self-consistent (simulating the returned world scores ~1.0).
- :func:`make_target_scorer` is the opaque scorer factory: it reads the target
  molecule's FINAL concentration off ``timeline.states[-1]`` and scores closeness
  to the goal with a bounded ``1 / (1 + |final - target|)`` falloff.
- :func:`make_intervention_objective` bundles that scorer into an
  :class:`OutcomeObjective`.
- :class:`DesignInterventionRecipe` is the :class:`ObjectiveRecipe` for the
  archetype: its question renders the target molecule (a ``node_set`` framed by
  the ``intervene`` verb); its "key" and distractors are trivial because outcome
  tasks grade through the scorer, never an :class:`Answer`.

**Molecule gate (audit lesson).** A prior archetype threaded a *reaction* node
into a ground-truth key. Here the target role is gated to molecules and every
constructed binding is verified to be a real molecule id, so the scorer can never
be pointed at a non-molecule node.

The real-physics agent loop (an agent actually intervening on the world) is out
of scope: this module builds the objective + scorer + recipe, exercised via a
direct :func:`alienbio.suite.verify.simulate` + :func:`grade_outcome`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Optional, cast

from ..bio.chemistry import ChemistryImpl
from ..bio.world import Compartment, WorldImpl
from ..infra.mk import mk
from .dist import Seed
from .types import (
    Answer,
    CarveResult,
    FeatureSet,
    GraderSpec,
    Motif,
    OutcomeObjective,
    Question,
    RoleSlot,
    TaskArchetype,
    Timeline,
)
from .verify import SimConfig, simulate

if TYPE_CHECKING:
    from ..bio.world_state import WorldStateImpl

#: The role name the ``target`` molecule binds to on the skeleton.
TARGET_ROLE = "target"


def _is_molecule(node: object) -> bool:
    """True for a molecule node, False for a reaction node.

    Reaction nodes expose ``reactants``; molecules do not — so this gates the
    ``target`` role to molecules without importing the concrete impl class, the
    same discipline the pathway archetype uses to keep reaction nodes out of a
    ground-truth key.
    """
    return not hasattr(node, "reactants")


def _intervention_motif() -> Motif:
    """A one-role motif: a single molecule-gated ``target`` slot, no edges."""
    role = RoleSlot(
        name=TARGET_ROLE,
        type_tag="intervention_target",
        constraints=(_is_molecule,),
    )
    return Motif(roles=(role,), edges=())


def _final_concentration(timeline: Timeline, molecule_id: str) -> float:
    """Total final concentration of ``molecule_id`` across all compartments.

    Reads ``timeline.states[-1]`` (a self-describing
    :class:`~alienbio.bio.world_state.WorldStateImpl`), locates the molecule on
    its id axis, and sums that molecule's column of ``as_array()`` over every
    compartment — so the scorer never needs to know a compartment id.

    Raises:
        ValueError: if the timeline has no states, or the final state is a
            pure-int state (no ``molecule_ids`` axis to locate the molecule on).
        KeyError: if ``molecule_id`` is absent from the state's molecule axis.
    """
    if not timeline.states:
        raise ValueError("timeline has no states to score")
    state = cast("WorldStateImpl", timeline.states[-1])
    mol_ids = state.molecule_ids
    if mol_ids is None:
        raise ValueError(
            "final timeline state is not self-describing (no molecule_ids); "
            "cannot locate the target molecule"
        )
    try:
        j = mol_ids.index(molecule_id)
    except ValueError:
        raise KeyError(
            f"target molecule id {molecule_id!r} is not on the state's molecule axis"
        ) from None
    arr = state.as_array()  # [compartments x molecules] (numpy 2D or list-of-lists)
    return float(sum(row[j] for row in arr))


def make_target_scorer(
    target_mol_id: str, target_value: float
) -> Callable[[Timeline], float]:
    """A scorer over a :class:`Timeline` measuring closeness to the goal.

    The returned callable reads the target molecule's FINAL concentration off
    ``timeline.states[-1]`` and returns ``1 / (1 + |final - target_value|)`` — a
    bounded score in ``(0, 1]`` that is exactly ``1.0`` when the final
    concentration hits the target and decays monotonically as it drifts away. The
    scorer closes over ``target_mol_id`` and ``target_value``; it is opaque to
    :func:`grade_outcome`, which only ever invokes it.
    """

    def scorer(timeline: Timeline) -> float:
        final = _final_concentration(timeline, target_mol_id)
        return 1.0 / (1.0 + abs(final - target_value))

    return scorer


def make_intervention_objective(
    target_mol_id: str, target_value: float
) -> OutcomeObjective:
    """Bundle the target scorer into an :class:`OutcomeObjective`.

    The objective carries the scorer (closed over ``target_mol_id`` /
    ``target_value``) and the ``target_value`` as its opaque ``target`` — the
    shape :func:`grade_outcome` expects (``target`` is passed through untouched;
    the scorer holds any context it needs).
    """
    return OutcomeObjective(
        scorer=make_target_scorer(target_mol_id, target_value),
        target=target_value,
    )


@dataclass(frozen=True)
class DesignInterventionRecipe:
    """Recipe for ``design_intervention``: drive the target to its goal.

    CarveResult-first like the pathway recipe — the target molecule id is read off
    ``skeleton.binding[role_name]`` by construction (we bound it, so we hold it).
    ``target_value`` is the goal concentration (a dial parameter, not a graded
    key). Because the task is outcome-scored:

    - ``build_key`` returns a **trivial** :class:`Answer` (the scalar target, for
      interface symmetry only) — grading goes through the scorer, never a key;
    - ``build_distractors`` returns an **empty** tuple (no multiple-choice
      framing for an outcome task);
    - ``grader_spec`` declares ``kind="outcome"`` so the engine routes to
      :func:`grade_outcome` + the scorer built by
      :func:`make_intervention_objective`.
    """

    target_value: float
    role_name: str = TARGET_ROLE
    verb: str = "intervene"

    def _target_id(self, skeleton: CarveResult) -> str:
        """The target molecule id — read off the skeleton by construction."""
        return skeleton.binding[self.role_name]

    def build_question(self, skeleton: CarveResult, world: WorldImpl) -> Question:
        """The target molecule as a single-element ``node_set`` question.

        A set, not a list — ``parse`` returns a set, so the pipeline round-trip
        guard (``parse(render(q)) == q``) requires set-valued ``node_set`` payloads.
        """
        return Question(structured={self._target_id(skeleton)}, kind="node_set")

    def build_key(self, skeleton: CarveResult, world: WorldImpl) -> Answer:
        """Trivial key (the scalar target) — outcome tasks grade via the scorer."""
        return Answer(value=self.target_value, kind="scalar")

    def grader_spec(self) -> GraderSpec:
        """Outcome grading — routed through :func:`grade_outcome` + the scorer."""
        return GraderSpec(kind="outcome")


def design_intervention(
    target_value: float,
    *,
    archetype_id: str = "design_intervention",
) -> TaskArchetype:
    """Build the ``design_intervention`` archetype (drive the target to a goal).

    The motif is a single molecule-gated ``target`` role (no edges — the archetype
    demands only that the world host one molecule to steer); the recipe carries
    the goal ``target_value`` and reads the target molecule off the skeleton.
    Framework machinery: parameterized by a dial (``target_value``), never a
    hand-authored scenario.
    """
    return TaskArchetype(
        id=archetype_id,
        motif=_intervention_motif(),
        verb="intervene",
        feature_reqs=FeatureSet(),
        recipe=DesignInterventionRecipe(target_value=float(target_value)),
    )


def draft_intervention_world(
    seed: Seed = Seed(0),
    *,
    n_nodes: int = 4,
    target_value: Optional[float] = None,
    sim_cfg: SimConfig = SimConfig(),
) -> tuple[WorldImpl, CarveResult, tuple[str, float]]:
    """Draft an intervention world + hand-built skeleton + ``(target_id, goal)``.

    Builds a linear reaction chain ``m0 -> m1 -> … -> m_{n-1}`` (``n = n_nodes``,
    which must be ≥ 2) with the source ``m0`` seeded high, so mass flows toward the
    sink ``m_{n-1}`` — the target molecule. ``seed`` varies the reaction *rates*
    (the dynamics), leaving the molecular structure — and therefore the chosen
    target id — seed-invariant; the world is deterministic in ``seed``.

    Ground truth is CHOSEN directly, not carved: the returned :class:`CarveResult`
    binds the ``target`` role straight to the sink molecule id (verified to be a
    real molecule, never a reaction node). ``target_value`` defaults to the
    concentration the target naturally reaches under :func:`simulate` — so the
    returned objective is self-consistent (simulating the returned world scores
    ~1.0). Pass an explicit ``target_value`` to set an arbitrary goal instead.

    Returns:
        ``(world, skeleton, (target_molecule_id, target_value))``.
    """
    if n_nodes < 2:
        raise ValueError(f"n_nodes must be >= 2, got {n_nodes}")

    names = [f"m{i}" for i in range(n_nodes)]
    molecules = [mk.M(name) for name in names]
    by_name = {name: molecules[i] for i, name in enumerate(names)}

    reactions = [
        mk.R(
            f"{names[i]}_{names[i + 1]}",
            {by_name[names[i]]: 1.0},
            {by_name[names[i + 1]]: 1.0},
            rate=float(
                seed.child(f"rate/{names[i]}_{names[i + 1]}").rng().uniform(0.1, 1.0)
            ),
        )
        for i in range(n_nodes - 1)
    ]

    # mk.C is dynamically dispatched (-> Entity); this call yields a ChemistryImpl.
    chem = cast(ChemistryImpl, mk.C("intervene_host", molecules, reactions))

    concentrations: dict[str, float] = {name: 0.0 for name in names}
    concentrations[names[0]] = 100.0
    comp = Compartment("cell", None, "cell", 1.0, concentrations=concentrations)
    world = WorldImpl(chem, (comp,))

    # The target is the chain sink; verify it is a real molecule (never a
    # reaction node) before it ever reaches the scorer / key.
    target_mol_id = names[-1]
    if target_mol_id not in world.chemistry.molecules:
        raise RuntimeError(
            f"target {target_mol_id!r} is not a molecule of the drafted chemistry"
        )
    if not _is_molecule(world.chemistry.molecules[target_mol_id]):
        raise RuntimeError(
            f"target {target_mol_id!r} bound to a non-molecule node (reaction); "
            "the intervention key would be corrupt"
        )

    # Default the goal to the naturally-reached final concentration, so the
    # returned objective is coherent and self-consistent.
    if target_value is None:
        baseline = simulate(world, sim_cfg, seed.child("draft-sim"))
        target_value = _final_concentration(baseline, target_mol_id)

    skeleton = CarveResult(
        motif=_intervention_motif(),
        binding={TARGET_ROLE: target_mol_id},
    )
    return world, skeleton, (target_mol_id, float(target_value))
