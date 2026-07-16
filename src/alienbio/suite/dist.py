"""Distributions, deterministic seeds, and parameter schemas.

This module provides the sampling seam for the ``suite`` subsystem. Everything
here is fully deterministic: a given :class:`Seed` always produces identical
draws, byte for byte. Child-seed derivation is hash-based (``hashlib.sha256``),
never ``random``/``os.urandom``/time, so reproducibility holds across processes
and machines.

Design notes:
- :class:`Seed` wraps a plain ``int`` and derives children from a label via
  SHA-256; each :class:`Seed` can spin up a ``numpy.random.Generator``.
- :class:`Dist` is a structural ``Protocol`` — concrete distributions are frozen
  dataclasses that expose ``sample(seed)``.
- :class:`ParamSchema` walks a (possibly nested) dict/list tree; every ``Dist``
  leaf is sampled with a seed derived from its *path*, so sampling is
  order-independent and reproducible.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Generic, Optional, Protocol, TypeVar, runtime_checkable

import numpy as np

T = TypeVar("T")
T_co = TypeVar("T_co", covariant=True)


@dataclass(frozen=True)
class Seed:
    """A deterministic seed: an ``int`` plus hash-based child derivation.

    ``child(label)`` derives a new, independent seed from this one and a string
    label via SHA-256, so distinct labels yield independent sub-streams while
    the same label always yields the same sub-seed.
    """

    value: int

    def child(self, label: str) -> "Seed":
        """Derive a child seed deterministically from ``label`` (hash-based)."""
        payload = f"{self.value}:{label}".encode("utf-8")
        digest = hashlib.sha256(payload).digest()[:8]
        return Seed(int.from_bytes(digest, "big"))

    def rng(self) -> np.random.Generator:
        """A numpy Generator seeded deterministically from this seed's value."""
        return np.random.default_rng(self.value)


@runtime_checkable
class Dist(Protocol[T_co]):
    """A sampleable distribution: ``sample(seed)`` returns a value."""

    def sample(self, seed: Seed) -> T_co: ...


@dataclass(frozen=True)
class Constant(Generic[T]):
    """Always samples ``value``."""

    value: T

    def sample(self, seed: Seed) -> T:
        return self.value


@dataclass(frozen=True)
class Uniform:
    """Uniform draw on ``[lo, hi)``."""

    lo: float
    hi: float

    def sample(self, seed: Seed) -> float:
        return float(seed.rng().uniform(self.lo, self.hi))


@dataclass(frozen=True)
class Normal:
    """Gaussian draw with the given ``mean`` and ``std``."""

    mean: float
    std: float

    def sample(self, seed: Seed) -> float:
        return float(seed.rng().normal(self.mean, self.std))


@dataclass(frozen=True)
class LogNormal:
    """Log-normal draw: ``exp(Normal(mean, sigma))``."""

    mean: float
    sigma: float

    def sample(self, seed: Seed) -> float:
        return float(seed.rng().lognormal(self.mean, self.sigma))


@dataclass(frozen=True)
class Choice(Generic[T]):
    """Categorical draw over ``options`` (optionally weighted)."""

    options: tuple[T, ...]
    weights: Optional[tuple[float, ...]] = None

    def sample(self, seed: Seed) -> T:
        rng = seed.rng()
        p: Optional[list[float]] = None
        if self.weights is not None:
            total = float(sum(self.weights))
            p = [w / total for w in self.weights]
        idx = int(rng.choice(len(self.options), p=p))
        return self.options[idx]


def _sample_tree(node: Any, seed: Seed, path: str) -> Any:
    """Recursively sample a parameter tree; ``Dist`` leaves use path-seeds."""
    if isinstance(node, Dist):
        return node.sample(seed.child(path))
    if isinstance(node, dict):
        return {k: _sample_tree(v, seed, f"{path}/{k}") for k, v in node.items()}
    if isinstance(node, list):
        return [_sample_tree(v, seed, f"{path}/{i}") for i, v in enumerate(node)]
    if isinstance(node, tuple):
        return tuple(_sample_tree(v, seed, f"{path}/{i}") for i, v in enumerate(node))
    return node


@dataclass(frozen=True)
class ParamSchema:
    """A nested dict/list tree whose ``Dist`` leaves are sampled by path.

    ``sample(seed)`` walks ``tree``; each ``Dist`` leaf is sampled with a child
    seed derived from its path (so a leaf's draw depends only on *where* it sits,
    never on iteration order). Non-``Dist`` leaves pass through unchanged.
    """

    tree: Any

    def sample(self, seed: Seed) -> Any:
        return _sample_tree(self.tree, seed, "")
