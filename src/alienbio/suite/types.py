"""Neutral, immutable value types for the ``suite`` subsystem (L0-L6).

This module is a **generic reaction-network / graph library**. It carries NO
domain logic: every piece of domain meaning is an opaque :data:`Tags` mapping
(``dict[str, str | float]``) that this code never inspects or branches on.
Likewise :data:`RateSpec` (a float or an opaque callable) is stored as-is and
never evaluated; round-trips preserve object identity.

All value types are ``@dataclass(frozen=True)`` — collections are stored as
tuples or immutable mappings, and nothing mutates after construction.

Layers:
- L0: primitive aliases (:data:`NodeId`, :data:`Tags`).
- L1: neutral bipartite reaction network (:class:`Species`, :class:`Reaction`,
  :class:`ReactionNetwork`).
- L2: world / physics / state (:class:`Compartment`, :class:`Topology`,
  :class:`StateVector`, :class:`Trace`, :class:`World`).
- L3: motif (abstract) vs skeleton (concrete binding).
- L4: dynamism seam (:class:`Op`, :class:`ScriptedOp`) + covering / envelopes.
- L5: question / objective / answer.
- L6: distributions everywhere, vector difficulty, worlds-as-input.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import (
    Any,
    Callable,
    Generic,
    Iterable,
    Mapping,
    Optional,
    Protocol,
    TypeVar,
    Union,
    runtime_checkable,
)

import numpy as np
import numpy.typing as npt

from .dist import Dist, ParamSchema

T = TypeVar("T")
T_co = TypeVar("T_co", covariant=True)

# ═══════════════════════════════════════════════════════════════════════════
# L0 — primitives
# ═══════════════════════════════════════════════════════════════════════════

NodeId = str
Tags = dict[str, Union[str, float]]

# A predicate is an opaque callable over a Species/Reaction — only ever called,
# never inspected.
Predicate = Callable[[Any], bool]

# A 2D float array [n_compartments x n_species].
FloatArray = npt.NDArray[np.float64]


# ═══════════════════════════════════════════════════════════════════════════
# L1 — neutral bipartite reaction network
# ═══════════════════════════════════════════════════════════════════════════

# Opaque rate: exactly the existing Reaction.rate type. Stored as-is, never
# evaluated or interpreted.
RateSpec = Union[float, Callable]


@dataclass(frozen=True)
class Species:
    """A network node carrying opaque tag data."""

    id: NodeId
    attrs: Tags = field(default_factory=dict)


@dataclass(frozen=True)
class Reaction:
    """A bipartite reaction node: reactants, products, modifiers, opaque rate.

    ``reactants``/``products`` are ``(node_id, stoichiometry)`` pairs;
    ``modifiers`` are ``(node_id, role_tag)`` pairs (may be empty). ``rate`` is
    an opaque :data:`RateSpec` stored verbatim.
    """

    id: NodeId
    reactants: tuple[tuple[NodeId, int], ...] = ()
    products: tuple[tuple[NodeId, int], ...] = ()
    modifiers: tuple[tuple[NodeId, str], ...] = ()
    rate: RateSpec = 1.0


@dataclass(frozen=True)
class ReactionNetwork:
    """An immutable bipartite species<->reaction network with graph queries."""

    species: Mapping[NodeId, Species]
    reactions: Mapping[NodeId, Reaction]

    def __post_init__(self) -> None:
        # Freeze the mappings so nothing mutates after construction.
        object.__setattr__(self, "species", MappingProxyType(dict(self.species)))
        object.__setattr__(self, "reactions", MappingProxyType(dict(self.reactions)))

    def neighbors(self, node: NodeId) -> set[NodeId]:
        """Species<->reaction adjacency (bipartite)."""
        result: set[NodeId] = set()
        if node in self.species:
            for rid, rxn in self.reactions.items():
                if any(n == node for n, _ in rxn.reactants) or any(
                    n == node for n, _ in rxn.products
                ) or any(n == node for n, _ in rxn.modifiers):
                    result.add(rid)
        if node in self.reactions:
            rxn = self.reactions[node]
            for n, _ in rxn.reactants:
                result.add(n)
            for n, _ in rxn.products:
                result.add(n)
            for n, _ in rxn.modifiers:
                result.add(n)
        return result

    def paths(self, a: NodeId, b: NodeId, max_len: int = 8) -> list[list[NodeId]]:
        """All simple paths from ``a`` to ``b`` with at most ``max_len`` edges."""
        if a == b:
            return [[a]]
        results: list[list[NodeId]] = []

        def dfs(cur: NodeId, path: list[NodeId], visited: set[NodeId]) -> None:
            if len(path) - 1 >= max_len:
                return
            for nb in sorted(self.neighbors(cur)):
                if nb in visited:
                    continue
                if nb == b:
                    results.append(path + [nb])
                    continue
                visited.add(nb)
                dfs(nb, path + [nb], visited)
                visited.discard(nb)

        dfs(a, [a], {a})
        return results

    def subgraph(self, nodes: Iterable[NodeId]) -> "ReactionNetwork":
        """The induced subgraph over ``nodes`` (edges to dropped nodes removed)."""
        node_set = set(nodes)
        new_species = {
            sid: sp for sid, sp in self.species.items() if sid in node_set
        }
        new_reactions: dict[NodeId, Reaction] = {}
        for rid, rxn in self.reactions.items():
            if rid not in node_set:
                continue
            new_reactions[rid] = Reaction(
                id=rxn.id,
                reactants=tuple((n, s) for n, s in rxn.reactants if n in node_set),
                products=tuple((n, s) for n, s in rxn.products if n in node_set),
                modifiers=tuple((n, r) for n, r in rxn.modifiers if n in node_set),
                rate=rxn.rate,
            )
        return ReactionNetwork(species=new_species, reactions=new_reactions)

    def _edge_set(self) -> set[frozenset[NodeId]]:
        edges: set[frozenset[NodeId]] = set()
        for nid in list(self.species.keys()) + list(self.reactions.keys()):
            for nb in self.neighbors(nid):
                edges.add(frozenset((nid, nb)))
        return edges

    def match(self, pattern: "ReactionNetwork") -> list[dict[NodeId, NodeId]]:
        """All subgraph embeddings of ``pattern`` into ``self``.

        Matching preserves node type (species<->species, reaction<->reaction),
        tag-equality on species ``attrs``, injectivity, and every pattern edge
        (a host edge must exist between the mapped nodes). Reactions match
        structurally (their rate is opaque and not compared). Returns every
        embedding as ``{pattern_node: host_node}``; ``[]`` if none.
        """
        p_nodes = list(pattern.species.keys()) + list(pattern.reactions.keys())

        def candidates(pn: NodeId) -> list[NodeId]:
            if pn in pattern.species:
                pattr = pattern.species[pn].attrs
                return [hid for hid, sp in self.species.items() if sp.attrs == pattr]
            return list(self.reactions.keys())

        cand_map = {pn: candidates(pn) for pn in p_nodes}
        p_edges = pattern._edge_set()
        host_edges = self._edge_set()
        results: list[dict[NodeId, NodeId]] = []

        def backtrack(i: int, mapping: dict[NodeId, NodeId], used: set[NodeId]) -> None:
            if i == len(p_nodes):
                results.append(dict(mapping))
                return
            pn = p_nodes[i]
            for hn in cand_map[pn]:
                if hn in used:
                    continue
                ok = True
                for edge in p_edges:
                    if pn not in edge:
                        continue
                    other = next(iter(edge - {pn}))
                    if other in mapping and frozenset((hn, mapping[other])) not in host_edges:
                        ok = False
                        break
                if not ok:
                    continue
                mapping[pn] = hn
                used.add(hn)
                backtrack(i + 1, mapping, used)
                del mapping[pn]
                used.discard(hn)

        backtrack(0, {}, set())
        return results


# ═══════════════════════════════════════════════════════════════════════════
# L2 — world (physics / space / state)
# ═══════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class Compartment:
    """A node in the compartment tree; the root has ``parent = None``."""

    id: NodeId
    parent: Optional[NodeId]
    kind: str
    volume: float


@dataclass(frozen=True)
class Topology:
    """A compartment tree (a tuple of compartments; root has no parent)."""

    compartments: tuple[Compartment, ...]


@dataclass(frozen=True, eq=False)
class StateVector:
    """A [n_compartments x n_species] float array with id-labelled axes.

    ``__eq__`` compares array *values* (not identity) along with the axis
    labels; ``__hash__`` falls back to identity.
    """

    data: FloatArray
    compartments: tuple[NodeId, ...]
    species: tuple[NodeId, ...]

    def get(self, comp_id: NodeId, species_id: NodeId) -> float:
        ci = self.compartments.index(comp_id)
        si = self.species.index(species_id)
        return float(self.data[ci, si])

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, StateVector):
            return NotImplemented
        return (
            self.compartments == other.compartments
            and self.species == other.species
            and np.array_equal(self.data, other.data)
        )

    def __hash__(self) -> int:
        return object.__hash__(self)


@dataclass(frozen=True)
class Trace:
    """A time-ordered sequence of states."""

    times: tuple[float, ...]
    states: tuple[StateVector, ...]


@dataclass(frozen=True)
class World:
    """A network + topology + initial state."""

    network: ReactionNetwork
    topology: Topology
    initial: StateVector


# ═══════════════════════════════════════════════════════════════════════════
# L3 — motif (abstract) vs skeleton (concrete binding)
# ═══════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class RoleSlot:
    """An abstract role: a name, a type tag, and opaque constraint predicates."""

    name: str
    type_tag: str
    constraints: tuple[Predicate, ...] = ()


@dataclass(frozen=True)
class Motif:
    """An abstract subgraph pattern: roles + tagged edges + opaque params."""

    roles: tuple[RoleSlot, ...]
    edges: tuple[tuple[str, str, str], ...]
    params: Tags = field(default_factory=dict)


@dataclass(frozen=True)
class Skeleton:
    """A concrete binding of a motif's roles to host nodes, plus edits."""

    motif: Motif
    binding: Mapping[str, NodeId]
    added: tuple[NodeId, ...] = ()
    removed: tuple[NodeId, ...] = ()


