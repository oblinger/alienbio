"""T091 AM — verifier AM's follow-ups on round AI: carve's cap counts the
reuse-maximal frontier only, splice keeps a feedback motif's two edges, the
identify key is molecules only, visited once, and the one SHORTEST route,
found by a bounded breadth-first search, and a role tagged ``molecule`` /
``reaction`` binds only to that kind."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from alienbio import mk
from alienbio.bio.world import Compartment, WorldImpl
from alienbio.suite.archetypes import _is_molecule, check_pathway_key, identify_pathway
from alienbio.suite.carve import _edge_holds, CarveFail, carve, splice
from alienbio.suite.dist import Seed
from alienbio.suite.types import CarveResult, Motif, RoleSlot

MOL = (_is_molecule,)
RXN = (lambda node: not _is_molecule(node),)


def _world(chem):
    first = sorted(m.name for m in chem.molecules.values())[0]
    return WorldImpl(chem, (Compartment("cell", None, "cell", 1.0, concentrations={first: 1.0}),))


def _chain_host(edges: list[tuple[str, str]], extra: tuple[str, ...] = ()):
    names = sorted({n for e in edges for n in e} | set(extra))
    m = {n: mk.M(n) for n in names}
    rx = [mk.R(f"x_{a}_{b}", {m[a]: 1.0}, {m[b]: 1.0}) for a, b in edges]
    return mk.C("host", list(m.values()), rx)


def test_the_cap_counts_the_best_reuse_only():
    """AM1: 110 inert molecules plus a 3-chain, a 5-role chain carved with
    allow_add: the reuse-4 set is 220 embeddings, but the reuse-3 transients
    passed MAX_EMBEDDINGS first and carve refused."""
    inert = [f"A{i:03d}" for i in range(110)]
    host = _chain_host([("Z0", "Z1"), ("Z1", "Z2")], extra=tuple(inert))
    t = time.time()
    result = carve(host, identify_pathway(5).motif, Seed(0), allow_add=True)
    assert time.time() - t < 5.0
    assert isinstance(result, CarveResult), result
    assert result.binding == {"r0": "A000", "r1": "r1#new", "r2": "Z0", "r3": "Z1", "r4": "Z2"}
    assert result.added == ("r1#new",)


def test_splice_keeps_both_edges_of_a_feedback_pair():
    """AM2: ``x -product-> m`` then ``m -substrate-> x`` popped m off the
    products the first edge had just added."""
    a, b = mk.M("A"), mk.M("B")
    host = mk.C("h", [a, b], [mk.R("x1", {a: 1.0}, {b: 1.0})])
    motif = Motif(
        roles=(RoleSlot("x", "r", RXN), RoleSlot("m", "m", MOL)),
        edges=(("x", "m", "product"), ("m", "x", "substrate")),
    )
    sk = CarveResult(motif=motif, binding={"x": "x1", "m": "m#new"}, added=("m#new",))
    out = splice(host, sk)
    rxn = out.reactions["x1"]
    assert {m.name for m in rxn.reactants} == {"A", "m#new"}
    assert {m.name for m in rxn.products} == {"B", "m#new"}
    for u, v, rel in motif.edges:
        assert _edge_holds(out, sk.binding[u], sk.binding[v], rel)


def test_a_shorter_true_route_refuses_naming_it():
    """AM3: A->B->C beside A->D->E->C: the key [A, D, E, C] loaded, and the
    true, shorter answer [A, B, C] scored 0 — the question states no length."""
    chem = _chain_host([("A", "B"), ("B", "C"), ("A", "D"), ("D", "E"), ("E", "C")])
    with pytest.raises(ValueError, match=r"not the shortest route — \['A', 'B', 'C'\] runs A -> C in 3 nodes"):
        check_pathway_key(["A", "D", "E", "C"], _world(chem))
    check_pathway_key(["A", "B", "C"], _world(chem))  # the longer alternative is allowed
    direct = _chain_host([("A", "B"), ("B", "C"), ("A", "C")])
    with pytest.raises(ValueError, match=r"\['A', 'C'\] runs A -> C in 2 nodes"):
        check_pathway_key(["A", "B", "C"], _world(direct))


def test_the_route_search_is_fast_on_a_dense_side_cluster():
    """AM6: a 12-molecule clique off the start took 78 s to walk every
    simple route of the key's length; the breadth-first search is linear."""
    cluster = [f"C{i}" for i in range(12)]
    edges = [("S", "M1"), ("M1", "M2"), ("M2", "M3"), ("M3", "M4"), ("M4", "M5"), ("M5", "M6"),
             ("M6", "M7"), ("M7", "M8"), ("M8", "E")]
    edges += [("S", c) for c in cluster] + [(a, b) for a in cluster for b in cluster if a != b]
    chem = _chain_host(edges)
    t = time.time()
    check_pathway_key(["S", "M1", "M2", "M3", "M4", "M5", "M6", "M7", "M8", "E"], _world(chem))
    assert time.time() - t < 1.0


