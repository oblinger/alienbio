"""Graph queries on ``ChemistryImpl`` (F007 — biological absorption, PR #1).

The unified protocol model folds the (now-retired) neutral ``ReactionNetwork``'s
graph-query surface (``neighbors`` / ``paths`` / ``subgraph`` / ``match``) onto
the biology ``Chemistry`` container, delegating to the single shared algorithm
in ``alienbio.infra.graph_ops``.

These tests pin exact golden literals for ``neighbors`` / ``paths`` / ``subgraph``
/ ``match`` directly on ``Chemistry`` — one per node / pair / node-set — so a
future edit that drifts the query results is caught immediately.
"""

from __future__ import annotations

from typing import Dict

import pytest

from alienbio.bio.atom import AtomImpl
from alienbio.bio.chemistry import ChemistryImpl
from alienbio.bio.molecule import MoleculeImpl
from alienbio.bio.reaction import ReactionImpl
from alienbio.infra.entity import MockDat


# ─────────────────────────────────────────────────────────────────────────────
# Fixture: a small, real metabolic chemistry
#
#   hexokinase:  glucose + atp -> g6p + adp   (rate 0.3)
#   isomerase:   g6p -> pyruvate              (rate 0.5)
#
# Node namespace (by name):
#   species   = glucose, g6p, pyruvate, atp, adp
#   reactions = hexokinase, isomerase
# ─────────────────────────────────────────────────────────────────────────────


def _mol(name: str, atoms: Dict[AtomImpl, int], bdepth: int) -> MoleculeImpl:
    return MoleculeImpl(name, dat=MockDat(f"mol/{name}"), atoms=atoms, bdepth=bdepth, name=name)


@pytest.fixture
def chem() -> ChemistryImpl:
    C = AtomImpl("C", "Carbon", 12.011)
    H = AtomImpl("H", "Hydrogen", 1.008)
    O = AtomImpl("O", "Oxygen", 15.999)
    N = AtomImpl("N", "Nitrogen", 14.007)
    P = AtomImpl("P", "Phosphorus", 30.974)

    glucose = _mol("glucose", {C: 6, H: 12, O: 6}, bdepth=2)
    g6p = _mol("g6p", {C: 6, H: 13, O: 9, P: 1}, bdepth=3)
    pyruvate = _mol("pyruvate", {C: 3, H: 4, O: 3}, bdepth=3)
    atp = _mol("atp", {C: 10, H: 16, N: 5, O: 13, P: 3}, bdepth=4)
    adp = _mol("adp", {C: 10, H: 15, N: 5, O: 10, P: 2}, bdepth=4)

    hexokinase = ReactionImpl(
        "hexokinase",
        reactants={glucose: 1, atp: 1},
        products={g6p: 1, adp: 1},
        rate=0.3,
        dat=MockDat("rxn/hexokinase"),
    )
    isomerase = ReactionImpl(
        "isomerase",
        reactants={g6p: 1},
        products={pyruvate: 1},
        rate=0.5,
        dat=MockDat("rxn/isomerase"),
    )

    return ChemistryImpl(
        "glycolysis",
        atoms={"C": C, "H": H, "O": O, "N": N, "P": P},
        molecules={
            "glucose": glucose,
            "g6p": g6p,
            "pyruvate": pyruvate,
            "atp": atp,
            "adp": adp,
        },
        reactions={"hexokinase": hexokinase, "isomerase": isomerase},
        dat=MockDat("chem/glycolysis"),
    )


def _all_nodes(chem: ChemistryImpl) -> list[str]:
    return [m.name for m in chem.molecules.values()] + [
        r.name for r in chem.reactions.values()
    ]


# ─────────────────────────────────────────────────────────────────────────────
# neighbors
# ─────────────────────────────────────────────────────────────────────────────


def test_neighbors_golden(chem: ChemistryImpl) -> None:
    assert chem.neighbors("glucose") == {"hexokinase"}
    assert chem.neighbors("g6p") == {"hexokinase", "isomerase"}
    assert chem.neighbors("hexokinase") == {"glucose", "atp", "g6p", "adp"}
    assert chem.neighbors("isomerase") == {"g6p", "pyruvate"}
    assert chem.neighbors("pyruvate") == {"isomerase"}
    # A node in neither namespace has no neighbors.
    assert chem.neighbors("nonexistent") == set()


