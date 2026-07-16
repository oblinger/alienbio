"""Acceptance tests for the distribution-matching graph augmenter (FT04).

F007: the augmenter operates on the biology ``Chemistry`` (unified protocol model).
``ChemistryImpl`` uses identity equality (it is an ``Entity``, not a frozen
dataclass), so structural comparisons go through :func:`_chem_shape` rather than
``==``.
"""

from __future__ import annotations

import logging

import numpy as np

from alienbio.bio.chemistry import ChemistryImpl
from alienbio.bio.molecule import MoleculeImpl
from alienbio.bio.reaction import ReactionImpl
from alienbio.infra.entity import MockDat
from alienbio.suite.augment import augment, graph_stats
from alienbio.suite.dist import Seed
from alienbio.suite.types import (
    Compartment,
    StateVector,
    Topology,
    World,
)


def _mol(name: str) -> MoleculeImpl:
    return MoleculeImpl(name, name=name, dat=MockDat(f"mol/{name}"))


def build_world() -> tuple[World, set[str]]:
    """A small hand-made world plus a protected node set.

    Molecules: s_a, s_b, s_c, s_d.  Reactions: r_x (s_a -> s_b), r_y (s_b -> s_c).
    Protected = {s_a, r_x}: a protected molecule and a protected reaction with an
    edge between them (and r_x also touches non-protected s_b).
    """
    s_a, s_b, s_c, s_d = _mol("s_a"), _mol("s_b"), _mol("s_c"), _mol("s_d")
    r_x = ReactionImpl(
        "r_x", reactants={s_a: 1.0}, products={s_b: 1.0}, dat=MockDat("rxn/r_x")
    )
    r_y = ReactionImpl(
        "r_y", reactants={s_b: 1.0}, products={s_c: 1.0}, dat=MockDat("rxn/r_y")
    )
    network = ChemistryImpl(
        "world",
        molecules={"s_a": s_a, "s_b": s_b, "s_c": s_c, "s_d": s_d},
        reactions={"r_x": r_x, "r_y": r_y},
        dat=MockDat("chem/world"),
    )

    topology = Topology(
        compartments=(Compartment("root", None, "organism", 1.0),),
    )
    initial = StateVector(
        data=np.zeros((1, 4), dtype=np.float64),
        compartments=("root",),
        species=("s_a", "s_b", "s_c", "s_d"),
    )
    world = World(network=network, topology=topology, initial=initial)
    protected = {"s_a", "r_x"}
    return world, protected


def _chem_shape(chem: ChemistryImpl) -> tuple[set[str], dict[str, tuple]]:
    """Normalize a chemistry to comparable plain data (order-independent)."""
    species = set(chem.molecules.keys())
    reactions = {
        rid: (
            frozenset((m.name, c) for m, c in rxn.reactants.items()),
            frozenset((m.name, c) for m, c in rxn.products.items()),
        )
        for rid, rxn in chem.reactions.items()
    }
    return species, reactions


def _incident_edges(chem: ChemistryImpl, nodes: set[str]) -> set[frozenset[str]]:
    """Every edge (frozenset pair) incident to any node in ``nodes``."""
    edges: set[frozenset[str]] = set()
    for node in nodes:
        for nb in chem.neighbors(node):
            edges.add(frozenset((node, nb)))
    return edges


def test_stats_within_tolerance():
    world, protected = build_world()
    targets = {
        "n_species": (12.0, 0.0),
        "n_reactions": (6.0, 0.0),
        "mean_degree": (2.0, 0.5),
    }
    result = augment(world, targets, protected, seed=Seed(1))
    stats = graph_stats(result.network)
    for key, (target, tol) in targets.items():
        assert abs(stats[key] - target) <= tol, (key, stats[key], target, tol)


