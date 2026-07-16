"""Subgraph carve / splice engine — pure graph embedding + minimal edits.

This module is domain-neutral. It treats a :class:`~alienbio.suite.types.ReactionNetwork`
as a generic bipartite graph reached only through ``neighbors``/``species``/``reactions``,
and a :class:`~alienbio.suite.types.Motif` as an abstract pattern graph. Role constraints
are opaque :data:`~alienbio.suite.types.Predicate` callables that are only *called*; a
role's ``type_tag`` and an edge's ``relation`` tag are opaque strings that are only
*copied onto* synthesized nodes, never interpreted.

Two operations:
- :func:`carve` — find a reuse-maximal, injective, predicate-gated embedding of a motif
  into a host, synthesizing the minimum number of new nodes when (and only when) a role
  has no working host candidate. Returns a :class:`~alienbio.suite.types.Skeleton` or a
  :class:`CarveFail`.
- :func:`splice` — deterministically reconstruct the host with a skeleton's edits applied
  (synthesized nodes created, motif edges realized, removed nodes dropped).

Bipartite-adjacency note: a host reaction connecting species ``a`` (reactant) to species
``b`` (product) does not make ``a`` a direct ``neighbors`` of ``b`` — the graph is
bipartite (species<->reaction only). ``carve`` and ``splice`` therefore share a single
:func:`_adjacent` predicate: two nodes are adjacent if they are direct bipartite
``neighbors`` OR a single reaction links them as reactant->product (either direction).
The reaction ``splice`` inserts to realize a motif edge makes exactly this predicate true.
"""

from __future__ import annotations

from dataclasses import dataclass

from .dist import Seed
from .types import (
    Motif,
    NodeId,
    Reaction,
    ReactionNetwork,
    Skeleton,
    Species,
)


@dataclass(frozen=True)
class CarveFail:
    """A carve that could not produce a valid embedding, with a reason."""

    reason: str


def _adjacent(net: ReactionNetwork, u: NodeId, v: NodeId) -> bool:
    """Whether ``u`` and ``v`` are connected in the bipartite host graph.

    True iff ``v`` is a direct bipartite ``neighbors`` of ``u`` (one is a species,
    the other a reaction referencing it) OR a single reaction links them as
    reactant->product in either direction (the connection ``splice`` synthesizes).
    """
    if v in net.neighbors(u):
        return True
    for rxn in net.reactions.values():
        r_ids = {n for n, _ in rxn.reactants}
        p_ids = {n for n, _ in rxn.products}
        if (u in r_ids and v in p_ids) or (v in r_ids and u in p_ids):
            return True
    return False


