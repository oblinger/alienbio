"""Tests for M27.2 — ``build_vocabulary`` (controlled vocabularies for FT08).

A vocabulary is a per-world, seed-deterministic, injective ``token -> phrase``
map over the world's node namespace. The load-bearing properties: it covers
every node, it is a bijection (so FT08's ``parse(render(x)) == x`` still holds),
and it is deterministic in ``(nodes, seed)``.
"""

from __future__ import annotations

from alienbio.bio.chemistry import ChemistryImpl
from alienbio.bio.molecule import MoleculeImpl
from alienbio.bio.reaction import ReactionImpl
from alienbio.bio.world import Compartment, WorldImpl
from alienbio.infra.entity import MockDat
from alienbio.suite.dist import Seed
from alienbio.suite.render import parse, render
from alienbio.suite.types import Answer
from alienbio.suite.vocab import build_vocabulary

_TOKENS = ("A", "B", "C", "R1", "R2")


def _world() -> WorldImpl:
    a = MoleculeImpl("A", name="A", dat=MockDat("mol/A"))
    b = MoleculeImpl("B", name="B", dat=MockDat("mol/B"))
    c = MoleculeImpl("C", name="C", dat=MockDat("mol/C"))
    r1 = ReactionImpl(
        "R1", reactants={a: 1.0}, products={b: 1.0}, rate=0.1, dat=MockDat("rxn/R1")
    )
    r2 = ReactionImpl(
        "R2", reactants={b: 1.0}, products={c: 1.0}, rate=0.1, dat=MockDat("rxn/R2")
    )
    chem = ChemistryImpl(
        "world",
        molecules={"A": a, "B": b, "C": c},
        reactions={"R1": r1, "R2": r2},
        dat=MockDat("chem/world"),
    )
    comps = (
        Compartment("cell", None, "cell", 1.0, concentrations={"A": 10.0, "B": 0.0, "C": 0.0}),
    )
    return WorldImpl(chem, comps)


def test_covers_all_nodes():
    vocab = build_vocabulary(_world())
    for token in _TOKENS:
        assert vocab.phrase_for(token)  # no KeyError => token is mapped


def test_injective_and_roundtrips_each_token():
    vocab = build_vocabulary(_world())
    phrases = [vocab.phrase_for(t) for t in _TOKENS]
    assert len(set(phrases)) == len(phrases)  # distinct phrases (bijection)
    for t in _TOKENS:
        assert vocab.token_for(vocab.phrase_for(t)) == t


def test_deterministic_in_seed():
    p1 = {t: build_vocabulary(_world(), seed=Seed(7)).phrase_for(t) for t in _TOKENS}
    p2 = {t: build_vocabulary(_world(), seed=Seed(7)).phrase_for(t) for t in _TOKENS}
    assert p1 == p2


def test_different_seed_varies_phrases():
    p1 = {t: build_vocabulary(_world(), seed=Seed(1)).phrase_for(t) for t in _TOKENS}
    p2 = {t: build_vocabulary(_world(), seed=Seed(2)).phrase_for(t) for t in _TOKENS}
    assert p1 != p2


def test_render_parse_roundtrip_node_set():
    vocab = build_vocabulary(_world())
    ans = Answer(value={"A", "C"}, kind="node_set")
    back = parse(render(ans, vocab), vocab, kind="node_set", as_answer=True)
    assert back == ans


def test_render_parse_roundtrip_ordered_path():
    vocab = build_vocabulary(_world())
    ans = Answer(value=["A", "B", "C"], kind="ordered_path")
    back = parse(render(ans, vocab), vocab, kind="ordered_path", as_answer=True)
    assert back == ans
