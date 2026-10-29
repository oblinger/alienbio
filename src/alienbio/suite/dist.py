"""Distributions and deterministic seeds.

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
- A distribution may state its ``support()`` (the interval it draws from;
  :func:`support_of` reads it, ``None`` = unknown) so a consumer can judge
  every seed at once — the rate grammar refuses a rate constant whose
  support reaches below zero at load (T091 I1).
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import Any, Generic, Optional, Protocol, TypeVar, cast, runtime_checkable

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

    def support(self) -> Optional[tuple[float, float]]:
        v = self.value
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return (float(v), float(v))
        return None


@dataclass(frozen=True)
class Uniform:
    """Uniform draw on ``[lo, hi)``."""

    lo: float
    hi: float

    def sample(self, seed: Seed) -> float:
        return float(seed.rng().uniform(self.lo, self.hi))

    def support(self) -> tuple[float, float]:
        return (min(self.lo, self.hi), max(self.lo, self.hi))


@dataclass(frozen=True)
class Normal:
    """Gaussian draw with the given ``mean`` and ``std``."""

    mean: float
    std: float

    def sample(self, seed: Seed) -> float:
        return float(seed.rng().normal(self.mean, self.std))

    def support(self) -> tuple[float, float]:
        return (-math.inf, math.inf)


@dataclass(frozen=True)
class LogNormal:
    """Log-normal draw: ``exp(Normal(mean, sigma))``."""

    mean: float
    sigma: float

    def sample(self, seed: Seed) -> float:
        return float(seed.rng().lognormal(self.mean, self.sigma))

    def support(self) -> tuple[float, float]:
        return (0.0, math.inf)


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

    def support(self) -> Optional[tuple[float, float]]:
        values = [o for o in self.options if isinstance(o, (int, float)) and not isinstance(o, bool)]
        if not values or len(values) != len(self.options):
            return None
        return (float(min(values)), float(max(values)))


def support_of(dist: Any) -> Optional[tuple[float, float]]:
    """The closed interval ``(lo, hi)`` a distribution can draw from, when it
    says (a ``support()`` method), else ``None`` (unknown). ``Normal`` is
    the whole line whatever its parameters; a rate law reads this to refuse
    a constant whose draw could go negative on SOME seed (T091 I1)."""
    method = getattr(dist, "support", None)
    if not callable(method):
        return None
    result = method()
    if result is None:
        return None
    lo, hi = cast("tuple[float, float]", result)
    return (float(lo), float(hi))