# ═══════════════════════════════════════════════════════════════════════════
# L4 — dynamism seam + covering / envelopes
# ═══════════════════════════════════════════════════════════════════════════

Directive = str


@runtime_checkable
class Op(Protocol[T_co]):
    """An opaque callable operation over a context."""

    def __call__(self, context: Any) -> T_co: ...


@dataclass(frozen=True)
class ScriptedOp(Generic[T]):
    """An :class:`Op` backed by a Python callable."""

    fn: Callable[[Any], T]

    def __call__(self, context: Any) -> T:
        return self.fn(context)


@dataclass(frozen=True)
class FeatureSet:
    """A set of named predicates a world must satisfy."""

    features: frozenset[tuple[str, Predicate]] = frozenset()


@dataclass(frozen=True)
class WorldEnvelope:
    """A parameter schema, required features, and an optional directive."""

    params: ParamSchema
    must_satisfy: FeatureSet
    directive: Optional[Directive] = None


# ═══════════════════════════════════════════════════════════════════════════
# L5 — question / objective / answer
# ═══════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class Answer:
    """An opaque JSON-ish value tagged by ``kind``.

    ``kind`` in {node_set, ordered_path, node_id, scalar, json}.
    """

    value: Any
    kind: str


@runtime_checkable
class Renderable(Protocol):
    """Something that can render itself to text given a vocabulary."""

    def render(self, vocabulary: Any) -> str: ...


