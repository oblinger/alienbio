"""Distribution-matching graph augmenter for the ``suite`` reaction-network.

Pure graph work: :func:`augment` adds *filler* species/reactions and filler
edges to a :class:`~alienbio.suite.types.World` until a set of summary
statistics approximately matches the requested targets. It carries NO domain
logic — every tag is an opaque string that is only ever copied, never inspected.

The load-bearing invariant is that the **protected** subgraph is left provably
untouched: :func:`augment` never adds, removes, or modifies a protected node,
and never touches an edge incident to a protected node. Filler edges connect
only newly-added (non-protected) filler nodes, so the induced subgraph over the
protected set — and the full incidence of every protected node — is identical
before and after.

Supported statistic vocabulary (:func:`graph_stats`):
- ``"n_species"``   — number of species nodes.
- ``"n_reactions"`` — number of reaction nodes.
- ``"mean_degree"`` — mean over *all* nodes (species + reactions) of
  ``len(net.neighbors(node))``.
"""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import Mapping

from .dist import Seed
from .types import NodeId, ReactionNetwork, Reaction, Species, World

log = logging.getLogger(__name__)

# A target stat: (target_value, tolerance). Keys are drawn from the vocabulary
# documented above.
TargetStats = Mapping[str, "tuple[float, float]"]


def graph_stats(net: ReactionNetwork) -> dict[str, float]:
    """Summary statistics of ``net`` over the supported stat vocabulary."""
    n_species = len(net.species)
    n_reactions = len(net.reactions)
    all_nodes = list(net.species.keys()) + list(net.reactions.keys())
    if all_nodes:
        total_degree = sum(len(net.neighbors(node)) for node in all_nodes)
        mean_degree = total_degree / len(all_nodes)
    else:
        mean_degree = 0.0
    return {
        "n_species": float(n_species),
        "n_reactions": float(n_reactions),
        "mean_degree": mean_degree,
    }


def augment(
    world: World,
    target_stats: TargetStats,
    protected: set[NodeId],
    seed: Seed = Seed(0),
    max_iters: int = 10_000,
) -> World:
    """Add filler nodes/edges until ``target_stats`` are met within tolerance.

    Only *additions* among non-protected nodes are made. Protected nodes and any
    edge incident to a protected node are never altered. Returns a NEW
    :class:`World` sharing the original ``topology`` and ``initial`` (only the
    network grows). If ``max_iters`` is exhausted before every target is within
    tolerance, the missed stat(s) are logged.
    """
    protected_set = set(protected)
    rng = seed.rng()

    # Mutable working copies of the network's node tables.
    species: dict[NodeId, Species] = dict(world.network.species)
    reactions: dict[NodeId, Reaction] = dict(world.network.reactions)

    # Filler bookkeeping. Filler edges only ever connect a filler species to a
    # filler reaction, so no protected (or even pre-existing) node is touched.
    filler_species: list[NodeId] = []
    filler_reactions: list[NodeId] = []
    used_pairs: set[tuple[NodeId, NodeId]] = set()

    _s_counter = 0
    _r_counter = 0

    def _fresh_id(prefix: str, counter: int) -> tuple[NodeId, int]:
        while True:
            nid = f"{prefix}{counter}"
            counter += 1
            if nid not in species and nid not in reactions and nid not in protected_set:
                return nid, counter

    def _add_filler_species() -> None:
        nonlocal _s_counter
        sid, _s_counter = _fresh_id("fill_s", _s_counter)
        species[sid] = Species(id=sid)
        filler_species.append(sid)

    def _add_filler_reaction() -> None:
        nonlocal _r_counter
        rid, _r_counter = _fresh_id("fill_r", _r_counter)
        reactions[rid] = Reaction(id=rid)
        filler_reactions.append(rid)

    def _add_filler_edge() -> bool:
        """Connect an unused (filler reaction, filler species) pair; add one
        filler edge. Returns True if an edge was added, False if no capacity."""
        candidates = [
            (r, s)
            for r in filler_reactions
            for s in filler_species
            if (r, s) not in used_pairs
        ]
        if not candidates:
            return False
        idx = int(rng.integers(len(candidates)))
        r, s = candidates[idx]
        used_pairs.add((r, s))
        rxn = reactions[r]
        reactions[r] = replace(rxn, reactants=rxn.reactants + ((s, 1),))
        return True

    def _stats() -> dict[str, float]:
        return graph_stats(ReactionNetwork(species=species, reactions=reactions))

    def _misses(stats: dict[str, float]) -> dict[str, float]:
        out: dict[str, float] = {}
        for key, (target, tol) in target_stats.items():
            if key not in stats:
                continue
            delta = stats[key] - target
            if abs(delta) > tol:
                out[key] = delta
        return out

    for _ in range(max_iters):
        stats = _stats()
        misses = _misses(stats)
        if not misses:
            break

        acted = False

        # Priority: fix node counts first (species, then reactions), then adjust
        # mean_degree via filler edges. Edges don't change the counts, so once the
        # counts are within tolerance the degree pass converges without disturbing
        # them.
        if "n_species" in target_stats:
            target, tol = target_stats["n_species"]
            if stats["n_species"] < target - tol:
                _add_filler_species()
                acted = True

        if not acted and "n_reactions" in target_stats:
            target, tol = target_stats["n_reactions"]
            if stats["n_reactions"] < target - tol:
                _add_filler_reaction()
                acted = True

        if not acted and "mean_degree" in target_stats:
            target, tol = target_stats["mean_degree"]
            if stats["mean_degree"] < target - tol:
                acted = _add_filler_edge()
            elif stats["mean_degree"] > target + tol:
                # Overshoot: the only additive lever is to raise the node count
                # (denominator). Do so only where it won't violate a pinned count.
                if "n_species" not in target_stats:
                    _add_filler_species()
                    acted = True
                elif "n_reactions" not in target_stats:
                    _add_filler_reaction()
                    acted = True

        if not acted:
            # No additive move can reduce a remaining miss; stop early.
            break

    remaining = _misses(_stats())
    if remaining:
        detail = ", ".join(
            f"{key} off by {delta:+.4g} (target {target_stats[key][0]}, "
            f"tol {target_stats[key][1]})"
            for key, delta in remaining.items()
        )
        log.warning("augment: targets not reached within max_iters: %s", detail)

    new_network = ReactionNetwork(species=species, reactions=reactions)
    return World(network=new_network, topology=world.topology, initial=world.initial)
