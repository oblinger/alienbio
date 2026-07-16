"""Neutral bipartite-graph algorithms shared by the reaction-network views.

This is the **single source of truth** for the four graph queries the biology
``Chemistry`` container exposes: ``neighbors`` / ``paths`` / ``subgraph`` /
``match`` (originally shared with the now-retired neutral ``ReactionNetwork``
shadow type). Each caller adapts its own representation into a
:class:`GraphView` (ordered species + reaction ids, plus a per-reaction
incidence set and a per-species opaque comparison key) and delegates here; the
algorithm never inspects domain objects.

The bipartite model: species nodes and reaction nodes live in one id namespace;
a reaction is adjacent to every species it touches (reactants, products, or
modifiers, unioned into :attr:`GraphView.incidence`). Ordering of
:attr:`GraphView.species_ids` / :attr:`GraphView.reaction_ids` is preserved
(source dict order) so that :func:`match` and :func:`paths` produce identical,
deterministic result sequences regardless of caller.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

NodeId = str


@dataclass(frozen=True)
class GraphView:
    """An ordered, id-only view of a bipartite species<->reaction network.

    - ``species_ids`` / ``reaction_ids`` — the two node namespaces, in source
      order (dict-insertion order at the caller). Order is load-bearing:
      :func:`match` and :func:`paths` enumerate in this order.
    - ``incidence`` — ``reaction_id -> frozenset`` of every species id the
      reaction touches (reactants ∪ products ∪ modifiers).
    - ``species_key`` — ``species_id -> opaque comparable`` used only by
      :func:`match` for candidate tag-equality; compared with ``==`` and never
      otherwise inspected (a dict of attrs, a tuple of props — caller's choice,
      as long as it is internally consistent).
    """

    species_ids: tuple[NodeId, ...]
    reaction_ids: tuple[NodeId, ...]
    incidence: Mapping[NodeId, frozenset[NodeId]]
    species_key: Mapping[NodeId, Any] = field(default_factory=dict)

    # Membership sets (derived; order-independent lookups).
    _species_set: frozenset[NodeId] = field(init=False, repr=False, compare=False)
    _reaction_set: frozenset[NodeId] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_species_set", frozenset(self.species_ids))
        object.__setattr__(self, "_reaction_set", frozenset(self.reaction_ids))


def neighbors(view: GraphView, node: NodeId) -> set[NodeId]:
    """Species<->reaction adjacency (bipartite).

    Mirrors the union-of-both-branches semantics: if ``node`` is a species,
    every reaction incident on it; if ``node`` is a reaction, every species it
    touches. (A node in neither namespace yields the empty set.)
    """
    result: set[NodeId] = set()
    if node in view._species_set:
        for rid in view.reaction_ids:
            if node in view.incidence.get(rid, frozenset()):
                result.add(rid)
    if node in view._reaction_set:
        result |= set(view.incidence.get(node, frozenset()))
    return result


def paths(
    view: GraphView, a: NodeId, b: NodeId, max_len: int = 8
) -> list[list[NodeId]]:
    """All simple paths from ``a`` to ``b`` with at most ``max_len`` edges."""
    if a == b:
        return [[a]]
    results: list[list[NodeId]] = []

    def dfs(cur: NodeId, path: list[NodeId], visited: set[NodeId]) -> None:
        if len(path) - 1 >= max_len:
            return
        for nb in sorted(neighbors(view, cur)):
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


def subgraph_selection(
    view: GraphView, nodes: Iterable[NodeId]
) -> tuple[tuple[NodeId, ...], tuple[NodeId, ...]]:
    """The induced-subgraph node selection over ``nodes``, in source order.

    Returns ``(kept_species_ids, kept_reaction_ids)`` — the species and reactions
    that survive (i.e. whose id is in ``nodes``), preserving the view's ordering.
    Callers reconstruct their own concrete type, filtering each kept reaction's
    endpoint list to the kept-node set (edges to dropped nodes are removed).
    """
    node_set = set(nodes)
    kept_species = tuple(sid for sid in view.species_ids if sid in node_set)
    kept_reactions = tuple(rid for rid in view.reaction_ids if rid in node_set)
    return kept_species, kept_reactions


def edge_set(view: GraphView) -> set[frozenset[NodeId]]:
    """The undirected edge set (each edge an unordered ``{u, v}`` pair)."""
    edges: set[frozenset[NodeId]] = set()
    for nid in list(view.species_ids) + list(view.reaction_ids):
        for nb in neighbors(view, nid):
            edges.add(frozenset((nid, nb)))
    return edges


def match(view: GraphView, pattern: GraphView) -> list[dict[NodeId, NodeId]]:
    """All subgraph embeddings of ``pattern`` into ``view``.

    Preserves node type (species<->species, reaction<->reaction), species
    ``species_key`` equality, injectivity, and every pattern edge (a host edge
    must exist between the mapped nodes). Reactions match structurally (no key).
    Returns every embedding as ``{pattern_node: host_node}``; ``[]`` if none.
    Enumeration order follows the pattern's node ordering.
    """
    p_nodes = list(pattern.species_ids) + list(pattern.reaction_ids)

    def candidates(pn: NodeId) -> list[NodeId]:
        if pn in pattern._species_set:
            pkey = pattern.species_key.get(pn)
            return [
                hid
                for hid in view.species_ids
                if view.species_key.get(hid) == pkey
            ]
        return list(view.reaction_ids)

    cand_map = {pn: candidates(pn) for pn in p_nodes}
    p_edges = edge_set(pattern)
    host_edges = edge_set(view)
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