@dataclass(frozen=True)
class Question:
    """A structured, opaque JSON-ish question tagged by ``kind``."""

    structured: Any
    kind: str


@dataclass(frozen=True)
class GraderSpec:
    """Grader configuration (tolerance / partial-credit knobs as tags)."""

    kind: str
    config: Tags = field(default_factory=dict)


@dataclass(frozen=True)
class AnswerObjective:
    """Grade a submitted answer against a key with a grader."""

    grader: GraderSpec
    key: Answer


@dataclass(frozen=True)
class OutcomeObjective:
    """Score an outcome against a target with an opaque scorer."""

    scorer: Callable
    target: Any


Objective = Union[AnswerObjective, OutcomeObjective]


# ═══════════════════════════════════════════════════════════════════════════
# L6 — distributions everywhere, vector difficulty, worlds-as-input
# ═══════════════════════════════════════════════════════════════════════════

# Difficulty is a VECTOR: dimension name -> value.
Difficulty = dict[str, float]


@dataclass(frozen=True)
class TaskArchetype:
    """A reusable task template: motif + verb + feature requirements + recipe."""

    id: str
    motif: Motif
    verb: str
    feature_reqs: FeatureSet
    recipe: Any


@dataclass(frozen=True)
class TaskInstance:
    """A concrete task: archetype + world + skeleton + objective + question."""

    archetype: str
    world: str
    skeleton: Skeleton
    objective: Objective
    question: Question
    setup: Any


@dataclass(frozen=True)
class SuiteSpec:
    """A generative spec: archetype mix + per-archetype schemas + seed."""

    archetype_mix: "Dist[TaskArchetype]"
    per_archetype: Mapping[str, tuple[ParamSchema, "Dist[Difficulty]"]]
    seed: int


@dataclass(frozen=True)
class Suite:
    """A materialized suite: worlds + task instances."""

    worlds: tuple[World, ...]
    tasks: tuple[TaskInstance, ...]
