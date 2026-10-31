"""M27.1 — the task-archetype catalog (mechanism-discovery family).

An archetype is a *reusable, parameterized, domain-neutral* task template
(`TaskArchetype`): a motif (the structure the world must contain), a verb (the
FT08 question framing), and an `ObjectiveRecipe` (how the task is questioned and graded). This module ships the
first, ``identify_pathway`` — the template for the rest — per the M27 design
(``ABIO Semantic Layer`` § M27.1).

The recipe is **skeleton-first**: because the pipeline carves the motif into the
world and *then* asks the question, the ground-truth key is read off the carved
:class:`CarveResult` by construction — we hold the answer because we built the
structure. The engines only ever *invoke* a recipe; they never inspect it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .types import (
    Answer,
    GraderSpec,
    Motif,
    CarveResult,
    Predicate,
    Question,
    RoleSlot,
    TaskArchetype,
)

if TYPE_CHECKING:
    from ..bio.world import WorldImpl

#: The opaque edge tag used to chain successive pathway roles.
REACTS_TO = "reacts_to"


def _is_molecule(node: object) -> bool:
    """Carve node-object predicate admitting molecule nodes only.

    In the bipartite host graph a role could otherwise bind to a *reaction*
    node (they are graph-adjacent to their substrates), corrupting the pathway
    key with a non-molecule id. Reaction nodes expose ``reactants``; molecules
    do not — so this excludes them without the archetype layer importing the
    concrete impl class.
    """
    return not hasattr(node, "reactants")


#: The shortest chain an identify question can ask about (T091 AF3): the
#: question states both endpoints, so at two nodes it states the whole key.
MIN_PATHWAY_LENGTH = 3


def _successors(world: "WorldImpl") -> dict[str, set[str]]:
    """Each world node's directed successors, as :func:`~alienbio.suite.carve.splice`
    realizes an edge: a molecule leads to every reaction taking it as reactant
    and to every molecule such a reaction produces; a reaction leads to its
    products."""
    succ: dict[str, set[str]] = {}
    for rxn in world.chemistry.reactions.values():
        products = {m.name for m in rxn.products}
        succ.setdefault(rxn.name, set()).update(products)
        for a in rxn.reactants:
            succ.setdefault(a.name, set()).update(products | {rxn.name})
    return succ


def check_pathway_key(path: list[str], world: "WorldImpl") -> None:
    """Refuse a pathway key the world does not carry (T091 AF1, AF5).

    Every node must be a node of the world — a node a carve synthesized
    (``r2#new``) is not, nor is a hand ``binding`` naming an id the world
    lacks; each step must run the chemistry's way (molecule to molecule
    through a reaction, molecule to a reaction consuming it, reaction to its
    product), so the end is reached and is no inert distractor; and the route
    must be the ONLY one between the endpoints the question states with the
    same length and the same molecule/reaction shape — a second true route
    would score 0.
    """
    chem = world.chemistry
    molecules = {m.name for m in chem.molecules.values()}
    reactions = {r.name for r in chem.reactions.values()}
    absent = [node for node in path if node not in molecules | reactions]
    if absent:
        raise ValueError(
            f"identify: key {path} names {absent}, not nodes of the world "
            "(a carve that synthesized a node — carve with allow_add: False — or a "
            "binding naming an id the world lacks)"
        )
    succ = _successors(world)
    for a, b in zip(path, path[1:]):
        if b not in succ.get(a, ()):
            raise ValueError(
                f"identify: key {path} steps {a} -> {b}, which the world's reactions do "
                "not run that way; the key is not a route of the world"
            )
    shape = [node in molecules for node in path]
    end = path[-1]
    other: list[str] = []

    def walk(route: list[str]) -> bool:
        i = len(route)
        if i == len(path):
            if route[-1] == end and route != path:
                other.extend(route)
                return True
            return False
        for nxt in sorted(succ.get(route[-1], ())):
            if nxt in route or (nxt in molecules) != shape[i] or (nxt == end) != (i == len(path) - 1):
                continue
            route.append(nxt)
            if walk(route):
                return True
            route.pop()
        return False

    if walk([path[0]]):
        raise ValueError(
            f"identify: the key is not unique — {path} and {other} both run "
            f"{path[0]} -> {end} in {len(path)} nodes; the question would mark a "
            "true route wrong"
        )


@dataclass(frozen=True)
class IdentifyPathwayRecipe:
    """Recipe for ``identify_pathway``: recover a hidden linear chain.

    Holds the ordered role names of the chain (``r0 … r_{n-1}``); every method
    reads the concrete answer off the carved ``CarveResult.binding`` — which maps
    each role name to the host node it was bound to — so the key is correct by
    construction. Question kind and answer kind are both ``ordered_path``: the
    question renders the chain's *endpoints*, the answer the *full ordered chain*.
    The chain is at least :data:`MIN_PATHWAY_LENGTH` roles long, and the bound
    chain must be the world's one route of that length between its endpoints
    (:func:`check_pathway_key`) — both refused otherwise.
    """

    role_names: tuple[str, ...]
    verb: str = "identify"

    def __post_init__(self) -> None:
        if len(self.role_names) < MIN_PATHWAY_LENGTH:
            raise ValueError(
                f"identify: a pathway needs at least {MIN_PATHWAY_LENGTH} roles, got "
                f"{len(self.role_names)} — the question states both endpoints, so a "
                "shorter chain's question would state the whole key"
            )

    def _path(self, skeleton: CarveResult, world: "WorldImpl") -> list[str]:
        """The ordered host-node chain the carve bound this motif's roles to,
        checked against ``world`` (:func:`check_pathway_key`)."""
        path = [skeleton.binding[name] for name in self.role_names]
        check_pathway_key(path, world)
        return path

    def build_question(self, skeleton: CarveResult, world: "WorldImpl") -> Question:
        """The chain's endpoints (start, end) as an ``ordered_path`` question."""
        path = self._path(skeleton, world)
        endpoints = [path[0], path[-1]]
        return Question(structured=endpoints, kind="ordered_path")

    def build_key(self, skeleton: CarveResult, world: "WorldImpl") -> Answer:
        """The full ordered chain — read off the skeleton by construction."""
        return Answer(value=self._path(skeleton, world), kind="ordered_path")

    def grader_spec(self) -> GraderSpec:
        """Order-sensitive path grading with longest-common-prefix partial
        credit over the interior: the start and end nodes the question states
        earn none (T088 the start; T091 AF11 the end — appending it doubled
        ``[s, m]``'s credit at three nodes)."""
        return GraderSpec(
            kind="ordered_path", config={"partial": True, "given_prefix": 1, "given_suffix": 1}
        )


