"""M29.4 — the ``predict_response`` task archetype.

The mechanism-discovery family asks *what happens if you push a lever*: given a
small reaction network and a named perturbation (speed up one reaction), predict
how a named target molecule's steady-state level responds — ``up`` / ``down`` /
``same``. Unlike ``diagnose_perturbation`` (whose ground truth is a *generation
choice* read straight off the skeleton binding), this archetype's ground truth
is **computed from real physics**: the drafter fixes the network, the perturbed
reaction, and the target molecule, and the answer is obtained by *simulating*
the baseline world and the perturbed world and comparing the target's final
concentration. The response is therefore correct by construction — it is the
observed outcome of the exact simulation, recomputed deterministically.

The drafter constructs the :class:`CarveResult` directly (never carves): a recipe
never inspects how a binding arose. The binding records the *structural* facts
of the task — ``binding['perturbed']`` (the perturbed reaction id) and
``binding['target']`` (the molecule whose response is predicted). The response
tokens ``up`` / ``down`` / ``same`` are **not** node ids; they are an opaque
three-value vocabulary carried under the ``node_id`` answer kind (the engines
only ever substitute surface phrases, they never interpret a token).

Molecule-gate discipline: the ``target`` role is gated to a molecule and the
``perturbed`` role to a reaction (via defensive constraints), and the drafter
only ever picks a real molecule / real reaction — so the *question* payload can
never mix up which is which. The audited HIGH-severity corruption (a key that
threaded a reaction node) cannot occur here: the key is one of three fixed
response tokens, verified distinct from every node id.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import cast

from ..bio.chemistry import ChemistryImpl
from ..bio.world import Compartment, WorldImpl
from ..bio.world_state import WorldStateImpl
from ..infra.mk import mk
from .dist import Seed
from .perturbations import perturb_rate
from .types import (
    Answer,
    FeatureSet,
    GraderSpec,
    CarveResult,
    Motif,
    Question,
    RoleSlot,
    TaskArchetype,
)
from .verify import SimConfig, simulate

#: Role name for the perturbed reaction (a reaction id, by construction).
PERTURBED_ROLE = "perturbed"
#: Role name for the target molecule whose response is predicted.
TARGET_ROLE = "target"
#: The three opaque response tokens (an ordered, exhaustive vocabulary).
RESPONSE_TOKENS: tuple[str, str, str] = ("up", "down", "same")
#: Default absolute delta below which a response is classified ``same``.
DEFAULT_TOL = 1e-6
#: Default rate-scaling factor applied to the perturbed reaction.
DEFAULT_FACTOR = 3.0


def _is_molecule(node: object) -> bool:
    """Role-gate predicate admitting molecule nodes only.

    Reaction nodes expose ``reactants``; molecule nodes do not — so this keeps a
    reaction from ever binding to the ``target`` role. Defensive: the drafter
    already only ever chooses a molecule for the target.
    """
    return not hasattr(node, "reactants")


def _is_reaction(node: object) -> bool:
    """Role-gate predicate admitting reaction nodes only (mirror of :func:`_is_molecule`)."""
    return hasattr(node, "reactants")


def _final_concentration(world: WorldImpl, target_id: str, sim_cfg: SimConfig, seed: Seed) -> float:
    """Simulate ``world`` and read the target molecule's FINAL concentration.

    Uses the single compartment's id as the read axis (this archetype drafts a
    one-compartment world). Deterministic in ``(world, sim_cfg)``.
    """
    timeline = simulate(world, sim_cfg, seed)
    comp_id = world.compartments[0].id
    # states are typed as the WorldState protocol; the concrete impl exposes concentration().
    final = cast(WorldStateImpl, timeline.states[-1])
    return float(final.concentration(comp_id, target_id))


def predicted_response(
    world: WorldImpl,
    target_id: str,
    reaction_id: str,
    factor: float,
    sim_cfg: SimConfig = SimConfig(),
    seed: Seed = Seed(0),
    *,
    tol: float = DEFAULT_TOL,
) -> str:
    """Compute the ground-truth response token from real simulation.

    Simulates the baseline world and the world with ``reaction_id``'s rate scaled
    by ``factor`` (via :func:`~alienbio.suite.perturbations.perturb_rate`), under
    the *same* ``sim_cfg`` and ``seed``, then compares ``target_id``'s final
    concentration:

    - ``up``   — the perturbed final exceeds the baseline final by more than ``tol``;
    - ``down`` — it falls below the baseline final by more than ``tol``;
    - ``same`` — the absolute delta is within ``tol``.

    Deterministic: identical inputs always yield the identical token (the
    integrator is deterministic and ``seed`` only matters under stochastic
    pressure, which this path never supplies).
    """
    base_final = _final_concentration(world, target_id, sim_cfg, seed)
    perturbed_world = perturb_rate(world, reaction_id, factor)
    pert_final = _final_concentration(perturbed_world, target_id, sim_cfg, seed)
    delta = pert_final - base_final
    if abs(delta) <= tol:
        return "same"
    return "up" if delta > 0.0 else "down"


def draft_prediction_world(
    seed: Seed = Seed(0),
    *,
    n_nodes: int = 4,
    factor: float = DEFAULT_FACTOR,
    ill_posed: bool = False,
) -> tuple[WorldImpl, CarveResult, str]:
    """Draft a chain network and fix a perturbation target reaction + target molecule.

    ``ill_posed=True`` (M36.3 / EXP-6's meta-objective trap) makes the
    question *subtly ill-posed*: the link immediately downstream of the
    perturbed reaction (``m1_m2``) is kept in the chemistry but made inert
    (rate ``0.0``), so the target is unreachable from the perturbation and the
    simulated response is ``same`` by construction. Nothing in the question
    changes — the agent must notice. Requires ``n_nodes >= 3`` (there must be
    a downstream link to cut).

    Builds ``n_nodes`` molecules ``m0 … m_{n-1}`` chained by ``n_nodes - 1``
    unidirectional reactions ``m0_m1, m1_m2, …``; the source ``m0`` starts high so
    the chain has substrate to propagate to the terminal sink ``m_{n-1}``. The
    perturbed reaction is the *first* (``m0_m1`` — the chain's throttle) and the
    target molecule is the *terminal sink* (``m_{n-1}`` — a monotonic accumulator),
    so speeding the throttle moves more mass downstream and the response is a
    well-defined ``up`` for ``factor > 1``.

    ``seed`` varies only the reaction *rates* (the dynamics), leaving the molecular
    *structure* — and therefore the perturbed/target choice — seed-invariant, so
    the drafted structure is deterministic in ``seed``.

    Returns ``(world, skeleton, reaction_id)``:
    - ``skeleton.binding['perturbed']`` is the perturbed reaction id,
    - ``skeleton.binding['target']`` is the target molecule id,
    - the returned ``reaction_id`` is the perturbed reaction (echoed so a caller can
      build the recipe without re-reading the binding). ``factor`` and ``seed`` are
      the reproducibility knobs — pass them (with ``reaction_id`` / ``target``) to
      :func:`predict_response` so the recipe recomputes the identical response.
    """
    if n_nodes < 2:
        raise ValueError(f"n_nodes must be >= 2, got {n_nodes}")
    if ill_posed and n_nodes < 3:
        raise ValueError(f"ill_posed needs n_nodes >= 3 (a downstream link to cut), got {n_nodes}")

    node_names = [f"m{i}" for i in range(n_nodes)]
    molecules = [mk.M(name) for name in node_names]
    by_name = {name: molecules[i] for i, name in enumerate(node_names)}

    reaction_ids = [f"{node_names[i]}_{node_names[i + 1]}" for i in range(n_nodes - 1)]
    inert = reaction_ids[1] if ill_posed else None
    reactions = [
        mk.R(
            reaction_ids[i],
            {by_name[node_names[i]]: 1.0},
            {by_name[node_names[i + 1]]: 1.0},
            rate=0.0
            if reaction_ids[i] == inert
            else float(seed.child(f"rate/{reaction_ids[i]}").rng().uniform(0.1, 1.0)),
        )
        for i in range(n_nodes - 1)
    ]

    # mk.C is dynamically dispatched (-> Entity); this call yields a ChemistryImpl.
    chem = cast(ChemistryImpl, mk.C("predict_host", molecules, reactions))

    concentrations: dict[str, float] = {name: 0.0 for name in node_names}
    concentrations[node_names[0]] = 100.0
    comp = Compartment("cell", None, "cell", 1.0, concentrations=concentrations)
    world = WorldImpl(chem, (comp,))

    reaction_id = reaction_ids[0]       # perturb the chain's throttle
    target_id = node_names[-1]          # predict the terminal sink

    # Molecule-gate discipline (defensive; the drafter's own choice already holds):
    # the target is a real molecule, the perturbed lever is a real reaction.
    assert target_id in chem.molecules and target_id not in chem.reactions
    assert reaction_id in chem.reactions and reaction_id not in chem.molecules

    perturbed_role = RoleSlot(
        name=PERTURBED_ROLE, type_tag="perturbed_reaction", constraints=(_is_reaction,)
    )
    target_role = RoleSlot(
        name=TARGET_ROLE, type_tag="response_target", constraints=(_is_molecule,)
    )
    motif = Motif(roles=(perturbed_role, target_role), edges=())
    skeleton = CarveResult(
        motif=motif, binding={PERTURBED_ROLE: reaction_id, TARGET_ROLE: target_id}
    )
    return world, skeleton, reaction_id


@dataclass(frozen=True)
class PredictResponseRecipe:
    """Recipe for ``predict_response``: predict a target molecule's response token.

    Holds the *structural* task facts (``reaction_id``, ``target_id``) plus the
    perturbation magnitude (``factor``) and the deterministic simulation knobs
    (``sim_cfg``, ``seed``, ``tol``). ``build_key`` recomputes the response from
    real physics via :func:`predicted_response` — so the key is exactly the
    observed simulation outcome. Question kind is ``node_set`` (what was perturbed
    + what to predict); answer kind is ``node_id`` (the opaque response token).
    """

    reaction_id: str
    target_id: str
    factor: float = DEFAULT_FACTOR
    verb: str = "predict"
    sim_cfg: SimConfig = field(default_factory=SimConfig)
    seed: Seed = field(default_factory=lambda: Seed(0))
    tol: float = DEFAULT_TOL

    def build_question(self, skeleton: CarveResult, world: WorldImpl) -> Question:
        """What was perturbed + what to predict, as a ``node_set`` question.

        The two structural facts (perturbed reaction id, target molecule id) as a
        set — the framing ``verb='predict'`` renders "given the perturbation of
        {…}, predict the response?".
        """
        return Question(
            structured={self.reaction_id, self.target_id}, kind="node_set"
        )

    def build_key(self, skeleton: CarveResult, world: WorldImpl) -> Answer:
        """The simulated response token — computed from real physics by construction."""
        token = predicted_response(
            world,
            self.target_id,
            self.reaction_id,
            self.factor,
            self.sim_cfg,
            self.seed,
            tol=self.tol,
        )
        return Answer(value=token, kind="node_id")

    def build_distractors(
        self, skeleton: CarveResult, world: WorldImpl, seed: Seed
    ) -> tuple[Answer, ...]:
        """The other two response tokens as ``node_id`` distractors.

        Deterministic and distinct: the fixed three-token vocabulary minus the key
        token, so exactly two near-miss responses, each a real response token
        (never a node id).
        """
        key_token = self.build_key(skeleton, world).value
        return tuple(
            Answer(value=token, kind="node_id")
            for token in RESPONSE_TOKENS
            if token != key_token
        )

    def grader_spec(self) -> GraderSpec:
        """Exact single-token grading."""
        return GraderSpec(kind="node_id")


def predict_response(
    reaction_id: str,
    target_id: str,
    factor: float = DEFAULT_FACTOR,
    *,
    sim_cfg: SimConfig = SimConfig(),
    seed: Seed = Seed(0),
    archetype_id: str = "predict_response",
) -> TaskArchetype:
    """Build a ``predict_response`` archetype over a fixed perturbation + target.

    The motif has two gated roles — ``perturbed`` (a reaction) and ``target`` (a
    molecule) — and no edges; the ground truth is *computed by simulation*, not a
    subgraph to carve. The archetype makes no world-validity demand (empty
    :class:`FeatureSet`); its recipe grades the predicted response token exactly.

    This is framework machinery — a template parameterized by the perturbation
    dial (``factor``) and the network's structural facts, not a hand-authored
    scenario.
    """
    perturbed_role = RoleSlot(
        name=PERTURBED_ROLE, type_tag="perturbed_reaction", constraints=(_is_reaction,)
    )
    target_role = RoleSlot(
        name=TARGET_ROLE, type_tag="response_target", constraints=(_is_molecule,)
    )
    motif = Motif(roles=(perturbed_role, target_role), edges=())
    recipe = PredictResponseRecipe(
        reaction_id=reaction_id,
        target_id=target_id,
        factor=factor,
        sim_cfg=sim_cfg,
        seed=seed,
    )
    return TaskArchetype(
        id=archetype_id,
        motif=motif,
        verb="predict",
        feature_reqs=FeatureSet(),
        recipe=recipe,
    )
