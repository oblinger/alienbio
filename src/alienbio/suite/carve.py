"""Subgraph carve / splice engine — pure graph embedding + minimal edits.

This module is domain-neutral in its *algorithm*: it treats a
:class:`~alienbio.bio.chemistry.ChemistryImpl` as a generic bipartite graph of
molecules (species nodes) and reactions (reaction nodes), reached only through
``neighbors`` / ``molecules`` / ``reactions`` (all keyed by ``name``), and a
:class:`~alienbio.suite.types.Motif` as an abstract pattern graph. Role
constraints are opaque :data:`~alienbio.suite.types.Predicate` callables that are
only *called* on the bound node object (a ``MoleculeImpl`` or ``ReactionImpl``); a
role's ``type_tag`` and an edge's ``relation`` tag are opaque strings that are only
*copied onto* synthesized nodes, never interpreted — except the two tags
``molecule`` / ``reaction``, which gate a role to that node kind (T091 AM4).

F007 note: the engine was retargeted off the neutral ``ReactionNetwork`` shadow onto
the biology ``Chemistry`` (unified protocol model — one data model everywhere). It
builds ``Chemistry`` objects as its working representation ("this is generation time,
not simulation time").

F008 note: the biology ``Reaction`` now carries a first-class ``modifiers`` edge kind
(a catalyst/regulator acting on a reaction without being stoichiometrically consumed).
:func:`splice` realizes a motif edge whose ``relation`` names a catalytic role
(:data:`_MODIFIER_RELATIONS`) as a **modifier** attachment on the reaction, and every
reaction reconstruction preserves the reaction's existing ``modifiers``. All other
molecule<->reaction edges still realize as reactant/product incidence.

Two operations:
- :func:`carve` — find a reuse-maximal, injective, predicate-gated embedding of a motif
  into a host, synthesizing the minimum number of new nodes when (and only when) a role
  has no working host candidate. Returns a :class:`~alienbio.suite.types.CarveResult` or a
  :class:`CarveFail`.
- :func:`splice` — deterministically reconstruct the host with a skeleton's edits applied
  (synthesized nodes created, motif edges realized, removed nodes dropped).

Bipartite-adjacency note: a host reaction connecting molecule ``a`` (reactant) to
molecule ``b`` (product) does not make ``a`` a direct ``neighbors`` of ``b`` — the graph
is bipartite (molecule<->reaction only). ``carve`` and ``splice`` therefore share a single
:func:`_edge_holds` predicate, and every case of it is DIRECTED the way ``splice``
builds the edge: a molecule->molecule edge holds when one reaction takes the first
as reactant and gives the second as product; ``mol -> rxn`` holds when the molecule
is a reactant, ``rxn -> mol`` when it is a product; a catalytic relation holds on a
modifier. The edge ``splice`` inserts to realize a motif edge makes exactly this
predicate true, so carve never binds a role against the chemistry's direction.

Search size: :func:`carve` collects every embedding at the best reuse before it
picks one, and refuses once more than :data:`MAX_EMBEDDINGS` are in hand.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from ..bio.chemistry import ChemistryImpl, _mock_dat
from ..bio.molecule import MoleculeImpl
from ..bio.reaction import ReactionImpl, rebuild_reaction
from .dist import Seed
from .types import (
    CarveResult,
    Motif,
    NodeId,
)


#: Motif-edge ``relation`` tags that :func:`splice` realizes as a **modifier**
#: (catalyst/regulator) attachment rather than reactant/product incidence. The
#: relation string itself is stored as the modifier's opaque role tag. This is the
#: one place the otherwise-opaque ``relation`` tag is interpreted (F008).
_MODIFIER_RELATIONS = frozenset(
    {"catalyzes", "catalyst", "modifies", "regulates", "inhibits", "activates"}
)


#: The most embeddings :func:`carve` collects before it refuses (T091 AF4): the
#: pick is ``seed % len(top)`` over every reuse-maximal embedding, so carve must
#: hold them all, and a long motif in a large host has combinatorially many.
MAX_EMBEDDINGS = 10_000


#: The two ``type_tag`` values carve reads as a constraint (T091 AM4): a role
#: tagged ``molecule`` binds only to a host molecule, ``reaction`` only to a
#: host reaction. Every other tag is opaque — copied, never interpreted.
_TYPE_TAG_KINDS = {
    "molecule": lambda host: host.molecules,
    "reaction": lambda host: host.reactions,
}


@dataclass(frozen=True)
class CarveFail:
    """A carve that could not produce a valid embedding, with a reason."""

    reason: str


def _node_objs(host: ChemistryImpl) -> Dict[NodeId, object]:
    """Every graph node keyed by ``name``: molecules first, then reactions."""
    objs: Dict[NodeId, object] = {}
    for mol in host.molecules.values():
        objs[mol.name] = mol
    for rxn in host.reactions.values():
        objs[rxn.name] = rxn
    return objs


def _adjacent(host: ChemistryImpl, u: NodeId, v: NodeId) -> bool:
    """Whether the motif edge ``u -> v`` is realized in the bipartite host graph.

    True iff ``v`` is a direct bipartite ``neighbors`` of ``u`` OR a single
    reaction links them as reactant ``u`` -> product ``v``. The reaction case
    is DIRECTED (M36.7 fix): ``splice`` realizes a motif edge ``a -> b`` as
    the reaction ``a -> b``, and a carve that accepted ``b -> a`` bound
    ``identify_pathway``'s chain onto a host backwards for some seeds. The
    bipartite molecule<->reaction case never reaches here: :func:`_edge_holds`
    reads it directed itself (T091 AF2 closed the same bug on that edge).
    """
    if v in host.neighbors(u):
        return True
    for rxn in host.reactions.values():
        if u in {m.name for m in rxn.reactants} and v in {m.name for m in rxn.products}:
            return True
    return False


def _edge_holds(host: ChemistryImpl, u: NodeId, v: NodeId, relation: str) -> bool:
    """Whether the motif edge ``(u, v, relation)`` is realized in ``host`` as
    :func:`splice` would realize it (T088 carve 1). A molecule<->reaction edge
    whose ``relation`` names a catalytic role (:data:`_MODIFIER_RELATIONS`)
    holds only when the molecule is a MODIFIER of the reaction; any other
    molecule<->reaction edge holds only on reactant/product incidence (a
    catalyst does not satisfy a substrate edge, nor a substrate a catalyst
    edge). The incidence is DIRECTED as splice builds it (T091 AF2): ``mol ->
    rxn`` holds only on a reactant, ``rxn -> mol`` only on a product — a
    substrate role bound to a reaction's product was the M36.7 backwards
    binding on the bipartite edge. Molecule<->molecule edges read
    :func:`_adjacent`."""
    if u in host.reactions and v in host.molecules or u in host.molecules and v in host.reactions:
        rxn_id, mol_id = (u, v) if u in host.reactions else (v, u)
        rxn = host.reactions[rxn_id]
        if relation.lower() in _MODIFIER_RELATIONS:
            return mol_id in {m.name for m in rxn.modifiers}
        if u == mol_id:
            return mol_id in {m.name for m in rxn.reactants}
        return mol_id in {m.name for m in rxn.products}
    return _adjacent(host, u, v)


def carve(
    host: ChemistryImpl,
    motif: Motif,
    seed: Seed = Seed(0),
    allow_add: bool = True,
) -> CarveResult | CarveFail:
    """Embed ``motif`` into ``host``, reusing host nodes maximally.

    For each role, candidates are the existing host nodes passing every constraint
    predicate. A backtracking search finds an injective binding of all roles such
    that every motif edge holds between two existing-bound nodes (adjacency via
    :func:`_adjacent`); edges touching a synthesized node are deferred to
    :func:`splice`. The reuse-maximal binding (most roles bound to existing nodes,
    equivalently fewest synthesized) is chosen deterministically; ``seed`` only
    breaks ties among equal-quality embeddings.

    The search runs first with no synthesis (T091 AF4) — when every role
    binds to a host node those embeddings ARE the reuse-maximal set, so the
    pick is the one a single full search makes. Only when that finds nothing,
    and with ``allow_add``, it runs again allowing ``k = 1, 2, …`` synthesized
    roles, stopping at the first ``k`` with an embedding and pruning every
    branch that would need more (T091 AM1). More than :data:`MAX_EMBEDDINGS`
    embeddings at the best reuse — the frontier, never a lower-reuse one the
    search discards — refuses, naming the motif and host sizes.

    A role whose ``type_tag`` is ``"molecule"`` or ``"reaction"`` binds only
    to a node of that kind (T091 AM4: ``!pattern {roles: {a: molecule}}``
    could bind ``a`` to a reaction); any other tag stays opaque.

    Returns a :class:`~alienbio.suite.types.CarveResult` (with ``added`` listing the
    synthesized node ids, sorted) or a :class:`CarveFail` when no embedding exists
    (e.g. a role has no candidate and ``allow_add`` is False).
    """
    node_objs = _node_objs(host)

    cands: dict[str, list[NodeId]] = {}
    for role in motif.roles:
        kinds = _TYPE_TAG_KINDS.get(role.type_tag)
        cands[role.name] = sorted(
            nid
            for nid, obj in node_objs.items()
            if (kinds is None or nid in kinds(host))
            and all(pred(obj) for pred in role.constraints)
        )

    role_names = [role.name for role in motif.roles]
    edges = motif.edges

    # Each collected solution: (reuse_count, canonical_key, binding, synth_roles).
    solutions: list[tuple[int, tuple[tuple[str, NodeId], ...], dict[str, NodeId], tuple[str, ...]]] = []
    best = [-1]  # the best reuse found so far (a cell the closure mutates)

    class _TooMany(Exception):
        pass

    # ``_edge_holds`` rebuilds the host's graph view per call; the search asks
    # the same few (src, dst, relation) questions many times over.
    holds: dict[tuple[NodeId, NodeId, str], bool] = {}

    def edge_holds(src: NodeId, dst: NodeId, relation: str) -> bool:
        key = (src, dst, relation)
        if key not in holds:
            holds[key] = _edge_holds(host, src, dst, relation)
        return holds[key]

    def edge_ok(
        name: str,
        node_id: NodeId,
        is_synth: bool,
        assigned: dict[str, tuple[NodeId, bool]],
    ) -> bool:
        """Whether binding ``name`` to ``node_id`` keeps all satisfiable edges intact."""
        for a, b, relation in edges:
            if a == name:
                other, forward = b, True
            elif b == name:
                other, forward = a, False
            else:
                continue
            if other not in assigned:
                continue
            other_id, other_synth = assigned[other]
            if is_synth or other_synth:
                # Adjacency to a synthesized node is realized later by splice.
                continue
            src, dst = (node_id, other_id) if forward else (other_id, node_id)
            if not edge_holds(src, dst, relation):
                return False
        return True

    def backtrack(
        i: int,
        assigned: dict[str, tuple[NodeId, bool]],
        used: set[NodeId],
        reuse: int,
        synth_ok: bool,
    ) -> None:
        # Branch and bound: a branch that cannot reach the best reuse found
        # holds no reuse-maximal embedding (equal-reuse branches are kept,
        # so the top set — and the seed's pick in it — is unchanged).
        if reuse + (len(role_names) - i) < best[0]:
            return
        if i == len(role_names):
            if reuse > best[0]:
                best[0] = reuse
                solutions[:] = [sol for sol in solutions if sol[0] >= reuse]
            binding = {name: nid for name, (nid, _) in assigned.items()}
            key = tuple(sorted(binding.items()))
            synth_roles = tuple(
                sorted(name for name, (_, synth) in assigned.items() if synth)
            )
            solutions.append((reuse, key, binding, synth_roles))
            if len(solutions) > MAX_EMBEDDINGS:
                raise _TooMany
            return
        name = role_names[i]
        for nid in cands[name]:
            if nid in used:
                continue
            if edge_ok(name, nid, False, assigned):
                assigned[name] = (nid, False)
                used.add(nid)
                backtrack(i + 1, assigned, used, reuse + 1, synth_ok)
                del assigned[name]
                used.discard(nid)
        if synth_ok:
            synth_id = f"{name}#new"
            if edge_ok(name, synth_id, True, assigned):
                assigned[name] = (synth_id, True)
                backtrack(i + 1, assigned, used, reuse, synth_ok)
                del assigned[name]

    try:
        backtrack(0, {}, set(), 0, False)
        # The synthesis pass deepens the number of synthesized roles one at a
        # time (T091 AM1): at ``k`` the bound starts at ``n - k``, so a leaf is
        # reached only at that reuse — the frontier — and the cap counts it
        # alone, never a lower-reuse transient a later branch would discard.
        # Every ``k`` below the first that finds one found none, so the set it
        # finds is exactly the reuse-maximal set a single search would keep.
        for k in range(1, len(role_names) + 1) if allow_add else ():
            if solutions:
                break
            best[0] = len(role_names) - k
            backtrack(0, {}, set(), 0, True)
    except _TooMany:
        return CarveFail(
            reason=(
                f"more than {MAX_EMBEDDINGS} embeddings of a {len(role_names)}-role motif "
                f"in a host of {len(node_objs)} nodes ({len(host.molecules)} molecules, "
                f"{len(host.reactions)} reactions); refusing rather than enumerating them — "
                "narrow the role constraints or shrink the host"
            )
        )

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
    return CarveResult(motif=motif, binding=binding, added=added, removed=())


def _rebuild(
    molecules: Dict[NodeId, MoleculeImpl],
    reactions: Dict[NodeId, ReactionImpl],
    atoms: Dict[str, object],
) -> ChemistryImpl:
    """A working ``ChemistryImpl`` over the given name-keyed node tables."""
    return ChemistryImpl(
        "splice",
        atoms=dict(atoms),  # type: ignore[arg-type]
        molecules=dict(molecules),
        reactions=dict(reactions),
        dat=_mock_dat("chem/splice"),
    )


def splice(host: ChemistryImpl, skeleton: CarveResult) -> ChemistryImpl:
    """Return a new host with ``skeleton``'s edits applied (deterministic).

    Creates each synthesized node (an atom-free :class:`~alienbio.bio.molecule.MoleculeImpl`
    carrying the ``type_tag`` of the role bound to it as its ``description``), realizes
    every motif edge as reactant/product incidence, and drops every removed node
    (stripping it from all reaction reactant/product lists). The output is a pure
    function of ``(host, skeleton)``.

    Edge realization is bio-typed:
    - a **molecule<->reaction** edge whose ``relation`` names a catalytic role
      (:data:`_MODIFIER_RELATIONS`) attaches the molecule as a **modifier**
      (catalyst/regulator, not consumed), with the relation as its role tag;
    - any other **molecule<->reaction** edge adds the molecule to that reaction (as a
      product when the edge runs reaction->molecule, else as a reactant), moving it
      off the other side when the host had it backwards — unless another motif edge
      asks for that side (a feedback motif keeps the molecule on both); a move that
      would empty a side refuses (``ValueError``) rather than turn a conversion
      into a boundary reaction;
    - a **molecule<->molecule** edge inserts a neutral reactant->product reaction;
    - a **reaction<->reaction** edge has no bio meaning and is skipped.
    """
    molecules: Dict[NodeId, MoleculeImpl] = {m.name: m for m in host.molecules.values()}
    reactions: Dict[NodeId, ReactionImpl] = {r.name: r for r in host.reactions.values()}
    atoms: Dict[str, object] = dict(host.atoms)
    binding = skeleton.binding
    motif = skeleton.motif
    role_by_name = {role.name: role for role in motif.roles}

    for nid in skeleton.added:
        tag = ""
        for name, bound_id in binding.items():
            if bound_id == nid:
                tag = role_by_name[name].type_tag
                break
        if nid not in molecules and nid not in reactions:
            molecules[nid] = MoleculeImpl(
                nid,
                name=nid,
                bdepth=0,
                description=tag,
                dat=_mock_dat(f"mol/{nid}"),
            )

    # The sides the motif asks of each (reaction, molecule) pair (T091 AM2): a
    # feedback motif (``x -product-> m`` and ``m -substrate-> x``) asks for
    # both, and realizing one edge must not undo the other.
    demanded: dict[tuple[NodeId, NodeId], set[str]] = {}
    for a, b, relation in motif.edges:
        u, v = binding[a], binding[b]
        if relation.lower() in _MODIFIER_RELATIONS or (u in reactions) == (v in reactions):
            continue
        pair = (u, v) if u in reactions else (v, u)
        demanded.setdefault(pair, set()).add("products" if u in reactions else "reactants")

    for a, b, relation in motif.edges:
        u = binding[a]
        v = binding[b]
        current = _rebuild(molecules, reactions, atoms)
        if _edge_holds(current, u, v, relation):
            continue

        u_is_rxn = u in reactions
        v_is_rxn = v in reactions

        if u_is_rxn and v_is_rxn:
            # No bio meaning for a reaction<->reaction edge; nothing to realize.
            continue

        if u_is_rxn or v_is_rxn:
            # Molecule<->reaction edge. A catalytic relation attaches the molecule as
            # a modifier (not consumed); otherwise follow the edge direction —
            # reaction->molecule makes the molecule a product, molecule->reaction a
            # reactant. Every case preserves the reaction's existing modifiers.
            rxn_id = u if u_is_rxn else v
            mol_id = v if u_is_rxn else u
            mol = molecules[mol_id]
            rxn = reactions[rxn_id]
            new_reactants = dict(rxn.reactants)
            new_products = dict(rxn.products)
            new_modifiers = dict(rxn.modifiers)
            if relation.lower() in _MODIFIER_RELATIONS:
                new_modifiers[mol] = relation
            else:
                # A molecule on the wrong side is re-bound (T091 AF2: the edge
                # says rxn -> mol, the host had mol -> rxn, or the reverse) —
                # unless another motif edge asks for that side too (T091 AM2),
                # and never so that a side empties (T091 AM7: ``A -> B`` would
                # become the sink ``A + B -> ∅``, which the conservation canary
                # exempts as a boundary reaction).
                add_side, other_side = (
                    (new_products, new_reactants) if u_is_rxn else (new_reactants, new_products)
                )
                other_name = "reactants" if u_is_rxn else "products"
                if mol in other_side and other_name not in demanded.get((rxn_id, mol_id), set()):
                    if len(other_side) == 1:
                        raise ValueError(
                            f"splice: edge ({a!r}, {b!r}, {relation!r}) would move {mol_id} off "
                            f"reaction {rxn_id}'s {other_name}, leaving that side empty — the "
                            "skeleton runs against the host's chemistry"
                        )
                    other_side.pop(mol)
                add_side[mol] = 1.0
            reactions[rxn_id] = rebuild_reaction(
                rxn,
                reactants=new_reactants,
                products=new_products,
                modifiers=new_modifiers,
                dat=_mock_dat(f"rxn/{rxn_id}"),
            )
        else:
            # Molecule<->molecule edge: insert a reactant->product reaction.
            rxn_id = f"rxn::{u}->{v}"
            reactions[rxn_id] = ReactionImpl(
                rxn_id,
                reactants={molecules[u]: 1.0},
                products={molecules[v]: 1.0},
                dat=_mock_dat(f"rxn/{rxn_id}"),
            )

    realized = _rebuild(molecules, reactions, atoms)
    unrealized = [
        (a, b, relation)
        for a, b, relation in motif.edges
        if not (binding[a] in reactions and binding[b] in reactions)
        and not _edge_holds(realized, binding[a], binding[b], relation)
    ]
    if unrealized:
        raise AssertionError(f"splice: motif edges {unrealized} do not hold after splice")

    for nid in skeleton.removed:
        molecules.pop(nid, None)
        reactions.pop(nid, None)
        for rid in list(reactions.keys()):
            rxn = reactions[rid]
            reactions[rid] = rebuild_reaction(
                rxn,
                reactants={m: c for m, c in rxn.reactants.items() if m.name != nid},
                products={m: c for m, c in rxn.products.items() if m.name != nid},
                modifiers={m: r for m, r in rxn.modifiers.items() if m.name != nid},
                dat=_mock_dat(f"rxn/{rid}"),
            )

    return _rebuild(molecules, reactions, atoms)
