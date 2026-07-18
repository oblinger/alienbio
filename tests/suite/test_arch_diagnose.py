"""Unit tests for the ``diagnose_perturbation`` archetype (M29.2).

Fully self-contained: constructs worlds/skeletons directly via
:func:`draft_diagnosis_world`, exercises the recipe methods + grading, and
asserts the ground-truth guards (key is a real molecule id, self-grades to 1.0,
round-trips through render/parse, distractors are real molecules that grade
below 1.0, and target selection is seed-deterministic).
"""

from __future__ import annotations

from alienbio.suite.arch_diagnose import (
    DiagnosePerturbationRecipe,
    diagnose_perturbation,
    draft_diagnosis_world,
)
from alienbio.suite.dist import Seed
from alienbio.suite.grade import grade_answer
from alienbio.suite.render import Vocabulary, parse, render
from alienbio.suite.types import Skeleton, TaskArchetype


def _vocab(world) -> Vocabulary:
    """A trivial injective vocabulary over every molecule id in ``world``."""
    return Vocabulary({mid: mid.upper() for mid in world.chemistry.molecules})


def test_build_key_reads_target_off_skeleton() -> None:
    world, skeleton = draft_diagnosis_world(Seed(0), n_nodes=4)
    recipe = DiagnosePerturbationRecipe()
    key = recipe.build_key(skeleton, world)
    assert key.kind == "node_id"
    assert key.value == skeleton.binding["target"]


def test_key_is_a_real_molecule_not_a_reaction() -> None:
    world, skeleton = draft_diagnosis_world(Seed(3), n_nodes=4)
    recipe = DiagnosePerturbationRecipe()
    key = recipe.build_key(skeleton, world)
    # The key must be a real molecule id, never a reaction id.
    assert key.value in world.chemistry.molecules
    assert key.value not in world.chemistry.reactions


def test_key_self_grades_to_one() -> None:
    world, skeleton = draft_diagnosis_world(Seed(1), n_nodes=5)
    recipe = DiagnosePerturbationRecipe()
    key = recipe.build_key(skeleton, world)
    assert grade_answer(key, key, recipe.grader_spec()) == 1.0


def test_key_round_trips_through_render_parse() -> None:
    world, skeleton = draft_diagnosis_world(Seed(2), n_nodes=4)
    recipe = DiagnosePerturbationRecipe()
    key = recipe.build_key(skeleton, world)
    vocab = _vocab(world)
    back = parse(render(key, vocab), vocab, kind=key.kind, as_answer=True)
    assert back == key


def test_distractors_are_real_molecules_distinct_from_key() -> None:
    world, skeleton = draft_diagnosis_world(Seed(4), n_nodes=4, distractor_count=2)
    recipe = DiagnosePerturbationRecipe()
    key = recipe.build_key(skeleton, world)
    distractors = recipe.build_distractors(skeleton, world, Seed(0))

    assert distractors, "expected a non-empty distractor set for n_nodes>1"
    values = [d.value for d in distractors]
    assert len(values) == len(set(values)), "distractors must be distinct"
    for d in distractors:
        assert d.kind == "node_id"
        assert d.value != key.value
        assert d.value in world.chemistry.molecules
        assert d.value not in world.chemistry.reactions
        # A wrong node grades strictly below a correct one.
        assert grade_answer(d, key, recipe.grader_spec()) < 1.0


def test_question_presents_full_candidate_set() -> None:
    world, skeleton = draft_diagnosis_world(Seed(5), n_nodes=3, distractor_count=1)
    recipe = DiagnosePerturbationRecipe()
    q = recipe.build_question(skeleton, world)
    assert q.kind == "node_set"
    assert q.structured == set(world.chemistry.molecules)  # a set (round-trippable)
    # The chosen target is among the candidates presented.
    assert skeleton.binding["target"] in q.structured


def test_target_selection_is_seed_deterministic() -> None:
    a1, s1 = draft_diagnosis_world(Seed(7), n_nodes=6)
    a2, s2 = draft_diagnosis_world(Seed(7), n_nodes=6)
    assert s1.binding == s2.binding
    del a1, a2

    # Different seeds can (and across a range, do) select different targets.
    seen = {
        draft_diagnosis_world(Seed(k), n_nodes=6)[1].binding["target"]
        for k in range(20)
    }
    assert len(seen) > 1, "target selection should vary with the seed"


def test_draft_produces_directly_built_one_role_skeleton() -> None:
    world, skeleton = draft_diagnosis_world(Seed(0), n_nodes=4)
    assert isinstance(skeleton, Skeleton)
    assert tuple(r.name for r in skeleton.motif.roles) == ("target",)
    assert skeleton.motif.roles[0].type_tag == "perturbed_node"
    # Constructed directly — no carve, so no synthesized nodes / removals.
    assert skeleton.added == ()
    assert skeleton.removed == ()
    assert set(skeleton.binding) == {"target"}


def test_archetype_factory_shape() -> None:
    arch = diagnose_perturbation(n_nodes=4)
    assert isinstance(arch, TaskArchetype)
    assert arch.id == "diagnose_perturbation"
    assert arch.verb == "diagnose"
    assert len(arch.motif.roles) == 1
    assert arch.motif.roles[0].name == "target"
    assert isinstance(arch.recipe, DiagnosePerturbationRecipe)


def test_recipe_end_to_end_via_archetype() -> None:
    # The archetype's own recipe grades the drafted skeleton's key at 1.0 and
    # rejects the first distractor.
    world, skeleton = draft_diagnosis_world(Seed(11), n_nodes=4)
    arch = diagnose_perturbation(n_nodes=4)
    recipe = arch.recipe
    key = recipe.build_key(skeleton, world)
    assert grade_answer(key, key, recipe.grader_spec()) == 1.0
    distractors = recipe.build_distractors(skeleton, world, Seed(1))
    assert grade_answer(distractors[0], key, recipe.grader_spec()) < 1.0


def test_diagnosis_node_set_question_round_trips():
    """Regression (audit F2): a ``node_set`` question must be a set, not a list —
    ``parse`` returns a set, so a list fails the pipeline guard ``parse(render(q)) == q``."""
    from alienbio.suite.vocab import build_vocabulary

    world, skeleton = draft_diagnosis_world(Seed(3), n_nodes=4)
    q = DiagnosePerturbationRecipe().build_question(skeleton, world)
    assert isinstance(q.structured, set)
    vocab = build_vocabulary(world)
    back = parse(render(q, vocab, verb="diagnose"), vocab, kind="node_set", verb="diagnose")
    assert back == q