def identify_pathway(
    pathway_length: int,
    *,
    constraints: tuple[Predicate, ...] = (),
    archetype_id: str = "identify_pathway",
) -> TaskArchetype:
    """Build a generic ``identify_pathway`` archetype over a chain of ``pathway_length`` nodes.

    The motif is a linear chain ``r0 -reacts_to-> r1 -reacts_to-> … -> r_{n-1}``
    (``n = pathway_length``, which must be ≥ :data:`MIN_PATHWAY_LENGTH`); every role carries the same
    opaque ``constraints`` (empty by default — the generic template makes no
    domain demand; realness constraints are layered in by callers/M27.3). The
    recipe grades the recovered ordered chain.

    This is framework machinery — a template parameterized by a dial
    (``pathway_length``), not a hand-tuned scenario.
    """
    if pathway_length < MIN_PATHWAY_LENGTH:
        raise ValueError(
            f"pathway_length must be >= {MIN_PATHWAY_LENGTH}, got {pathway_length} — the "
            "question states both endpoints, so a shorter chain's question states the whole key"
        )

    role_names = tuple(f"r{i}" for i in range(pathway_length))
    # Pathway nodes are molecules — prepend the molecule gate so carve never
    # binds a role to a reaction node (which would corrupt the ground-truth key).
    role_constraints = (_is_molecule,) + constraints
    roles = tuple(
        RoleSlot(name=name, type_tag="pathway_node", constraints=role_constraints)
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
        recipe=recipe,
    )
