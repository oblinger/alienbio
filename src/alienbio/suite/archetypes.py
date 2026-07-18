"""M27.1 — the task-archetype catalog (mechanism-discovery family).

An archetype is a *reusable, parameterized, domain-neutral* task template
(`TaskArchetype`): a motif (the structure the world must contain), a verb (the
FT08 question framing), feature requirements (the world-validity demand), and an
`ObjectiveRecipe` (how the task is questioned and graded). This module ships the
first, ``identify_pathway`` — the template for the rest — per the M27 design
(``ABIO Semantic Layer`` § M27.1).

The recipe is **skeleton-first**: because the pipeline carves the motif into the
world and *then* asks the question, the ground-truth key is read off the carved
:class:`Skeleton` by construction — we hold the answer because we built the
structure. The engines only ever *invoke* a recipe; they never inspect it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .dist import Seed
from .types import (
    Answer,
    FeatureSet,
    GraderSpec,
    Motif,
    Predicate,
    Question,
    RoleSlot,
    Skeleton,
    TaskArchetype,
)

if TYPE_CHECKING:
    from ..bio.world import WorldImpl

#: The opaque edge tag used to chain successive pathway roles.
REACTS_TO = "reacts_to"


@dataclass(frozen=True)
class IdentifyPathwayRecipe:
    """Recipe for ``identify_pathway``: recover a hidden linear chain.

    Holds the ordered role names of the chain (``r0 … r_{n-1}``); every method
    reads the concrete answer off the carved ``Skeleton.binding`` — which maps
    each role name to the host node it was bound to — so the key is correct by
    construction. Question kind and answer kind are both ``ordered_path``: the
    question renders the chain's *endpoints*, the answer the *full ordered chain*.
    """

    role_names: tuple[str, ...]
    verb: str = "identify"

    def _path(self, skeleton: Skeleton) -> list[str]:
        """The ordered host-node chain the carve bound this motif's roles to."""
        return [skeleton.binding[name] for name in self.role_names]

    def build_question(self, skeleton: Skeleton, world: "WorldImpl") -> Question:
        """The chain's endpoints (start, end) as an ``ordered_path`` question."""
        path = self._path(skeleton)
        endpoints = [path[0], path[-1]]
        return Question(structured=endpoints, kind="ordered_path")

    def build_key(self, skeleton: Skeleton, world: "WorldImpl") -> Answer:
        """The full ordered chain — read off the skeleton by construction."""
        return Answer(value=self._path(skeleton), kind="ordered_path")

    def build_distractors(
        self, skeleton: Skeleton, world: "WorldImpl", seed: Seed
    ) -> tuple[Answer, ...]:
        """Plausible near-miss paths: an interior swap and the reversed chain.

        Deterministic in ``seed``; every distractor differs from the key and
        stays within the chain's own node set (a same-length permutation), so it
        is a genuine near-miss rather than an obviously-wrong answer.
        """
        path = self._path(skeleton)
        n = len(path)
        distractors: list[Answer] = []
        seen = {tuple(path)}

        # An interior adjacent swap (needs ≥ 3 nodes to leave the endpoints fixed).
        if n >= 3:
            i = 1 + (seed.value % (n - 2))
            j = i + 1 if i + 1 < n - 1 else i - 1
            swapped = list(path)
            swapped[i], swapped[j] = swapped[j], swapped[i]
            if tuple(swapped) not in seen:
                distractors.append(Answer(value=swapped, kind="ordered_path"))
                seen.add(tuple(swapped))

        # The reversed chain (a whole-path permutation).
        reversed_path = list(reversed(path))
        if tuple(reversed_path) not in seen:
            distractors.append(Answer(value=reversed_path, kind="ordered_path"))
            seen.add(tuple(reversed_path))

        return tuple(distractors)

    def grader_spec(self) -> GraderSpec:
        """Order-sensitive path grading with longest-common-prefix partial credit."""
        return GraderSpec(kind="ordered_path", config={"partial": True})


def identify_pathway(
    pathway_length: int,
    *,
    constraints: tuple[Predicate, ...] = (),
    archetype_id: str = "identify_pathway",
) -> TaskArchetype:
    """Build a generic ``identify_pathway`` archetype over a chain of ``pathway_length`` nodes.

    The motif is a linear chain ``r0 -reacts_to-> r1 -reacts_to-> … -> r_{n-1}``
    (``n = pathway_length``, which must be ≥ 2); every role carries the same
    opaque ``constraints`` (empty by default — the generic template makes no
    domain demand; realness constraints are layered in by callers/M27.3). The
    recipe grades the recovered ordered chain.

    This is framework machinery — a template parameterized by a dial
    (``pathway_length``), not a hand-tuned scenario.
    """
    if pathway_length < 2:
        raise ValueError(f"pathway_length must be >= 2, got {pathway_length}")

    role_names = tuple(f"r{i}" for i in range(pathway_length))
    roles = tuple(
        RoleSlot(name=name, type_tag="pathway_node", constraints=constraints)
        for name in role_names
    )
    edges = tuple(
        (role_names[i], role_names[i + 1], REACTS_TO)
        for i in range(pathway_length - 1)
    )
    motif = Motif(roles=roles, edges=edges)
    recipe = IdentifyPathwayRecipe(role_names=role_names)

    return TaskArchetype(
        id=archetype_id,
        motif=motif,
        verb="identify",
        feature_reqs=FeatureSet(),
        recipe=recipe,
    )