def carve(
    host: ReactionNetwork,
    motif: Motif,
    seed: Seed = Seed(0),
    allow_add: bool = True,
) -> Skeleton | CarveFail:
    """Embed ``motif`` into ``host``, reusing host nodes maximally.

    For each role, candidates are the existing host nodes passing every constraint
    predicate. A backtracking search finds an injective binding of all roles such
    that every motif edge holds between two existing-bound nodes (adjacency via
    :func:`_adjacent`); edges touching a synthesized node are deferred to
    :func:`splice`. The reuse-maximal binding (most roles bound to existing nodes,
    equivalently fewest synthesized) is chosen deterministically; ``seed`` only
    breaks ties among equal-quality embeddings.

    Returns a :class:`~alienbio.suite.types.Skeleton` (with ``added`` listing the
    synthesized node ids, sorted) or a :class:`CarveFail` when no embedding exists
    (e.g. a role has no candidate and ``allow_add`` is False).
    """
    node_objs: dict[NodeId, object] = {}
    for sid, sp in host.species.items():
        node_objs[sid] = sp
    for rid, rx in host.reactions.items():
        node_objs[rid] = rx

    cands: dict[str, list[NodeId]] = {}
    for role in motif.roles:
        cands[role.name] = sorted(
            nid
            for nid, obj in node_objs.items()
            if all(pred(obj) for pred in role.constraints)
        )

    role_names = [role.name for role in motif.roles]
    edges = motif.edges

    # Each collected solution: (reuse_count, canonical_key, binding, synth_roles).
    solutions: list[tuple[int, tuple[tuple[str, NodeId], ...], dict[str, NodeId], tuple[str, ...]]] = []

    def edge_ok(
        name: str,
        node_id: NodeId,
        is_synth: bool,
        assigned: dict[str, tuple[NodeId, bool]],
    ) -> bool:
        """Whether binding ``name`` to ``node_id`` keeps all satisfiable edges intact."""
        for a, b, _ in edges:
            if a == name:
                other = b
            elif b == name:
                other = a
            else:
                continue
            if other not in assigned:
                continue
            other_id, other_synth = assigned[other]
            if is_synth or other_synth:
                # Adjacency to a synthesized node is realized later by splice.
                continue
            if not _adjacent(host, node_id, other_id):
                return False
        return True

    def backtrack(
        i: int,
        assigned: dict[str, tuple[NodeId, bool]],
        used: set[NodeId],
    ) -> None:
        if i == len(role_names):
            reuse = sum(1 for _, synth in assigned.values() if not synth)
            binding = {name: nid for name, (nid, _) in assigned.items()}
            key = tuple(sorted(binding.items()))
            synth_roles = tuple(
                sorted(name for name, (_, synth) in assigned.items() if synth)
            )
            solutions.append((reuse, key, binding, synth_roles))
            return
        name = role_names[i]
        for nid in cands[name]:
            if nid in used:
                continue
            if edge_ok(name, nid, False, assigned):
                assigned[name] = (nid, False)
                used.add(nid)
                backtrack(i + 1, assigned, used)
                del assigned[name]
                used.discard(nid)
        if allow_add:
            synth_id = f"{name}#new"
            if edge_ok(name, synth_id, True, assigned):
                assigned[name] = (synth_id, True)
                backtrack(i + 1, assigned, used)
                del assigned[name]

    backtrack(0, {}, set())

    if not solutions:
        unbindable = [role.name for role in motif.roles if not cands[role.name]]
        if not allow_add and unbindable:
            return CarveFail(
                reason=f"roles have no host candidate and allow_add=False: {unbindable}"
            )
        return CarveFail(
            reason="no injective embedding satisfies the motif edges"
        )

    max_reuse = max(sol[0] for sol in solutions)
    top = sorted(
        (sol for sol in solutions if sol[0] == max_reuse),
        key=lambda sol: sol[1],
    )
    chosen = top[seed.value % len(top)]
    binding = chosen[2]
    synth_roles = chosen[3]
    added = tuple(sorted(f"{name}#new" for name in synth_roles))
    return Skeleton(motif=motif, binding=binding, added=added, removed=())


def splice(host: ReactionNetwork, skeleton: Skeleton) -> ReactionNetwork:
    """Return a new host with ``skeleton``'s edits applied (deterministic).

    Creates each synthesized node (a :class:`~alienbio.suite.types.Species` tagged
    with the ``type_tag`` of the role bound to it), realizes every motif edge by
    inserting a neutral reactant->product reaction when the two bound nodes are not
    already adjacent, and drops every removed node (stripping it from all reaction
    reactant/product/modifier lists). The output is a pure function of
    ``(host, skeleton)``.
    """
    species: dict[NodeId, Species] = dict(host.species)
    reactions: dict[NodeId, Reaction] = dict(host.reactions)
    binding = skeleton.binding
    motif = skeleton.motif
    role_by_name = {role.name: role for role in motif.roles}

    for nid in skeleton.added:
        tag = ""
        for name, bound_id in binding.items():
            if bound_id == nid:
                tag = role_by_name[name].type_tag
                break
        if nid not in species and nid not in reactions:
            species[nid] = Species(id=nid, attrs={"type": tag})

    for a, b, _ in motif.edges:
        u = binding[a]
        v = binding[b]
        current = ReactionNetwork(species=species, reactions=reactions)
        if not _adjacent(current, u, v):
            rxn_id = f"rxn::{u}->{v}"
            reactions[rxn_id] = Reaction(
                id=rxn_id,
                reactants=((u, 1),),
                products=((v, 1),),
                modifiers=(),
            )

    for nid in skeleton.removed:
        species.pop(nid, None)
        reactions.pop(nid, None)
        for rid in list(reactions.keys()):
            rxn = reactions[rid]
            reactions[rid] = Reaction(
                id=rxn.id,
                reactants=tuple((n, s) for n, s in rxn.reactants if n != nid),
                products=tuple((n, s) for n, s in rxn.products if n != nid),
                modifiers=tuple((n, r) for n, r in rxn.modifiers if n != nid),
                rate=rxn.rate,
            )

    return ReactionNetwork(species=species, reactions=reactions)