def test_neighbors_exhaustive_golden(chem: ChemistryImpl) -> None:
    """``neighbors`` pinned for every node in the fixture, not just a sample."""
    expected = {
        "glucose": {"hexokinase"},
        "g6p": {"hexokinase", "isomerase"},
        "pyruvate": {"isomerase"},
        "atp": {"hexokinase"},
        "adp": {"hexokinase"},
        "hexokinase": {"glucose", "atp", "g6p", "adp"},
        "isomerase": {"g6p", "pyruvate"},
    }
    for node in _all_nodes(chem):
        assert chem.neighbors(node) == expected[node], node


# ─────────────────────────────────────────────────────────────────────────────
# paths
# ─────────────────────────────────────────────────────────────────────────────


def test_paths_golden(chem: ChemistryImpl) -> None:
    assert chem.paths("glucose", "glucose") == [["glucose"]]
    assert chem.paths("glucose", "pyruvate") == [
        ["glucose", "hexokinase", "g6p", "isomerase", "pyruvate"]
    ]
    # Unreachable within the edge budget.
    assert chem.paths("glucose", "pyruvate", max_len=2) == []


def test_paths_exhaustive_golden(chem: ChemistryImpl) -> None:
    """``paths`` pinned for several a/b pairs beyond the single golden case above."""
    expected = {
        ("glucose", "pyruvate"): [
            ["glucose", "hexokinase", "g6p", "isomerase", "pyruvate"]
        ],
        ("atp", "adp"): [["atp", "hexokinase", "adp"]],
        ("glucose", "adp"): [["glucose", "hexokinase", "adp"]],
        ("pyruvate", "glucose"): [
            ["pyruvate", "isomerase", "g6p", "hexokinase", "glucose"]
        ],
        ("g6p", "g6p"): [["g6p"]],
    }
    for (a, b), want in expected.items():
        assert chem.paths(a, b) == want, (a, b)


# ─────────────────────────────────────────────────────────────────────────────
# subgraph
# ─────────────────────────────────────────────────────────────────────────────


def test_subgraph_golden(chem: ChemistryImpl) -> None:
    # Drop isomerase + pyruvate; hexokinase and its four endpoints survive.
    sub = chem.subgraph({"glucose", "atp", "g6p", "adp", "hexokinase"})
    assert set(sub.molecules) == {"glucose", "atp", "g6p", "adp"}
    assert set(sub.reactions) == {"hexokinase"}
    # The surviving reaction keeps all four endpoints (none were dropped).
    hk = sub.reactions["hexokinase"]
    assert {m.name for m in hk.reactants} == {"glucose", "atp"}
    assert {m.name for m in hk.products} == {"g6p", "adp"}
    # Atoms are retained (not graph nodes).
    assert set(sub.atoms) == set(chem.atoms)


def test_subgraph_drops_edges_to_removed_nodes(chem: ChemistryImpl) -> None:
    # Keep hexokinase but drop adp: the reaction survives with adp filtered out.
    sub = chem.subgraph({"glucose", "atp", "g6p", "hexokinase"})
    hk = sub.reactions["hexokinase"]
    assert {m.name for m in hk.reactants} == {"glucose", "atp"}
    assert {m.name for m in hk.products} == {"g6p"}  # adp edge removed


def _rxn_shape(sub: ChemistryImpl) -> dict[str, tuple[tuple, tuple]]:
    """Molecule-name reactant/product pairs for every surviving reaction."""
    return {
        rid: (
            tuple(sorted((m.name, s) for m, s in rxn.reactants.items())),
            tuple(sorted((m.name, s) for m, s in rxn.products.items())),
        )
        for rid, rxn in sub.reactions.items()
    }


