"""M29.2 — the ``diagnose_perturbation`` task archetype.

The mechanism-discovery family asks *which node is the distinguished one*: given
a small reaction network in which exactly one molecule has been perturbed, name
that molecule from the candidate set. Unlike ``identify_pathway`` (whose ground
truth is *recovered* by carving a hidden motif out of an authored host), this
archetype's ground truth is a **generation choice** — we *pick* the perturbed
node when drafting the world. So the drafter constructs the :class:`CarveResult`
directly with a hand-built binding rather than carving: a recipe never inspects
how a binding arose, so a directly-built one is indistinguishable from a carved
one to every downstream engine.

Because we *chose* the answer, the key is correct by construction: every recipe
method reads the perturbed node off ``skeleton.binding['target']``. The role is
molecule-gated (both by the drafter, which only ever picks a molecule, and by a
defensive constraint on the role) so the key can never be a *reaction* id — the
HIGH-severity corruption a recent audit caught in a sibling archetype.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from ..bio.chemistry import ChemistryImpl
from ..bio.world import Compartment, WorldImpl
from ..infra.mk import mk
from .dist import Seed
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

if TYPE_CHECKING:
    pass

#: The single role name of this archetype's motif — the perturbed node.
TARGET_ROLE = "target"
#: The type tag carried by that role.
PERTURBED_TAG = "perturbed_node"


def _is_molecule(node: object) -> bool:
    """Role-gate predicate admitting molecule nodes only.

    Reaction nodes expose ``reactants``; molecule nodes do not — so this excludes
    a reaction from ever binding to the ``target`` role, which would corrupt the
    ground-truth key with a non-molecule id (the audited HIGH-severity failure).
    Defensive here: the drafter already only ever chooses a molecule.
    """
    return not hasattr(node, "reactants")


def draft_diagnosis_world(
    seed: Seed = Seed(0),
    *,
    n_nodes: int = 4,
    distractor_count: int = 0,
) -> tuple[WorldImpl, CarveResult]:
    """Draft a small reaction network and *choose* one molecule as perturbed.

    Builds ``n_nodes`` molecules ``m0 … m_{n-1}`` chained by ``n_nodes - 1``
    unidirectional reactions, plus ``distractor_count`` off-chain molecules
    ``d0 …`` (extra candidates that widen the answer set). One molecule is picked
    as the perturbed ``target`` seed-deterministically, and a :class:`CarveResult` is
    **constructed directly** (never carved) binding the sole ``target`` role to
    that molecule id.

    Deterministic in ``seed``: the same seed always selects the same target and
    yields the same structure. The molecular structure itself is seed-invariant;
    only the choice of which molecule is perturbed varies with the seed.

    Returns ``(world, skeleton)`` — the skeleton's ``binding['target']`` is the
    ground truth this archetype's recipe reads its key off of.
    """
    if n_nodes < 1:
        raise ValueError(f"n_nodes must be >= 1, got {n_nodes}")
    if distractor_count < 0:
        raise ValueError(f"distractor_count must be >= 0, got {distractor_count}")

    node_names = [f"m{i}" for i in range(n_nodes)]
    molecules = [mk.M(name) for name in node_names]
    by_name = {name: molecules[i] for i, name in enumerate(node_names)}

    reactions = [
        mk.R(
            f"r{i}",
            {by_name[node_names[i]]: 1.0},
            {by_name[node_names[i + 1]]: 1.0},
        )
        for i in range(n_nodes - 1)
    ]

    distractors = [mk.M(f"d{i}") for i in range(distractor_count)]

    # mk.C is dynamically dispatched (-> Entity); this call yields a ChemistryImpl.
    chem = cast(ChemistryImpl, mk.C("host", molecules + distractors, reactions))

    # Seed the chain's source high so the network has substrate to move.
    concentrations: dict[str, float] = {name: 0.0 for name in node_names}
    if node_names:
        concentrations[node_names[0]] = 100.0
    for i in range(distractor_count):
        concentrations[f"d{i}"] = 1.0

    comp = Compartment("cell", None, "cell", 1.0, concentrations=concentrations)
    world = WorldImpl(chem, (comp,))

    # Choose the perturbed node seed-deterministically (a molecule by
    # construction — the candidate set is exactly the molecule ids).
    target_idx = int(seed.child("target").rng().integers(n_nodes))
    target_id = node_names[target_idx]

    role = RoleSlot(
        name=TARGET_ROLE, type_tag=PERTURBED_TAG, constraints=(_is_molecule,)
    )
    motif = Motif(roles=(role,), edges=())
    skeleton = CarveResult(motif=motif, binding={TARGET_ROLE: target_id})
    return world, skeleton


@dataclass(frozen=True)
class DiagnosePerturbationRecipe:
    """Recipe for ``diagnose_perturbation``: name the one perturbed node.

    Holds the role name of the perturbed node (``target``); every method reads the
    concrete answer off ``skeleton.binding[target_role]`` — the binding the drafter
    *chose* — so the key is correct by construction. Question kind is ``node_set``
    (present the candidate molecules); answer kind is ``node_id`` (the single
    perturbed node).
    """

    target_role: str = TARGET_ROLE
    verb: str = "diagnose"

    def build_question(self, skeleton: CarveResult, world: WorldImpl) -> Question:
        """The candidate set — every molecule id — as a ``node_set`` question.

        ``node_set`` payloads are sets: ``parse`` returns a set, so a list here
        would fail the pipeline's round-trip guard (``parse(render(q)) == q``).
        """
        return Question(structured=set(world.chemistry.molecules), kind="node_set")

    def build_key(self, skeleton: CarveResult, world: WorldImpl) -> Answer:
        """The perturbed node — read off the skeleton binding by construction."""
        return Answer(value=skeleton.binding[self.target_role], kind="node_id")

    def build_distractors(
        self, skeleton: CarveResult, world: WorldImpl, seed: Seed
    ) -> tuple[Answer, ...]:
        """Every other molecule id as a near-miss ``node_id`` distractor.

        Deterministic and distinct: the sorted molecule ids minus the target, each
        a real molecule (never a reaction). Non-empty whenever the world has more
        than one molecule.
        """
        target = skeleton.binding[self.target_role]
        others = [mid for mid in sorted(world.chemistry.molecules) if mid != target]
        return tuple(Answer(value=mid, kind="node_id") for mid in others)

    def grader_spec(self) -> GraderSpec:
        """Exact single-node grading."""
        return GraderSpec(kind="node_id")


def diagnose_perturbation(
    *,
    n_nodes: int = 4,
    archetype_id: str = "diagnose_perturbation",
) -> TaskArchetype:
    """Build a ``diagnose_perturbation`` archetype over an ``n_nodes`` network.

    The motif has a single molecule-gated role (``target`` / ``perturbed_node``)
    and no edges — the ground truth is a *generation choice* made by
    :func:`draft_diagnosis_world`, not a subgraph to carve. The archetype makes no
    world-validity demand (empty :class:`FeatureSet`); its recipe grades the named
    perturbed node exactly.

    This is framework machinery — a template parameterized by the network-size
    dial ``n_nodes``, not a hand-authored scenario.
    """
    if n_nodes < 1:
        raise ValueError(f"n_nodes must be >= 1, got {n_nodes}")

    role = RoleSlot(
        name=TARGET_ROLE, type_tag=PERTURBED_TAG, constraints=(_is_molecule,)
    )
    motif = Motif(roles=(role,), edges=())
    recipe = DiagnosePerturbationRecipe()

    return TaskArchetype(
        id=archetype_id,
        motif=motif,
        verb="diagnose",
        feature_reqs=FeatureSet(),
        recipe=recipe,
    )
