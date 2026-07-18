"""Acceptance tests for the deterministic NL rendering engine.

The load-bearing property is a lossless round-trip over a fixed vocabulary:
``parse(render(x), ...) == x`` for every supported ``kind``, for both
:class:`Answer` and :class:`Question`.
"""

from __future__ import annotations

import pytest

from alienbio.suite.render import EMPTY, SEP, Vocabulary, parse, render
from alienbio.suite.types import Answer, Question


def build_vocab() -> Vocabulary:
    """A small synthetic controlled vocabulary (injective phrases)."""
    return Vocabulary(
        {
            "n0": "the red node",
            "n1": "the blue node",
            "n2": "the green node",
            "n3": "the yellow node",
        }
    )


# ── 1. Round-trip across all kinds (answers + questions) ────────────────────


def _round_trip(x):
    vocab = build_vocab()
    as_answer = isinstance(x, Answer)
    text = render(x, vocab)
    back = parse(text, vocab, kind=x.kind, as_answer=as_answer)
    assert back == x


def test_round_trip_answer_node_id():
    _round_trip(Answer(value="n0", kind="node_id"))


def test_round_trip_answer_node_set():
    _round_trip(Answer(value={"n0", "n2", "n3"}, kind="node_set"))


def test_round_trip_answer_node_set_empty():
    _round_trip(Answer(value=set(), kind="node_set"))


def test_round_trip_answer_ordered_path():
    _round_trip(Answer(value=["n2", "n0", "n1", "n0"], kind="ordered_path"))


def test_round_trip_answer_ordered_path_empty():
    _round_trip(Answer(value=[], kind="ordered_path"))


def test_round_trip_answer_scalar_int():
    _round_trip(Answer(value=42, kind="scalar"))


def test_round_trip_answer_scalar_float():
    _round_trip(Answer(value=3.14, kind="scalar"))


def test_round_trip_answer_json():
    _round_trip(
        Answer(value={"b": [1, 2, 3], "a": {"x": True, "y": None}}, kind="json")
    )


def test_round_trip_question_node_id():
    _round_trip(Question(structured="n1", kind="node_id"))


def test_round_trip_question_node_set():
    _round_trip(Question(structured={"n1", "n3"}, kind="node_set"))


def test_round_trip_question_ordered_path():
    _round_trip(Question(structured=["n0", "n3"], kind="ordered_path"))


def test_round_trip_question_scalar():
    _round_trip(Question(structured=7, kind="scalar"))


def test_round_trip_question_json():
    _round_trip(Question(structured=[{"k": 1}, "s", False], kind="json"))


# ── 2. Determinism (byte-identical repeats) ─────────────────────────────────


def test_determinism_across_kinds():
    vocab = build_vocab()
    nodes = [
        Answer(value="n0", kind="node_id"),
        Answer(value={"n0", "n1", "n2"}, kind="node_set"),
        Answer(value=["n2", "n1", "n0"], kind="ordered_path"),
        Answer(value=1.5, kind="scalar"),
        Answer(value={"z": 1, "a": 2}, kind="json"),
        Question(structured={"n3", "n0"}, kind="node_set"),
    ]
    for x in nodes:
        first = render(x, vocab)
        assert first == render(x, vocab)


def test_node_set_order_independent_output():
    """A set renders identically regardless of insertion order (sorted)."""
    vocab = build_vocab()
    a = render(Answer(value={"n0", "n1", "n2"}, kind="node_set"), vocab)
    b = render(Answer(value={"n2", "n1", "n0"}, kind="node_set"), vocab)
    assert a == b


# ── 3. Missing vocabulary entry raises (render + parse) ─────────────────────


def test_render_missing_token_raises():
    vocab = build_vocab()
    with pytest.raises(KeyError):
        render(Answer(value="UNKNOWN", kind="node_id"), vocab)
    with pytest.raises(KeyError):
        render(Answer(value={"n0", "UNKNOWN"}, kind="node_set"), vocab)


def test_parse_unknown_phrase_raises():
    vocab = build_vocab()
    with pytest.raises(ValueError):
        parse("The node is the purple node.", vocab, kind="node_id", as_answer=True)
    with pytest.raises(ValueError):
        parse(
            f"The nodes are: the red node{SEP}the purple node.",
            vocab,
            kind="node_set",
            as_answer=True,
        )


def test_parse_malformed_template_raises():
    vocab = build_vocab()
    with pytest.raises(ValueError):
        parse("nonsense text", vocab, kind="node_id", as_answer=True)


# ── 4. Injectivity + reserved-lexeme guards ─────────────────────────────────


def test_non_injective_vocabulary_rejected():
    with pytest.raises(ValueError):
        Vocabulary({"n0": "the same node", "n1": "the same node"})


def test_phrase_containing_separator_rejected():
    with pytest.raises(ValueError):
        Vocabulary({"n0": f"the red{SEP}node"})


def test_phrase_equal_to_empty_sentinel_rejected():
    with pytest.raises(ValueError):
        Vocabulary({"n0": EMPTY})


# ── extras: no LLM/network deps, template separation ────────────────────────


def test_answer_and_question_templates_distinct():
    vocab = build_vocab()
    ans_text = render(Answer(value="n0", kind="node_id"), vocab)
    q_text = render(Question(structured="n0", kind="node_id"), vocab)
    assert ans_text != q_text
    # Parsing an answer's text as a question must fail (wrong template).
    with pytest.raises(ValueError):
        parse(ans_text, vocab, kind="node_id", as_answer=False)


# ── 5. Verb-framed question templates (M27.2) ───────────────────────────────


def test_verb_selects_discovery_framing():
    vocab = build_vocab()
    q = Question(structured=["n0", "n2"], kind="ordered_path")
    framed = render(q, vocab, verb="identify")
    generic = render(q, vocab)
    assert framed.startswith("Which pathway connects: ")
    assert framed != generic  # the verb changed the framing


def test_verb_question_round_trips_with_same_verb():
    vocab = build_vocab()
    q = Question(structured=["n0", "n1", "n2"], kind="ordered_path")
    text = render(q, vocab, verb="identify")
    back = parse(text, vocab, kind="ordered_path", as_answer=False, verb="identify")
    assert back == q


def test_unknown_verb_falls_back_to_generic_template():
    vocab = build_vocab()
    q = Question(structured=["n0", "n1"], kind="ordered_path")
    assert render(q, vocab, verb="no_such_verb") == render(q, vocab)


def test_verb_ignored_for_answers():
    vocab = build_vocab()
    a = Answer(value=["n0", "n1"], kind="ordered_path")
    assert render(a, vocab, verb="identify") == render(a, vocab)


def test_verb_framed_text_does_not_parse_as_generic():
    vocab = build_vocab()
    q = Question(structured=["n0", "n2"], kind="ordered_path")
    framed = render(q, vocab, verb="identify")
    # Parsing verb-framed text without the verb must fail (template mismatch).
    with pytest.raises(ValueError):
        parse(framed, vocab, kind="ordered_path", as_answer=False)
