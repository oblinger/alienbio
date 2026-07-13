"""Set-covering / constrained-clustering solver over feature sets.

Pure combinatorial optimization with NO domain logic: every domain-specific
notion arrives as an opaque callable (:data:`Predicate` inside features, the
``admissible`` capacity oracle, the ``cost`` objective) that this code only
ever *calls*, never inspects.

The problem: partition a list of *items* — each a :class:`FeatureSet` of
required features — into containers, where a container's feature set is the
UNION of its assigned items' features and must satisfy ``admissible``. The
solver minimizes a pluggable ``cost`` (default: container count).

Algorithm: greedy open-or-place over items in their given order (an item is
placed only with an exact-schema match; otherwise a new container opens),
then local improvement in two parts:

1. *Merges* — best-first agglomerative merging of container pairs by overlap
   score (Jaccard similarity of the two feature sets), considering only
   admissible, cost-reducing merges. The ``aggressiveness`` knob in ``[0, 1]``
   is the stopping rule: merging halts at the first selected merge whose
   score falls below ``1 - aggressiveness``. Because the merge *sequence* is
   chosen independently of the threshold, each threshold executes a prefix of
   one fixed sequence — so the final container count is provably weakly
   non-increasing in ``aggressiveness`` (0 = isolate, 1 = merge hard).
2. *Moves* — single items are moved between containers when both resulting
   containers stay admissible and non-empty and the move strictly reduces
   ``cost``. Moves never change the container count (that is the merge
   phase's job), which preserves the monotonicity guarantee.

Everything is deterministic: identical inputs (including ``seed``) yield an
identical :class:`Cover`. The ``seed`` is used only to break ties (each
container gets a random priority at creation); no wall-clock or global
``random`` state is ever consulted.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable, Optional, Sequence

from .dist import Seed
from .types import FeatureSet, Predicate

log = logging.getLogger(__name__)

# A feature is a (key, opaque predicate) pair — exactly the elements of
# FeatureSet.features.
Feature = tuple[str, Predicate]

# Safety cap on local-improvement steps; strict cost decrease already
# guarantees termination, so this only guards pathological cost callables.
_MAX_IMPROVE_STEPS = 10_000


@dataclass(frozen=True)
class Cover:
    """A partition of items into admissible containers.

    ``containers[c]`` is the union of the features of every item assigned to
    container ``c``; ``assignment[i]`` is the container index of item ``i``.
    Containers are ordered by the smallest item index they contain, so equal
    inputs produce byte-identical covers.
    """

    containers: tuple[frozenset[Feature], ...]
    assignment: tuple[int, ...]


def _jaccard(a: frozenset[Feature], b: frozenset[Feature]) -> float:
    """Overlap score in [0, 1]: |a ∩ b| / |a ∪ b| (1.0 for two empty sets)."""
    union = a | b
    if not union:
        return 1.0
    return len(a & b) / len(union)


def _build_cover(
    n_items: int,
    groups: Sequence[Sequence[int]],
    feats: Sequence[frozenset[Feature]],
) -> Cover:
    """Canonicalize working state into a Cover (containers ordered by first item)."""
    order = sorted(range(len(groups)), key=lambda j: min(groups[j]))
    remap = {j: pos for pos, j in enumerate(order)}
    assignment = [0] * n_items
    for j, members in enumerate(groups):
        for i in members:
            assignment[i] = remap[j]
    containers = tuple(feats[j] for j in order)
    return Cover(containers=containers, assignment=tuple(assignment))


def cover(
    items: Sequence[FeatureSet],
    admissible: Callable[[frozenset[Feature]], bool] = lambda fs: True,
    cost: Callable[[Cover], float] = lambda c: float(len(c.containers)),
    seed: Seed = Seed(0),
    aggressiveness: float = 0.5,
) -> Cover:
    """Partition ``items`` into admissible containers, minimizing ``cost``.

    Greedy open-or-place (deterministic item order), then local improvement:
    threshold-stopped best-first merges followed by cost-reducing item moves
    (see the module docstring). ``aggressiveness`` in ``[0, 1]`` biases
    merging: 0 isolates items (more containers), 1 merges as hard as
    admissibility allows (fewer containers); the resulting container count is
    weakly non-increasing in it. ``seed`` is used only for tie-breaking, so
    identical inputs give identical covers.

    Raises ``ValueError`` if an item's own feature set is inadmissible (no
    valid cover exists) or ``aggressiveness`` is outside ``[0, 1]``.
    """
    if not 0.0 <= aggressiveness <= 1.0:
        raise ValueError(f"aggressiveness must be in [0, 1], got {aggressiveness}")
    threshold = 1.0 - aggressiveness
    rng = seed.rng()
    n = len(items)
    item_feats: list[frozenset[Feature]] = [frozenset(it.features) for it in items]

    # Working state: parallel lists over live containers.
    groups: list[list[int]] = []  # item indices per container
    feats: list[frozenset[Feature]] = []  # union of member features
    prios: list[float] = []  # seed-derived tie-break priority

    # ── Greedy open-or-place ────────────────────────────────────────────────
    # Place only on an exact schema match (overlap score 1.0, which clears any
    # threshold); otherwise open. Partial-overlap consolidation is left to the
    # merge phase, whose fixed merge sequence keeps the container count
    # provably monotone in ``aggressiveness``.
    for i, f in enumerate(item_feats):
        best_j = -1
        best_prio = -1.0
        for j in range(len(groups)):
            if feats[j] == f and admissible(f) and prios[j] > best_prio:
                best_j, best_prio = j, prios[j]
        if best_j >= 0:
            groups[best_j].append(i)
        else:
            if not admissible(f):
                raise ValueError(
                    f"item {i} is inadmissible even alone; no valid cover exists"
                )
            groups.append([i])
            feats.append(f)
            prios.append(float(rng.random()))

    current_cost = cost(_build_cover(n, groups, feats))
    steps = 0
    capped = False

    # ── Local improvement 1: threshold-stopped best-first merges ───────────
    # Selection ignores the threshold (fixed sequence); the threshold only
    # stops the sequence, so each aggressiveness executes a prefix of the
    # same merge chain.
    while True:
        if steps >= _MAX_IMPROVE_STEPS:
            capped = True
            break
        best_pair: Optional[tuple[int, int]] = None
        best_key = (-1.0, -1.0)
        best_pair_cost = current_cost
        for j in range(len(groups)):
            for k in range(j + 1, len(groups)):
                merged = feats[j] | feats[k]
                if not admissible(merged):
                    continue
                cand_groups = [
                    g for idx, g in enumerate(groups) if idx not in (j, k)
                ] + [groups[j] + groups[k]]
                cand_feats = [
                    fs for idx, fs in enumerate(feats) if idx not in (j, k)
                ] + [merged]
                cand_cost = cost(_build_cover(n, cand_groups, cand_feats))
                if cand_cost >= current_cost:
                    continue
                key = (_jaccard(feats[j], feats[k]), prios[j] + prios[k])
                if key > best_key:
                    best_key, best_pair = key, (j, k)
                    best_pair_cost = cand_cost
        if best_pair is None:
            log.info(
                "cover: no further admissible cost-reducing merge exists "
                "(%d containers)",
                len(groups),
            )
            break
        if best_key[0] < threshold:
            log.info(
                "cover: next merge score %.3f below threshold %.3f "
                "(aggressiveness %.2f); stopping merges at %d containers",
                best_key[0],
                threshold,
                aggressiveness,
                len(groups),
            )
            break
        j, k = best_pair
        groups[j] = groups[j] + groups[k]
        feats[j] = feats[j] | feats[k]
        del groups[k], feats[k], prios[k]
        current_cost = best_pair_cost
        steps += 1

    # ── Local improvement 2: cost-reducing single-item moves ───────────────
    # Moves keep both containers non-empty and admissible, so the container
    # count (and hence aggressiveness monotonicity) is untouched.
    while not capped:
        if steps >= _MAX_IMPROVE_STEPS:
            capped = True
            break
        best_move: Optional[tuple[int, int, int]] = None  # (item, src, dst)
        best_move_key = (0.0, -1.0)
        best_move_cost = current_cost
        for j in range(len(groups)):
            if len(groups[j]) < 2:
                continue  # donor must stay non-empty
            for i in groups[j]:
                donor = [m for m in groups[j] if m != i]
                donor_feats = frozenset().union(*(item_feats[m] for m in donor))
                if not admissible(donor_feats):
                    continue
                for k in range(len(groups)):
                    if k == j:
                        continue
                    target = feats[k] | item_feats[i]
                    if not admissible(target):
                        continue
                    cand_groups = [
                        donor if idx == j else list(g) for idx, g in enumerate(groups)
                    ]
                    cand_feats = [
                        donor_feats if idx == j else fs for idx, fs in enumerate(feats)
                    ]
                    cand_groups[k] = cand_groups[k] + [i]
                    cand_feats[k] = target
                    cand_cost = cost(_build_cover(n, cand_groups, cand_feats))
                    if cand_cost >= current_cost:
                        continue
                    key = (current_cost - cand_cost, prios[k])
                    if key > best_move_key:
                        best_move_key, best_move = key, (i, j, k)
                        best_move_cost = cand_cost
        if best_move is None:
            log.info(
                "cover: converged after %d improvement step(s) "
                "(%d containers)",
                steps,
                len(groups),
            )
            break
        i, j, k = best_move
        groups[j] = [m for m in groups[j] if m != i]
        feats[j] = frozenset().union(*(item_feats[m] for m in groups[j]))
        groups[k].append(i)
        feats[k] = feats[k] | item_feats[i]
        current_cost = best_move_cost
        steps += 1

    if capped:
        log.warning(
            "cover: local-improvement step cap (%d) reached; returning "
            "current cover with %d containers",
            _MAX_IMPROVE_STEPS,
            len(groups),
        )

    return _build_cover(n, groups, feats)
