"""Tests for M27.1 — the ``identify_pathway`` archetype + its recipe.

The load-bearing property is **skeleton-first key derivation**: given a carved
``Skeleton`` binding the chain roles to host nodes, the recipe reads the correct
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
from alienbio.suite.types import Motif, Skeleton


def _skeleton(role_to_node: dict[str, str], motif: Motif) -> Skeleton:
    return Skeleton(motif=motif, binding=role_to_node)


def test_identify_pathway_builds_a_chain_motif():
    arch = identify_pathway(pathway_length=3)
    assert arch.id == "identify_pathway"
    assert arch.verb == "identify"
    assert [r.name for r in arch.motif.roles] == ["r0", "r1", "r2"]
    assert arch.motif.edges == (("r0", "r1", "reacts_to"), ("r1", "r2", "reacts_to"))


def test_pathway_length_below_two_rejected():
    with pytest.raises(ValueError, match="pathway_length must be >= 2"):
        identify_pathway(pathway_length=1)


def test_constraints_are_applied_to_every_role():
    sentinel = lambda obj: True  # noqa: E731 - opaque predicate
    arch = identify_pathway(pathway_length=2, constraints=(sentinel,))
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
    key = arch.recipe.build_key(sk, world=None)  # type: ignore[arg-type]
    assert key.kind == "ordered_path"
    assert key.value == ["A", "B", "C"]  # order follows role indices, by construction


def test_build_question_is_the_endpoints():
    arch = identify_pathway(pathway_length=4)
    sk = _skeleton({"r0": "A", "r1": "B", "r2": "C", "r3": "D"}, arch.motif)
    q = arch.recipe.build_question(sk, world=None)  # type: ignore[arg-type]
    assert q.kind == "ordered_path"
    assert q.structured == ["A", "D"]  # start + end only


def test_key_self_grades_to_one():
    arch = identify_pathway(pathway_length=3)
    sk = _skeleton({"r0": "A", "r1": "B", "r2": "C"}, arch.motif)
    key = arch.recipe.build_key(sk, world=None)  # type: ignore[arg-type]
    assert grade_answer(key, key, arch.recipe.grader_spec()) == 1.0


def test_grader_spec_is_partial_ordered_path():
    arch = identify_pathway(pathway_length=2)
    spec = arch.recipe.grader_spec()
    assert spec.kind == "ordered_path"
    assert spec.config == {"partial": True}


def test_distractors_are_distinct_same_length_permutations():
    arch = identify_pathway(pathway_length=4)
    sk = _skeleton({"r0": "A", "r1": "B", "r2": "C", "r3": "D"}, arch.motif)
    key = arch.recipe.build_key(sk, world=None)  # type: ignore[arg-type]
    distractors = arch.recipe.build_distractors(sk, None, Seed(3))  # type: ignore[arg-type]
    assert len(distractors) >= 1
    for d in distractors:
        assert d.kind == "ordered_path"
        assert d.value != key.value  # a genuine near-miss
        assert sorted(d.value) == sorted(key.value)  # same node set, reordered
        # A distractor scores strictly below the key under the archetype's grader.
        assert grade_answer(d, key, arch.recipe.grader_spec()) < 1.0


def test_n3_distractors_never_move_a_single_endpoint():
    # Regression (Fable finding 3): the interior swap must not touch an endpoint.
    # For n=3 there is only one interior node, so the only same-length near-miss
    # is the full reversal — a distractor that changes exactly ONE endpoint (an
    # interior-swap bug) must never appear.
    arch = identify_pathway(pathway_length=3)
    sk = _skeleton({"r0": "A", "r1": "B", "r2": "C"}, arch.motif)
    key = ["A", "B", "C"]
    for seed_val in range(20):
        for d in arch.recipe.build_distractors(sk, None, Seed(seed_val)):
            moved_start = d.value[0] != key[0]
            moved_end = d.value[-1] != key[-1]
            # Either both endpoints move (a full reversal) or neither — never one.
            assert moved_start == moved_end, d.value


def test_n4_interior_swap_preserves_both_endpoints():
    arch = identify_pathway(pathway_length=4)
    sk = _skeleton({"r0": "A", "r1": "B", "r2": "C", "r3": "D"}, arch.motif)
    for seed_val in range(20):
        for d in arch.recipe.build_distractors(sk, None, Seed(seed_val)):
            if d.value != ["D", "C", "B", "A"]:  # not the reversal → the interior swap
                assert d.value[0] == "A" and d.value[-1] == "D", d.value


def test_distractors_are_deterministic_in_seed():
    arch = identify_pathway(pathway_length=4)
    sk = _skeleton({"r0": "A", "r1": "B", "r2": "C", "r3": "D"}, arch.motif)
    d1 = arch.recipe.build_distractors(sk, None, Seed(7))  # type: ignore[arg-type]
    d2 = arch.recipe.build_distractors(sk, None, Seed(7))  # type: ignore[arg-type]
    assert d1 == d2


def test_recipe_holds_role_order():
    arch = identify_pathway(pathway_length=3)
    assert isinstance(arch.recipe, IdentifyPathwayRecipe)
    assert arch.recipe.role_names == ("r0", "r1", "r2")
