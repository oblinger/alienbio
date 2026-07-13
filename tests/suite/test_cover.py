"""Acceptance tests for the set-covering / constrained-clustering solver."""

from __future__ import annotations

from typing import Any, Callable, Iterator

from alienbio.suite.cover import Cover, Feature, cover
from alienbio.suite.dist import Seed
from alienbio.suite.types import FeatureSet


def _true(x: Any) -> bool:
    return True


def _fs(*keys: str) -> FeatureSet:
    """A FeatureSet over the given keys with a shared trivial predicate."""
    return FeatureSet(frozenset((k, _true) for k in keys))


def _cap(k: int) -> Callable[[frozenset[Feature]], bool]:
    """Admissibility oracle: at most ``k`` distinct feature keys per container."""
    return lambda fs: len({key for key, _ in fs}) <= k


def _partitions(seq: list[int]) -> Iterator[list[list[int]]]:
    """All set partitions of ``seq`` (Bell-number enumeration)."""
    if not seq:
        yield []
        return
    first, rest = seq[0], seq[1:]
    for part in _partitions(rest):
        for i in range(len(part)):
            yield part[:i] + [[first] + part[i]] + part[i + 1 :]
        yield [[first]] + part


def _optimal_count(
    items: list[FeatureSet], admissible: Callable[[frozenset[Feature]], bool]
) -> int:
    """Brute-force minimum container count over all admissible partitions."""
    best = len(items)
    for part in _partitions(list(range(len(items)))):
        ok = all(
            admissible(frozenset().union(*(items[i].features for i in block)))
            for block in part
        )
        if ok:
            best = min(best, len(part))
    return best


# A fixed 8-item instance: two overlapping triads, plus two loners.
ITEMS_8 = [
    _fs("a", "b"),
    _fs("a", "c"),
    _fs("b", "c"),
    _fs("d", "e"),
    _fs("d", "f"),
    _fs("e", "f"),
    _fs("g"),
    _fs("h"),
]


def test_validity_under_key_cap():
    k = 4
    admissible = _cap(k)
    result = cover(ITEMS_8, admissible=admissible, seed=Seed(3), aggressiveness=0.8)

    # Every item assigned to exactly one existing container.
    assert len(result.assignment) == len(ITEMS_8)
    assert all(0 <= c < len(result.containers) for c in result.assignment)
    assert set(result.assignment) == set(range(len(result.containers)))

    # Each container's feature set is exactly the union of its items' features,
    # and no container exceeds the key cap.
    for c, feats in enumerate(result.containers):
        members = [i for i, a in enumerate(result.assignment) if a == c]
        union = frozenset().union(*(ITEMS_8[i].features for i in members))
        assert feats == union
        assert admissible(feats)
        assert len({key for key, _ in feats}) <= k


def test_near_optimal_on_tiny_instances():
    pool = ["a", "b", "c", "d", "e"]
    admissible = _cap(3)
    for seed_val in [0, 1, 2, 7, 13]:
        rng = Seed(seed_val).child("instance").rng()
        items = []
        for _ in range(int(rng.integers(4, 7))):  # 4-6 items
            n_keys = int(rng.integers(1, 4))
            keys = rng.choice(len(pool), size=n_keys, replace=False)
            items.append(_fs(*(pool[i] for i in keys)))
        opt = _optimal_count(items, admissible)
        result = cover(items, admissible=admissible, seed=Seed(seed_val), aggressiveness=1.0)
        assert len(result.containers) <= opt + 1


def test_aggressiveness_monotone_container_count():
    admissible = _cap(4)
    counts = [
        len(cover(ITEMS_8, admissible=admissible, seed=Seed(5), aggressiveness=a).containers)
        for a in [0.0, 0.25, 0.5, 0.75, 1.0]
    ]
    assert counts == sorted(counts, reverse=True)  # weakly non-increasing
    assert counts[0] > counts[-1]  # and the knob actually does something


def test_determinism():
    admissible = _cap(3)

    def custom_cost(c: Cover) -> float:
        # Container count plus a small spread penalty — exercises the cost seam.
        return len(c.containers) + 0.01 * sum(len(fs) for fs in c.containers)

    a = cover(ITEMS_8, admissible=admissible, cost=custom_cost, seed=Seed(42), aggressiveness=0.6)
    b = cover(ITEMS_8, admissible=admissible, cost=custom_cost, seed=Seed(42), aggressiveness=0.6)
    assert a == b
    assert a.containers == b.containers
    assert a.assignment == b.assignment
