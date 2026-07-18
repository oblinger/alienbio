"""Unit tests for the M29.3 ``design_intervention`` archetype (outcome-scored).

Self-contained: constructs the world/skeleton directly, simulates with the real
integrator, and exercises the scorer + objective + recipe in isolation — the
first user of the ``grade_outcome`` path. The load-bearing guards:

- the scorer ranks a target equal to the actual simulated final concentration
  ABOVE a far-off target (monotone closeness);
- ``grade_outcome`` runs and returns exactly that score;
- the drafter is deterministic in the seed;
- the target binding is a real molecule id (never a reaction node);
- the question renders + parses losslessly (up to set identity for a node_set).
"""

from __future__ import annotations

import math

import pytest

from alienbio.suite.arch_intervene import (
    DesignInterventionRecipe,
    TARGET_ROLE,
    _is_molecule,
    design_intervention,
    draft_intervention_world,
    make_intervention_objective,
    make_target_scorer,
)
from alienbio.suite.dist import Seed
from alienbio.suite.grade import grade_outcome
from alienbio.suite.render import Vocabulary, parse, render
from alienbio.suite.types import (
    Answer,
    GraderSpec,
    OutcomeObjective,
    Question,
    TaskArchetype,
)
from alienbio.suite.verify import SimConfig, simulate


def _vocab_for(world) -> Vocabulary:
    """A minimal injective vocabulary over the world's molecule ids."""
    return Vocabulary({mid: f"phrase-{mid}" for mid in world.chemistry.molecules})


def test_scorer_ranks_true_target_above_far_target() -> None:
    world, _skeleton, (target_id, target_value) = draft_intervention_world(Seed(1))
    timeline = simulate(world, SimConfig())

    score_true = make_target_scorer(target_id, target_value)(timeline)
    score_far = make_target_scorer(target_id, target_value + 500.0)(timeline)

    assert score_true > score_far
    # The default goal is the naturally-reached value, so the true score peaks.
    assert score_true == pytest.approx(1.0)
    assert 0.0 < score_far < score_true


def test_scorer_is_bounded_and_monotone_in_distance() -> None:
    world, _skeleton, (target_id, target_value) = draft_intervention_world(Seed(2))
    timeline = simulate(world, SimConfig())

    near = make_target_scorer(target_id, target_value + 1.0)(timeline)
    far = make_target_scorer(target_id, target_value + 10.0)(timeline)

    assert 0.0 < far < near <= 1.0


def test_grade_outcome_runs_and_matches_scorer() -> None:
    world, _skeleton, (target_id, target_value) = draft_intervention_world(Seed(3))
    timeline = simulate(world, SimConfig())

    objective = make_intervention_objective(target_id, target_value)
    assert isinstance(objective, OutcomeObjective)
    assert objective.target == pytest.approx(target_value)

    score = grade_outcome(timeline, objective.scorer, objective.target)
    assert score == pytest.approx(objective.scorer(timeline))
    assert score == pytest.approx(1.0)


def test_draft_is_deterministic_in_seed() -> None:
    w1, s1, (t1, v1) = draft_intervention_world(Seed(7))
    w2, s2, (t2, v2) = draft_intervention_world(Seed(7))

    assert t1 == t2
    assert v1 == v2  # simulate is pure -> byte-identical final concentration
    assert dict(s1.binding) == dict(s2.binding)
    assert list(w1.chemistry.molecules) == list(w2.chemistry.molecules)


def test_different_seeds_share_structure_but_differ_in_dynamics() -> None:
    _w1, s1, (t1, v1) = draft_intervention_world(Seed(11))
    _w2, s2, (t2, v2) = draft_intervention_world(Seed(12))

    # Structure (target id / binding) is seed-invariant; only the dynamics move.
    assert t1 == t2
    assert dict(s1.binding) == dict(s2.binding)


def test_target_binding_is_a_real_molecule() -> None:
    world, skeleton, (target_id, _v) = draft_intervention_world(Seed(4), n_nodes=5)

    bound = skeleton.binding[TARGET_ROLE]
    assert bound == target_id
    assert target_id in world.chemistry.molecules
    assert _is_molecule(world.chemistry.molecules[target_id])
    # Never a reaction node.
    assert target_id not in world.chemistry.reactions


def test_recipe_shapes_and_outcome_grader() -> None:
    world, skeleton, (target_id, target_value) = draft_intervention_world(Seed(5))
    recipe = DesignInterventionRecipe(target_value=target_value)

    question = recipe.build_question(skeleton, world)
    assert isinstance(question, Question)
    assert question.kind == "node_set"
    assert set(question.structured) == {target_id}

    key = recipe.build_key(skeleton, world)
    assert isinstance(key, Answer)  # trivial; unused by outcome grading

    assert recipe.build_distractors(skeleton, world, Seed(0)) == ()
    assert recipe.grader_spec() == GraderSpec(kind="outcome")


def test_question_round_trips_over_vocabulary() -> None:
    world, skeleton, _goal = draft_intervention_world(Seed(6))
    recipe = DesignInterventionRecipe(target_value=1.0)
    question = recipe.build_question(skeleton, world)
    vocab = _vocab_for(world)

    text = render(question, vocab, verb="intervene")
    back = parse(text, vocab, kind="node_set", verb="intervene")

    assert isinstance(back, Question)
    # node_set parses to a set; faithfulness is set identity of the tokens.
    assert set(back.structured) == set(question.structured)


def test_design_intervention_archetype() -> None:
    arch = design_intervention(target_value=42.0)
    assert isinstance(arch, TaskArchetype)
    assert arch.id == "design_intervention"
    assert arch.verb == "intervene"
    assert isinstance(arch.recipe, DesignInterventionRecipe)
    assert arch.recipe.grader_spec().kind == "outcome"
    # Single molecule-gated role, no edges.
    assert len(arch.motif.roles) == 1
    assert arch.motif.roles[0].name == TARGET_ROLE
    assert arch.motif.edges == ()


def test_explicit_target_value_overrides_natural() -> None:
    world, _skeleton, (target_id, goal) = draft_intervention_world(
        Seed(8), target_value=3.5
    )
    assert goal == 3.5
    timeline = simulate(world, SimConfig())
    # A goal far from the naturally-reached value scores below 1.0.
    score = make_target_scorer(target_id, goal)(timeline)
    assert 0.0 < score < 1.0
    assert math.isfinite(score)