def test_subgraph_exhaustive_golden(chem: ChemistryImpl) -> None:
    """``subgraph`` pinned for several node-sets beyond the two golden cases above."""
    nodes = {"glucose", "atp", "g6p", "adp", "hexokinase"}
    sub = chem.subgraph(nodes)
    assert sorted(sub.molecules) == ["adp", "atp", "g6p", "glucose"]
    assert _rxn_shape(sub) == {
        "hexokinase": ((("atp", 1), ("glucose", 1)), (("adp", 1), ("g6p", 1)))
    }

    nodes = {"glucose", "atp", "g6p", "hexokinase"}  # drops an endpoint (adp)
    sub = chem.subgraph(nodes)
    assert sorted(sub.molecules) == ["atp", "g6p", "glucose"]
    assert _rxn_shape(sub) == {
        "hexokinase": ((("atp", 1), ("glucose", 1)), (("g6p", 1),))
    }

    nodes = {"g6p", "pyruvate", "isomerase"}
    sub = chem.subgraph(nodes)
    assert sorted(sub.molecules) == ["g6p", "pyruvate"]
    assert _rxn_shape(sub) == {"isomerase": ((("g6p", 1),), (("pyruvate", 1),))}

    nodes = {"glucose", "g6p", "pyruvate"}  # species only, no reactions
    sub = chem.subgraph(nodes)
    assert sorted(sub.molecules) == ["g6p", "glucose", "pyruvate"]
    assert _rxn_shape(sub) == {}


def test_subgraph_carries_rate_through(chem: ChemistryImpl) -> None:
    sub = chem.subgraph({"g6p", "pyruvate", "isomerase"})
    assert sub.reactions["isomerase"].rate == 0.5


# ─────────────────────────────────────────────────────────────────────────────
# match
# ─────────────────────────────────────────────────────────────────────────────


def test_match_golden_single_embedding(chem: ChemistryImpl) -> None:
    # Pattern: glucose + atp -> (via a reaction) — a sub-shape of hexokinase.
    pattern = chem.subgraph({"glucose", "atp", "hexokinase"})
    embeddings = chem.match(pattern)
    assert embeddings == [
        {"glucose": "glucose", "atp": "atp", "hexokinase": "hexokinase"}
    ]


def test_match_isomerase_shape(chem: ChemistryImpl) -> None:
    pattern = chem.subgraph({"g6p", "pyruvate", "isomerase"})
    embeddings = chem.match(pattern)
    # g6p<->isomerase<->pyruvate embeds uniquely (isomerase is the only reaction
    # adjacent to both g6p and pyruvate).
    assert embeddings == [
        {"g6p": "g6p", "pyruvate": "pyruvate", "isomerase": "isomerase"}
    ]


def test_match_exhaustive_golden(chem: ChemistryImpl) -> None:
    """``match`` pinned for several patterns beyond the two golden cases above."""
    pattern = chem.subgraph({"glucose", "atp", "hexokinase"})
    assert chem.match(pattern) == [
        {"glucose": "glucose", "atp": "atp", "hexokinase": "hexokinase"}
    ]

    pattern = chem.subgraph({"g6p", "pyruvate", "isomerase"})
    assert chem.match(pattern) == [
        {"g6p": "g6p", "pyruvate": "pyruvate", "isomerase": "isomerase"}
    ]

    # A single-reaction pattern embeds at BOTH reactions (each touches g6p).
    pattern = chem.subgraph({"g6p", "hexokinase"})
    assert chem.match(pattern) == [
        {"g6p": "g6p", "hexokinase": "hexokinase"},
        {"g6p": "g6p", "hexokinase": "isomerase"},
    ]

    pattern = chem.subgraph({"glucose", "atp", "g6p", "adp", "hexokinase"})
    assert chem.match(pattern) == [
        {
            "glucose": "glucose",
            "g6p": "g6p",
            "atp": "atp",
            "adp": "adp",
            "hexokinase": "hexokinase",
        }
    ]


def test_match_empty_when_no_embedding(chem: ChemistryImpl) -> None:
    # A lone molecule not present in the host by key -> no embedding.
    stray = _mol("xenon_goo", {}, bdepth=9)
    pattern = ChemistryImpl(
        "p",
        molecules={"xenon_goo": stray},
        reactions={},
        dat=MockDat("chem/p"),
    )
    assert chem.match(pattern) == []
