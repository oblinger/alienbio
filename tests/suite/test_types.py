"""Acceptance tests for the neutral suite types (graph queries + immutability)."""

from __future__ import annotations

import dataclasses

import pytest

from alienbio.suite.types import Reaction, ReactionNetwork, Species


def build_net() -> ReactionNetwork:
    """A synthetic 6-node network: 4 species + 2 reactions.

    Structure:  A + B --R1--> C ,  C --R2--> D
    Tags:  A,B = substrate ; C = intermediate ; D = product
    """
    species = {
        "A": Species("A", {"role": "substrate"}),
        "B": Species("B", {"role": "substrate"}),
        "C": Species("C", {"role": "intermediate"}),
        "D": Species("D", {"role": "product"}),
    }
    reactions = {
        "R1": Reaction("R1", reactants=(("A", 1), ("B", 1)), products=(("C", 1),)),
        "R2": Reaction("R2", reactants=(("C", 1),), products=(("D", 1),)),
    }
    return ReactionNetwork(species=species, reactions=reactions)


def test_neighbors_bipartite():
    net = build_net()
    assert net.neighbors("A") == {"R1"}
    assert net.neighbors("B") == {"R1"}
    assert net.neighbors("C") == {"R1", "R2"}
    assert net.neighbors("D") == {"R2"}
    assert net.neighbors("R1") == {"A", "B", "C"}
    assert net.neighbors("R2") == {"C", "D"}


def test_paths():
    net = build_net()
    paths = net.paths("A", "D")
    assert paths == [["A", "R1", "C", "R2", "D"]]

    # a == b is a trivial single-node path
    assert net.paths("A", "A") == [["A"]]

    # No path within a too-small edge budget.
    assert net.paths("A", "D", max_len=2) == []


def test_subgraph_induced():
    net = build_net()
    sub = net.subgraph({"A", "B", "R1"})
    assert set(sub.species.keys()) == {"A", "B"}
    assert set(sub.reactions.keys()) == {"R1"}
    r1 = sub.reactions["R1"]
    # C dropped from products (not in the induced node set); reactants kept.
    assert r1.reactants == (("A", 1), ("B", 1))
    assert r1.products == ()


def test_match_embeddings_and_tag_filter():
    net = build_net()
    # Pattern: one substrate species feeding one reaction.
    pattern = ReactionNetwork(
        species={"s": Species("s", {"role": "substrate"})},
        reactions={"r": Reaction("r", reactants=(("s", 1),))},
    )
    embeddings = net.match(pattern)
    got = {(m["s"], m["r"]) for m in embeddings}
    # Both substrates A and B feed R1 (C is an intermediate -> filtered out).
    assert got == {("A", "R1"), ("B", "R1")}

    # A pattern whose tag matches no host species yields no embeddings.
    no_match = ReactionNetwork(
        species={"s": Species("s", {"role": "nonexistent"})},
        reactions={"r": Reaction("r", reactants=(("s", 1),))},
    )
    assert net.match(no_match) == []


def test_frozen_mutation_raises():
    sp = Species("A", {"role": "substrate"})
    with pytest.raises(dataclasses.FrozenInstanceError):
        sp.id = "B"  # type: ignore[misc]

    net = build_net()
    with pytest.raises(dataclasses.FrozenInstanceError):
        net.species = {}  # type: ignore[misc]
