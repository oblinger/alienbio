"""Unit tests for the ``predict_response`` archetype (M29.4).

Fully self-contained: constructs worlds/skeletons directly via
:func:`draft_prediction_world`, independently recomputes the simulated response,
exercises the recipe methods + grading, and asserts the ground-truth guards
(the key equals the independently-simulated response, is deterministic in seed,
self-grades to 1.0, round-trips through render/parse, and the three response
tokens are distinct and never node ids).
"""

from __future__ import annotations

import importlib

from alienbio.suite.arch_predict import (
    DEFAULT_FACTOR,
    RESPONSE_TOKENS,
    PredictResponseRecipe,
    draft_prediction_world,
    predict_response,
    predicted_response,
)
from alienbio.suite.dist import Seed
from alienbio.suite.grade import grade_answer
from alienbio.suite.render import Vocabulary, parse, render
from alienbio.suite.types import CarveResult, TaskArchetype

# The verb template the orchestrator will splice into render._VERB_TEMPLATES at
# integration; register it here so the verb-framed question round-trip is exercised
# against the real template rather than the generic fallback.
render_mod = importlib.import_module("alienbio.suite.render")
render_mod._VERB_TEMPLATES.setdefault(
    ("predict", "node_set"),
    ("Given the perturbation of: ", ", predict the response?"),
)


def _recipe(reaction_id: str, target_id: str) -> PredictResponseRecipe:
    return PredictResponseRecipe(reaction_id=reaction_id, target_id=target_id)


def _vocab(world, extra: dict[str, str]) -> Vocabulary:
    """Injective vocabulary over every molecule + reaction id, plus ``extra`` tokens."""
    phrases: dict[str, str] = {}
    for mid in world.chemistry.molecules:
        phrases[mid] = f"MOL_{mid}"
    for rid in world.chemistry.reactions:
        phrases[rid] = f"RXN_{rid}"
    phrases.update(extra)
    return Vocabulary(phrases)


def _response_vocab() -> dict[str, str]:
    return {tok: f"RESP_{tok}" for tok in RESPONSE_TOKENS}


def test_key_equals_independently_simulated_response() -> None:
    world, skeleton, reaction_id = draft_prediction_world(Seed(0), n_nodes=4)
    target_id = skeleton.binding["target"]
    recipe = _recipe(reaction_id, target_id)

    key = recipe.build_key(skeleton, world)
    expected = predicted_response(
        world, target_id, reaction_id, DEFAULT_FACTOR, recipe.sim_cfg, recipe.seed
    )
    assert key.kind == "node_id"
    assert key.value == expected


def test_response_token_is_one_of_the_three() -> None:
    world, skeleton, reaction_id = draft_prediction_world(Seed(4), n_nodes=5)
    key = _recipe(reaction_id, skeleton.binding["target"]).build_key(skeleton, world)
    assert key.value in RESPONSE_TOKENS


def test_speeding_the_throttle_raises_the_sink() -> None:
    # Speeding the first reaction on a monotonic terminal sink moves more mass
    # downstream by the final time -> the sink goes "up".
    world, skeleton, reaction_id = draft_prediction_world(Seed(1), n_nodes=4)
    key = _recipe(reaction_id, skeleton.binding["target"]).build_key(skeleton, world)
    assert key.value == "up"


def test_response_is_deterministic_in_seed() -> None:
    # Same seed -> identical structure -> identical response.
    w1, s1, r1 = draft_prediction_world(Seed(9), n_nodes=4)
    w2, s2, r2 = draft_prediction_world(Seed(9), n_nodes=4)
    assert s1.binding == s2.binding and r1 == r2

    t1 = predicted_response(w1, s1.binding["target"], r1, DEFAULT_FACTOR)
    t2 = predicted_response(w2, s2.binding["target"], r2, DEFAULT_FACTOR)
    assert t1 == t2

    # Repeated calls on the same world are also stable.
    again = predicted_response(w1, s1.binding["target"], r1, DEFAULT_FACTOR)
    assert again == t1


def test_key_self_grades_to_one() -> None:
    world, skeleton, reaction_id = draft_prediction_world(Seed(2), n_nodes=4)
    recipe = _recipe(reaction_id, skeleton.binding["target"])
    key = recipe.build_key(skeleton, world)
    assert grade_answer(key, key, recipe.grader_spec()) == 1.0


def test_key_round_trips_through_render_parse() -> None:
    world, skeleton, reaction_id = draft_prediction_world(Seed(3), n_nodes=4)
    recipe = _recipe(reaction_id, skeleton.binding["target"])
    key = recipe.build_key(skeleton, world)
    vocab = _vocab(world, _response_vocab())
    back = parse(render(key, vocab), vocab, kind=key.kind, as_answer=True)
    assert back == key


def test_question_round_trips_with_verb_framing() -> None:
    world, skeleton, reaction_id = draft_prediction_world(Seed(5), n_nodes=4)
    recipe = _recipe(reaction_id, skeleton.binding["target"])
    q = recipe.build_question(skeleton, world)
    assert q.kind == "node_set"
    assert set(q.structured) == {reaction_id, skeleton.binding["target"]}

    vocab = _vocab(world, _response_vocab())
    text = render(q, vocab, verb=recipe.verb)
    assert text.startswith("Given the perturbation of: ")
    back = parse(text, vocab, kind=q.kind, as_answer=False, verb=recipe.verb)
    assert back == q


def test_three_response_tokens_are_distinct() -> None:
    assert len(set(RESPONSE_TOKENS)) == 3
    assert set(RESPONSE_TOKENS) == {"up", "down", "same"}


def test_binding_records_reaction_and_molecule_not_swapped() -> None:
    world, skeleton, reaction_id = draft_prediction_world(Seed(7), n_nodes=4)
    perturbed = skeleton.binding["perturbed"]
    target = skeleton.binding["target"]
    # The perturbed role holds a real reaction; the target role a real molecule —
    # never crossed (the audited corruption).
    assert perturbed in world.chemistry.reactions
    assert perturbed not in world.chemistry.molecules
    assert target in world.chemistry.molecules
    assert target not in world.chemistry.reactions
    assert reaction_id == perturbed


def test_draft_produces_directly_built_two_role_skeleton() -> None:
    world, skeleton, _ = draft_prediction_world(Seed(0), n_nodes=4)
    del world
    assert isinstance(skeleton, CarveResult)
    assert set(r.name for r in skeleton.motif.roles) == {"perturbed", "target"}
    assert skeleton.added == ()
    assert skeleton.removed == ()
    assert set(skeleton.binding) == {"perturbed", "target"}


def test_predict_key_renders_only_with_response_tokens_in_vocab():
    """Regression (audit F1): up/down/same are not world nodes, so the key renders
    only when build_vocabulary is given them via extra_tokens — and fails loudly
    (KeyError) otherwise, which is exactly what the pipeline guard would hit."""
    import pytest

    from alienbio.suite.vocab import build_vocabulary

    world, skeleton, rid = draft_prediction_world(Seed(0), n_nodes=4)
    recipe = PredictResponseRecipe(reaction_id=rid, target_id=skeleton.binding["target"])
    key = recipe.build_key(skeleton, world)
    assert key.value in RESPONSE_TOKENS

    vocab = build_vocabulary(world, extra_tokens=RESPONSE_TOKENS)
    back = parse(render(key, vocab), vocab, kind="node_id", as_answer=True)
    assert back == key

    with pytest.raises(KeyError):
        render(key, build_vocabulary(world))  # tokens absent -> loud failure
