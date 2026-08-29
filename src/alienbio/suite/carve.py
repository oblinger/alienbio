"""Subgraph carve / splice engine — pure graph embedding + minimal edits.

This module is domain-neutral in its *algorithm*: it treats a
:class:`~alienbio.bio.chemistry.ChemistryImpl` as a generic bipartite graph of
molecules (species nodes) and reactions (reaction nodes), reached only through
``neighbors`` / ``molecules`` / ``reactions`` (all keyed by ``name``), and a
:class:`~alienbio.suite.types.Motif` as an abstract pattern graph. Role
constraints are opaque :data:`~alienbio.suite.types.Predicate` callables that are
only *called* on the bound node object (a ``MoleculeImpl`` or ``ReactionImpl``); a
role's ``type_tag`` and an edge's ``relation`` tag are opaque strings that are only
*copied onto* synthesized nodes, never interpreted.

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
:func:`_adjacent` predicate: two nodes are adjacent if they are direct bipartite
``neighbors`` OR a single reaction links them as reactant->product (either direction).
The edge ``splice`` inserts to realize a motif edge makes exactly this predicate true.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from ..bio.chemistry import ChemistryImpl, _mock_dat
from ..bio.molecule import MoleculeImpl
from ..bio.reaction import ReactionImpl
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

    True iff ``v`` is a direct bipartite ``neighbors`` of ``u`` (one is a molecule,
    the other a reaction referencing it — incidence has no direction) OR a
    single reaction links them as reactant ``u`` -> product ``v``. The
    reaction case is DIRECTED (M36.7 fix): ``splice`` realizes a motif edge
    ``a -> b`` as the reaction ``a -> b``, and a carve that accepted ``b -> a``
    bound ``identify_pathway``'s chain onto a host backwards for some seeds —
    minting a key path whose every edge ran against the chemistry (the
    reversed chain, which the recipe itself lists as a *distractor*).
    """
    if v in host.neighbors(u):
        return True
    for rxn in host.reactions.values():
        if u in {m.name for m in rxn.reactants} and v in {m.name for m in rxn.products}:
            return True
    return False


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

    Returns a :class:`~alienbio.suite.types.CarveResult` (with ``added`` listing the
    synthesized node ids, sorted) or a :class:`CarveFail` when no embedding exists
    (e.g. a role has no candidate and ``allow_add`` is False).
    """
    node_objs = _node_objs(host)

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
            if not _adjacent(host, src, dst):
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
      product when the edge runs reaction->molecule, else as a reactant);
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

    for a, b, relation in motif.edges:
        u = binding[a]
        v = binding[b]
        current = _rebuild(molecules, reactions, atoms)
        if _adjacent(current, u, v):
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
            elif u_is_rxn:
                new_products[mol] = 1.0
            else:
                new_reactants[mol] = 1.0
            reactions[rxn_id] = ReactionImpl(
                rxn_id,
                reactants=new_reactants,
                products=new_products,
                modifiers=new_modifiers,
                rate=rxn.rate,
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

    for nid in skeleton.removed:
        molecules.pop(nid, None)
        reactions.pop(nid, None)
        for rid in list(reactions.keys()):
            rxn = reactions[rid]
            reactions[rid] = ReactionImpl(
                rid,
                reactants={m: c for m, c in rxn.reactants.items() if m.name != nid},
                products={m: c for m, c in rxn.products.items() if m.name != nid},
                modifiers={m: r for m, r in rxn.modifiers.items() if m.name != nid},
                rate=rxn.rate,
                dat=_mock_dat(f"rxn/{rid}"),
            )

    return _rebuild(molecules, reactions, atoms)