def test_the_route_search_refuses_past_its_cap(monkeypatch):
    import alienbio.suite.archetypes as arch

    monkeypatch.setattr(arch, "MAX_ROUTE_NODES", 3)
    chem = _chain_host([("A", "B"), ("B", "C"), ("C", "D"), ("D", "E")])
    with pytest.raises(ValueError, match="more than 3 molecules reachable from A"):
        check_pathway_key(["A", "B", "C", "D", "E"], _world(chem))


def test_a_cyclic_key_refuses():
    """AM8: a reversible A<->B with binding {a: A, b: B, c: A} loaded [A, B, A]."""
    a, b = mk.M("A"), mk.M("B")
    chem = mk.C("h", [a, b], [mk.R("f", {a: 1.0}, {b: 1.0}), mk.R("r", {b: 1.0}, {a: 1.0})])
    with pytest.raises(ValueError, match=r"visits \['A'\] twice"):
        check_pathway_key(["A", "B", "A"], _world(chem))


def test_a_reaction_in_the_key_refuses():
    """AM4: the check accepted a reaction id, so a key could be [r0, r0_r1, r1]."""
    chem = _chain_host([("A", "B"), ("B", "C")])
    with pytest.raises(ValueError, match="reactions of the world, not molecules"):
        check_pathway_key(["A", "x_A_B", "B"], _world(chem))


def test_a_role_tagged_molecule_or_reaction_binds_only_that_kind():
    """AM4: ``!pattern {roles: {a: molecule}}``'s tag was opaque, so carve
    bound a "molecule" role to a reaction on half the seeds."""
    chem = _chain_host([("A", "B"), ("B", "C")])
    mols = Motif(roles=(RoleSlot("a", "molecule"), RoleSlot("b", "molecule"), RoleSlot("c", "molecule")),
                 edges=(("a", "b", "reacts_to"), ("b", "c", "reacts_to")))
    for s in range(8):
        result = carve(chem, mols, Seed(s), allow_add=False)
        assert isinstance(result, CarveResult) and result.binding == {"a": "A", "b": "B", "c": "C"}, s
    rxn = Motif(roles=(RoleSlot("x", "reaction"), RoleSlot("m", "molecule")), edges=(("x", "m", "product"),))
    for s in range(4):
        result = carve(chem, rxn, Seed(s), allow_add=False)
        assert isinstance(result, CarveResult) and result.binding["x"] in chem.reactions, s
    only = Motif(roles=(RoleSlot("x", "reaction"),), edges=())
    bare = mk.C("bare", [mk.M("A")], [])
    assert isinstance(carve(bare, only, Seed(0), allow_add=False), CarveFail)


def test_the_expr_spec_sample_yields_molecule_keys_on_every_seed():
    """AM4: the CI-executed Expr Spec sample gave keys like
    ['r0_r1', 'r1', 'r1_r2'] on half the seeds."""
    from alienbio.expr import Env

    text = """
d: !x identify_pathway(pathway_length=3)
w: !x d.world
p: !pattern
  roles: {a: molecule, b: molecule, c: molecule}
  edges: [ [a, b, reacts_to], [b, c, reacts_to] ]
sk: !carve {host: !x w, pattern: !x p}
obj: !identify {skeleton: !x sk, world: !x w, roles: [a, b, c]}
key: !x obj.objective.key.value
"""
    for s in range(8):
        values = Env.standard(seed=s).load(Path("sample.yaml"), text=text).force_all()
        world = values["w"]
        assert all(node in {m.name for m in world.chemistry.molecules.values()} for node in values["key"]), s
