"""T091 AF — the suite-construction layer end to end: carve direction and
search size, the identify key checked against its world, the stated end
earning no credit, self-loop motifs."""

from __future__ import annotations

import time

import pytest

from alienbio import mk
from alienbio.bio.world import Compartment, WorldImpl
from alienbio.suite.archetypes import _is_molecule, identify_pathway
from alienbio.suite.carve import MAX_EMBEDDINGS, CarveFail, carve, splice
from alienbio.suite.dist import Seed
from alienbio.suite.grade import grade_answer
from alienbio.suite.pipeline import draft_world
from alienbio.suite.types import Answer, Motif, RoleSlot


def _is_reaction(node) -> bool:
    return not _is_molecule(node)


MOL = (_is_molecule,)
RXN = (_is_reaction,)


def _world(chem):
    first = sorted(m.name for m in chem.molecules.values())[0]
    return WorldImpl(chem, (Compartment("cell", None, "cell", 1.0, concentrations={first: 1.0}),))


def test_a_substrate_role_binds_only_to_a_reactant():
    """AF2: odd seeds bound ``sub -substrate-> rx`` to the reaction's PRODUCT."""
    a, b = mk.M("A"), mk.M("B")
    chem = mk.C("host", [a, b], [mk.R("x1", {a: 1.0}, {b: 1.0})])
    motif = Motif(roles=(RoleSlot("sub", "m", MOL), RoleSlot("rx", "r", RXN)), edges=(("sub", "rx", "substrate"),))
    for s in range(6):
        result = carve(chem, motif, Seed(s), allow_add=False)
        assert not isinstance(result, CarveFail)
        assert result.binding == {"sub": "A", "rx": "x1"}, s
    product = Motif(roles=(RoleSlot("rx", "r", RXN), RoleSlot("out", "m", MOL)), edges=(("rx", "out", "product"),))
    for s in range(6):
        result = carve(chem, product, Seed(s), allow_add=False)
        assert not isinstance(result, CarveFail) and result.binding == {"rx": "x1", "out": "B"}


def test_splice_rebinds_a_backwards_incidence():
    """AF2: a hand skeleton whose ``mol -> rxn`` edge names the reaction's
    product moves the molecule to the reactant side, not onto both."""
    from alienbio.suite.types import CarveResult

    a, b = mk.M("A"), mk.M("B")
    chem = mk.C("host", [a, b], [mk.R("x1", {a: 1.0}, {b: 1.0})])
    motif = Motif(roles=(RoleSlot("sub", "m", MOL), RoleSlot("rx", "r", RXN)), edges=(("sub", "rx", "substrate"),))
    out = splice(chem, CarveResult(motif=motif, binding={"sub": "B", "rx": "x1"}))
    rxn = out.reactions["x1"]
    assert {m.name for m in rxn.reactants} == {"A", "B"}
    assert {m.name for m in rxn.products} == set()


def test_a_long_chain_among_many_distractors_carves_fast_and_identically():
    """AF4: n=8 with 10 distractors took 38 s (every synthesized-node
    combination enumerated before the full embedding won)."""
    arch = identify_pathway(8)
    host = draft_world(arch.motif, Seed(0), distractor_count=10).chemistry
    t = time.time()
    result = carve(host, arch.motif, Seed(0))
    assert time.time() - t < 2.0
    assert not isinstance(result, CarveFail)
    assert result.binding == {f"r{i}": f"r{i}" for i in range(8)} and result.added == ()


def test_too_many_embeddings_refuse_naming_the_size():
    """AF4: a 10-role motif over a 3-node chain among 12 distractors has more
    than MAX_EMBEDDINGS reuse-maximal embeddings; carve refuses."""
    host = draft_world(identify_pathway(3).motif, Seed(0), distractor_count=12).chemistry
    result = carve(host, identify_pathway(10).motif, Seed(0))
    assert isinstance(result, CarveFail)
    assert f"more than {MAX_EMBEDDINGS} embeddings of a 10-role motif" in result.reason


def test_a_key_with_a_synthesized_node_refuses():
    """AF1: a 4-role chain carved (allow_add) into a 3-node host synthesized
    ``r2#new`` and bound an inert distractor as the end."""
    host = draft_world(identify_pathway(3).motif, Seed(0), distractor_count=3)
    arch = identify_pathway(4)
    result = carve(host.chemistry, arch.motif, Seed(0))
    assert not isinstance(result, CarveFail) and result.added
    with pytest.raises(ValueError, match="not nodes of the world"):
        arch.recipe.build_key(result, host)


def test_a_binding_that_does_not_run_the_chemistry_refuses():
    """AF1: a hand binding is checked too — r0 -> d0 is no reaction."""
    from alienbio.suite.types import CarveResult

    world = draft_world(identify_pathway(3).motif, Seed(0), distractor_count=1)
    arch = identify_pathway(3)
    bad = CarveResult(motif=arch.motif, binding={"r0": "r0", "r1": "r1", "r2": "d0"})
    with pytest.raises(ValueError, match="steps r1 -> d0"):
        arch.recipe.build_question(bad, world)


def test_a_key_that_is_not_unique_refuses_naming_both_routes():
    """AF5: on a diamond A->B->D, A->C->D the seed's parity picked a route
    and the other true route scored 0."""
    m = {n: mk.M(n) for n in "ABCD"}
    rx = [
        mk.R("x1", {m["A"]: 1.0}, {m["B"]: 1.0}), mk.R("x2", {m["B"]: 1.0}, {m["D"]: 1.0}),
        mk.R("x3", {m["A"]: 1.0}, {m["C"]: 1.0}), mk.R("x4", {m["C"]: 1.0}, {m["D"]: 1.0}),
    ]
    chem = mk.C("host", list(m.values()), rx)
    arch = identify_pathway(3)
    result = carve(chem, arch.motif, Seed(0), allow_add=False)
    assert not isinstance(result, CarveFail)
    with pytest.raises(ValueError, match=r"not unique — \['A', 'B', 'D'\] and \['A', 'C', 'D'\]"):
        arch.recipe.build_key(result, _world(chem))


def test_neither_stated_endpoint_earns_credit():
    """AF11: appending the end the question states doubled [s, m]'s score."""
    spec = identify_pathway(3).recipe.grader_spec()
    key = Answer(["s", "m", "e"], "ordered_path")
    assert grade_answer(Answer(["s", "e"], "ordered_path"), key, spec) == 0.0
    assert grade_answer(Answer(["s", "m"], "ordered_path"), key, spec) == 1.0
    assert grade_answer(Answer(["s", "m", "e"], "ordered_path"), key, spec) == 1.0
    long_key = Answer(["s", "a", "b", "e"], "ordered_path")
    spec4 = identify_pathway(4).recipe.grader_spec()
    assert grade_answer(Answer(["s", "a"], "ordered_path"), long_key, spec4) == pytest.approx(0.5)
    assert grade_answer(Answer(["s", "a", "e"], "ordered_path"), long_key, spec4) == pytest.approx(0.5)


def test_a_self_loop_motif_edge_refuses():
    """AF9: carve never checked an (a, a) edge and splice minted a -> a."""
    with pytest.raises(ValueError, match="joins a role to itself"):
        Motif(roles=(RoleSlot("a", "m"),), edges=(("a", "a", "reacts_to"),))
