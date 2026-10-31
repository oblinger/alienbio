"""Tests for M27.1 — the ``identify_pathway`` archetype + its recipe.

The load-bearing property is **skeleton-first key derivation**: given a carved
``CarveResult`` binding the chain roles to host nodes, the recipe reads the correct
ordered path off the binding by construction, and the grader self-scores it 1.0.
"""

from __future__ import annotations

import pytest

from alienbio.suite.archetypes import (
    IdentifyPathwayRecipe,
    _is_molecule,
    identify_pathway,
)
from alienbio.suite.dist import Seed
from alienbio.suite.grade import grade_answer
from alienbio.suite.types import CarveResult, Motif


def _skeleton(role_to_node: dict[str, str], motif: Motif) -> CarveResult:
    return CarveResult(motif=motif, binding=role_to_node)


def _chain_world(*names: str):
    """A linear host ``names[0] -> names[1] -> …`` the key is checked against."""
    from alienbio import mk
    from alienbio.bio.world import Compartment, WorldImpl

    mols = {n: mk.M(n) for n in names}
    rxns = [mk.R(f"x{i}", {mols[a]: 1.0}, {mols[b]: 1.0}) for i, (a, b) in enumerate(zip(names, names[1:]))]
    chem = mk.C("host", list(mols.values()), rxns)
    return WorldImpl(chem, (Compartment("cell", None, "cell", 1.0, concentrations={names[0]: 1.0}),))


def test_identify_pathway_builds_a_chain_motif():
    arch = identify_pathway(pathway_length=3)
    assert arch.id == "identify_pathway"
    assert arch.verb == "identify"
    assert [r.name for r in arch.motif.roles] == ["r0", "r1", "r2"]
    assert arch.motif.edges == (("r0", "r1", "reacts_to"), ("r1", "r2", "reacts_to"))


def test_pathway_length_below_three_rejected():
    # T091 AF3: at two nodes the question's endpoints ARE the key.
    for n in (1, 2):
        with pytest.raises(ValueError, match="pathway_length must be >= 3.*whole key"):
            identify_pathway(pathway_length=n)
    with pytest.raises(ValueError, match="at least 3 roles"):
        IdentifyPathwayRecipe(role_names=("a", "b"))


def test_constraints_are_applied_to_every_role():
    sentinel = lambda obj: True  # noqa: E731 - opaque predicate
    arch = identify_pathway(pathway_length=3, constraints=(sentinel,))
    for role in arch.motif.roles:
        # The molecule gate is prepended; the user's constraint follows it.
        assert role.constraints == (_is_molecule, sentinel)


def test_roles_carry_the_molecule_gate_by_default():
    arch = identify_pathway(pathway_length=3)
    for role in arch.motif.roles:
        assert _is_molecule in role.constraints


def test_is_molecule_excludes_reaction_nodes():
    # A molecule (no `reactants`) passes; a reaction (has `reactants`) is rejected.
    from alienbio import mk

    a, b = mk.M("A"), mk.M("B")
    r = mk.R("R1", {a: 1.0}, {b: 1.0})
    assert _is_molecule(a) is True
    assert _is_molecule(r) is False


def test_build_key_reads_ordered_path_off_the_skeleton():
    arch = identify_pathway(pathway_length=3)
    sk = _skeleton({"r0": "A", "r1": "B", "r2": "C"}, arch.motif)
    key = arch.recipe.build_key(sk, _chain_world("A", "B", "C"))
    assert key.kind == "ordered_path"
    assert key.value == ["A", "B", "C"]  # order follows role indices, by construction


def test_build_question_is_the_endpoints():
    arch = identify_pathway(pathway_length=4)
    sk = _skeleton({"r0": "A", "r1": "B", "r2": "C", "r3": "D"}, arch.motif)
    q = arch.recipe.build_question(sk, _chain_world("A", "B", "C", "D"))
    assert q.kind == "ordered_path"
    assert q.structured == ["A", "D"]  # start + end only


def test_key_self_grades_to_one():
    arch = identify_pathway(pathway_length=3)
    sk = _skeleton({"r0": "A", "r1": "B", "r2": "C"}, arch.motif)
    key = arch.recipe.build_key(sk, _chain_world("A", "B", "C"))
    assert grade_answer(key, key, arch.recipe.grader_spec()) == 1.0


def test_grader_spec_is_partial_ordered_path():
    arch = identify_pathway(pathway_length=3)
    spec = arch.recipe.grader_spec()
    assert spec.kind == "ordered_path"
    # T088 identify_pathway 1 / T091 AF11: neither stated endpoint earns credit.
    assert spec.config == {"partial": True, "given_prefix": 1, "given_suffix": 1}


def test_recipe_holds_role_order():
    arch = identify_pathway(pathway_length=3)
    assert isinstance(arch.recipe, IdentifyPathwayRecipe)
    assert arch.recipe.role_names == ("r0", "r1", "r2")
