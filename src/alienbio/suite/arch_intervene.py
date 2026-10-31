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
  molecule's FINAL concentration in ONE compartment off ``timeline.states[-1]``
  and scores closeness to the goal with a bounded ``1 / (1 + |final - target|)``
  falloff. :func:`target_compartment` picks that compartment at draft time (T091
  E2: summing concentrations over compartments of different volumes ranked
  microcosm's worse feed rate higher).
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
from typing import TYPE_CHECKING, Any, Callable, Optional, cast

from ..bio.chemistry import ChemistryImpl
from ..bio.world import Compartment, WorldImpl
from ..infra.mk import mk
from .dist import Seed
from .types import (
    Answer,
    CarveResult,
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

#: The binding entry naming the compartment the target is read in (optional:
#: :func:`target_compartment` defaults it when the choice is unambiguous).
COMPARTMENT_ROLE = "compartment"


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


def target_compartment(
    world: WorldImpl,
    target_id: str,
    named: Optional[str] = None,
    *,
    task: str = "intervene",
    hint: Optional[str] = None,
) -> str:
    """The compartment an intervene task reads its target in (T091 E2).

    ``named`` (the binding's ``compartment`` entry) wins and must be one of
    the world's compartments. Unnamed: a one-compartment world's only
    compartment, else the one compartment that can hold ``target_id`` —
    read off the chemistry, not off the ``initial`` listing (T091 I4): a
    compartment holds the target when its initial amount there is > 0, or
    a reaction can make it there (every reaction runs in every compartment,
    so one whose reactants can all be present there — a reactant-free source
    always can), or a transport flow carries it in from a compartment that
    can hold it, or a death law releases it there, or a count flow carries
    it in with the individuals it moves (:func:`target_holders`).
    So a cosmetic ``P: 0.0`` changes nothing. Several holders, or none,
    refuse — naming the compartments — because a concentration summed over
    compartments of different volumes is no quantity the task states.
    ``task`` prefixes the refusal and ``hint`` replaces its binding advice,
    so another scorer reading one compartment (the conflict oracle,
    :mod:`~alienbio.suite.tradeoff`) shares the rule.
    """
    ids = [str(c.id) for c in world.compartments]
    if named is not None:
        if str(named) not in ids:
            raise ValueError(
                f"{task}: target compartment {named!r} is not a compartment of the world {ids}"
            )
        return str(named)
    if len(ids) == 1:
        return ids[0]
    holders = target_holders(world, target_id)
    if len(holders) == 1:
        return holders[0]
    where = f"can be held in {holders}" if holders else "is held in none"
    if hint is None:
        hint = (
            f"name the one to score with a {COMPARTMENT_ROLE!r} binding (binding: {{{TARGET_ROLE}: ..., "
            f"{COMPARTMENT_ROLE}: <id>}})"
        )
    raise ValueError(f"{task}: target {target_id!r} {where} of the world's compartments {ids}; {hint}")


def target_holders(world: Any, target_id: str) -> list[str]:
    """The compartments (in world order) that can ever hold ``target_id``: a
    fixpoint over what each compartment can contain — its initial amounts
    above zero, the products of every reaction whose reactants can all be
    there (the simulators run every reaction in every compartment; a rate
    of 0 still counts, since an Intervene may set it), what a transport flux
    carries while its driver can be in the origin, what a death law
    releases, and what a count flow carries from its origin to its dest
    with the individuals it moves. Duck-typed: a world without ``flows`` / ``population_laws``
    has none (T091 I4)."""
    comps = list(world.compartments)
    present: dict[str, set[str]] = {
        str(c.id): {str(m) for m, v in dict(c.concentrations).items() if float(v) > 0.0} for c in comps
    }
    reactions = [
        ({m.name for m in r.reactants}, {m.name for m in r.products})
        for r in dict(world.chemistry.reactions).values()
    ]
    # A transport flux runs origin -> dest while its driver is in the origin;
    # a positive count carries a species to dest, a negative one back (bio/flow.py).
    flows = [
        (
            str(f.origin),
            str(f.dest),
            str(f.driver_molecule),
            {str(m) for m, n in dict(f.stoichiometry).items() if float(n) > 0},
            {str(m) for m, n in dict(f.stoichiometry).items() if float(n) < 0},
        )
        for f in getattr(world, "flows", ()) or ()
    ]
    releases = [
        (str(law.release_compartment), str(law.release_resource))
        for law in getattr(world, "population_laws", ()) or ()
        if getattr(law, "release_compartment", None) is not None and getattr(law, "release_resource", None) is not None
    ]
    for comp, resource in releases:
        if comp in present:
            present[comp].add(resource)
    # A count flow (``CountFlow``) moves individuals origin -> dest with their
    # contents (``Carry(src=origin, dst=dest, removes=True)``), so whatever the
    # origin can hold the dest can come to hold (T091 M7). It is the one
    # population law whose carry changes compartment: a birth copies in place
    # and a death's contents leave the world.
    carries = [
        (str(law.origin), str(law.dest))
        for law in getattr(world, "population_laws", ()) or ()
        if getattr(law, "origin", None) is not None and getattr(law, "dest", None) is not None
    ]
    changed = True
    while changed:
        changed = False
        for held in present.values():
            for reactants, products in reactions:
                if reactants <= held and not products <= held:
                    held |= products
                    changed = True
        for origin, dest, driver, forward, back in flows:
            if origin not in present or dest not in present or driver not in present[origin]:
                continue
            for src, dst, carried in ((origin, dest, forward), (dest, origin, back)):
                moved = (carried & present[src]) - present[dst]
                if moved:
                    present[dst] |= moved
                    changed = True
        for origin, dest in carries:
            if origin in present and dest in present and not present[origin] <= present[dest]:
                present[dest] |= present[origin]
                changed = True
    return [str(c.id) for c in comps if target_id in present[str(c.id)]]


def _final_concentration(timeline: Timeline, molecule_id: str, compartment: Optional[str] = None) -> float:
    """Final concentration of ``molecule_id`` in one compartment.

    Reads ``timeline.states[-1]`` (a self-describing
    :class:`~alienbio.bio.world_state.WorldStateImpl`), locates the molecule on
    its id axis and ``compartment`` on its compartment axis. ``compartment``
    unset is allowed only on a one-compartment state — the drafters of the
    generative intervene world, whose only compartment is ``cell``.

    Raises:
        ValueError: if the timeline has no states, the final state is a
            pure-int state (no ``molecule_ids`` axis to locate the molecule on),
            ``compartment`` is unset on a multi-compartment state, or names a
            compartment the state does not carry.
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
    comp_ids = state.compartment_ids
    if compartment is None:
        if len(arr) != 1:
            raise ValueError(
                f"target {molecule_id!r}: the state has {len(arr)} compartments "
                f"{list(comp_ids) if comp_ids is not None else ''}; the scorer needs the one to read "
                "(see target_compartment)"
            )
        return float(arr[0][j])
    if comp_ids is None or compartment not in comp_ids:
        raise ValueError(
            f"target compartment {compartment!r} is not on the state's compartment axis "
            f"{list(comp_ids) if comp_ids is not None else '(unlabelled)'}"
        )
    return float(arr[comp_ids.index(compartment)][j])


def make_target_scorer(
    target_mol_id: str, target_value: float, compartment: Optional[str] = None
) -> Callable[[Timeline], float]:
    """A scorer over a :class:`Timeline` measuring closeness to the goal.

    The returned callable reads the target molecule's FINAL concentration in
    ``compartment`` (unset: the state's only compartment) off
    ``timeline.states[-1]`` and returns ``1 / (1 + |final - target_value|)`` — a
    bounded score in ``(0, 1]`` that is exactly ``1.0`` when the final
    concentration hits the target and decays monotonically as it drifts away. The
    scorer closes over ``target_mol_id`` and ``target_value``; it is opaque to
    :func:`grade_outcome`, which only ever invokes it.
    """

    def scorer(timeline: Timeline) -> float:
        final = _final_concentration(timeline, target_mol_id, compartment)
        return 1.0 / (1.0 + abs(final - target_value))

    return scorer


def make_intervention_objective(
    target_mol_id: str,
    target_value: float,
    compartment: Optional[str] = None,
    *,
    world: WorldImpl,
) -> OutcomeObjective:
    """Bundle the target scorer into an :class:`OutcomeObjective`.

    The objective carries the scorer (closed over ``target_mol_id`` /
    ``target_value``) and the ``target_value`` as its opaque ``target`` — the
    shape :func:`grade_outcome` expects (``target`` is passed through untouched;
    the scorer holds any context it needs).

    ``world`` (T091 I5, required since T092): the compartment is resolved
    HERE by :func:`target_compartment` — a multi-compartment world with no
    ``compartment`` named refuses at construction, with the draft-time
    message, for every caller, instead of from the scorer after every turn
    has been taken (and, under a live agent, paid for). It was optional, and
    a caller that left it out got that refusal only when scored.
    """
    compartment = target_compartment(world, target_mol_id, compartment)
    return OutcomeObjective(
        scorer=make_target_scorer(target_mol_id, target_value, compartment),
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

    def build_objective(self, skeleton: CarveResult, world: WorldImpl) -> OutcomeObjective:
        """The outcome objective, read in the compartment :func:`target_compartment`
        picks — refused at draft when the world leaves it ambiguous."""
        target = self._target_id(skeleton)
        return make_intervention_objective(target, self.target_value, skeleton.binding.get(COMPARTMENT_ROLE), world=world)

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
