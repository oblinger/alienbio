"""Acceptance tests for the distribution-matching graph augmenter (FT04)."""

from __future__ import annotations

import logging

import numpy as np

from alienbio.suite.augment import augment, graph_stats
from alienbio.suite.dist import Seed
from alienbio.suite.types import (
    Compartment,
    Reaction,
    ReactionNetwork,
    Species,
    StateVector,
    Topology,
    World,
)


def build_world() -> tuple[World, set[str]]:
    """A small hand-made world plus a protected node set.

    Species: s_a, s_b, s_c, s_d.  Reactions: r_x (s_a -> s_b), r_y (s_b -> s_c).
    Protected = {s_a, r_x}: a protected species and a protected reaction with an
    edge between them (and r_x also touches non-protected s_b).
    """
    species = {
        "s_a": Species("s_a"),
        "s_b": Species("s_b"),
        "s_c": Species("s_c"),
        "s_d": Species("s_d"),
    }
    reactions = {
        "r_x": Reaction("r_x", reactants=(("s_a", 1),), products=(("s_b", 1),)),
        "r_y": Reaction("r_y", reactants=(("s_b", 1),), products=(("s_c", 1),)),
    }
    network = ReactionNetwork(species=species, reactions=reactions)

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


def _incident_edges(net: ReactionNetwork, nodes: set[str]) -> set[frozenset[str]]:
    """Every edge (frozenset pair) incident to any node in ``nodes``."""
    edges: set[frozenset[str]] = set()
    for node in nodes:
        for nb in net.neighbors(node):
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
    assert result.network.subgraph(protected) == world.network.subgraph(protected)

    # Strong form: the full set of edges incident to any protected node is
    # unchanged before/after.
    assert _incident_edges(result.network, protected) == _incident_edges(
        world.network, protected
    )

    # No reaction references a protected node unless it already did in the input.
    original_refs = {
        rid
        for rid, rxn in world.network.reactions.items()
        if any(
            n in protected
            for n, _ in (*rxn.reactants, *rxn.products, *rxn.modifiers)
        )
    }
    for rid, rxn in result.network.reactions.items():
        refs_protected = any(
            n in protected
            for n, _ in (*rxn.reactants, *rxn.products, *rxn.modifiers)
        )
        if refs_protected:
            assert rid in original_refs
            # And that reaction must be byte-for-byte the original.
            assert rxn == world.network.reactions[rid]


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
    assert set(a.network.species.keys()) == set(b.network.species.keys())
    assert set(a.network.reactions.keys()) == set(b.network.reactions.keys())
    # Full structural equality of the resulting networks.
    assert a.network == b.network


def test_unreachable_target_logs(caplog):
    world, protected = build_world()
    # An impossible n_species target with a tiny iteration budget.
    targets = {"n_species": (1_000_000.0, 0.0)}
    with caplog.at_level(logging.WARNING, logger="alienbio.suite.augment"):
        result = augment(world, targets, protected, seed=Seed(0), max_iters=5)

    # It returned, made partial progress (added up to max_iters fillers), and
    # logged the miss.
    stats = graph_stats(result.network)
    assert stats["n_species"] == len(world.network.species) + 5
    assert any(
        "not reached" in rec.message and "n_species" in rec.message
        for rec in caplog.records
    )