def test_protected_subgraph_invariant():
    world, protected = build_world()
    targets = {
        "n_species": (12.0, 0.0),
        "n_reactions": (6.0, 0.0),
        "mean_degree": (2.0, 0.5),
    }
    result = augment(world, targets, protected, seed=Seed(2))

    # Induced subgraph over the protected set is structurally identical.
    assert _chem_shape(result.network.subgraph(protected)) == _chem_shape(
        world.network.subgraph(protected)
    )

    # Strong form: the full set of edges incident to any protected node is
    # unchanged before/after.
    assert _incident_edges(result.network, protected) == _incident_edges(
        world.network, protected
    )

    # No reaction references a protected node unless it already did in the input
    # (references include modifiers — catalysts are first-class edges, F008).
    original_refs = {
        rid
        for rid, rxn in world.network.reactions.items()
        if any(
            m.name in protected
            for m in (*rxn.reactants, *rxn.products, *rxn.modifiers)
        )
    }
    for rid, rxn in result.network.reactions.items():
        refs_protected = any(
            m.name in protected
            for m in (*rxn.reactants, *rxn.products, *rxn.modifiers)
        )
        if refs_protected:
            assert rid in original_refs
            # And that reaction must be the original object (reused by identity).
            assert rxn is world.network.reactions[rid]


def test_protected_reaction_modifier_preserved():
    """A first-class modifier on a protected reaction survives augment (F008).

    The protected reaction is reused by identity, so its ``modifiers`` edge is
    preserved byte-for-byte and the catalyst stays adjacent to the reaction in
    the augmented graph.
    """
    s_a, s_b, s_enz = _mol("s_a"), _mol("s_b"), _mol("s_enz")
    r_x = ReactionImpl(
        "r_x",
        reactants={s_a: 1.0},
        products={s_b: 1.0},
        modifiers={s_enz: "catalyst"},
        dat=MockDat("rxn/r_x"),
    )
    network = ChemistryImpl(
        "world",
        molecules={"s_a": s_a, "s_b": s_b, "s_enz": s_enz},
        reactions={"r_x": r_x},
        dat=MockDat("chem/world"),
    )
    topology = Topology(compartments=(Compartment("root", None, "organism", 1.0),))
    initial = StateVector(
        data=np.zeros((1, 3), dtype=np.float64),
        compartments=("root",),
        species=("s_a", "s_b", "s_enz"),
    )
    world = World(network=network, topology=topology, initial=initial)
    protected = {"s_a", "s_b", "s_enz", "r_x"}

    result = augment(
        world,
        {"n_species": (8.0, 0.0), "n_reactions": (4.0, 0.0)},
        protected,
        seed=Seed(3),
    )

    kept = result.network.reactions["r_x"]
    # Reused by identity → modifier edge intact.
    assert kept is r_x
    assert {m.name: role for m, role in kept.modifiers.items()} == {"s_enz": "catalyst"}
    # The catalyst is adjacent to the reaction via first-class modifier incidence.
    assert "r_x" in result.network.neighbors("s_enz")
    assert "s_enz" in result.network.neighbors("r_x")


def test_determinism():
    world, protected = build_world()
    targets = {
        "n_species": (12.0, 0.0),
        "n_reactions": (6.0, 0.0),
        "mean_degree": (2.0, 0.5),
    }
    a = augment(world, targets, protected, seed=Seed(7))
    b = augment(world, targets, protected, seed=Seed(7))

    assert graph_stats(a.network) == graph_stats(b.network)
    assert set(a.network.molecules.keys()) == set(b.network.molecules.keys())
    assert set(a.network.reactions.keys()) == set(b.network.reactions.keys())
    # Full structural equality of the resulting chemistries.
    assert _chem_shape(a.network) == _chem_shape(b.network)


def test_unreachable_target_logs(caplog):
    world, protected = build_world()
    # An impossible n_species target with a tiny iteration budget.
    targets = {"n_species": (1_000_000.0, 0.0)}
    with caplog.at_level(logging.WARNING, logger="alienbio.suite.augment"):
        result = augment(world, targets, protected, seed=Seed(0), max_iters=5)

    # It returned, made partial progress (added up to max_iters fillers), and
    # logged the miss.
    stats = graph_stats(result.network)
    assert stats["n_species"] == len(world.network.molecules) + 5
    assert any(
        "not reached" in rec.message and "n_species" in rec.message
        for rec in caplog.records
    )
