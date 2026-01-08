"""Built-in functions for spec evaluation.

Distribution functions and other helpers available to !_ expressions.
All functions that need randomness accept ctx as a keyword-only parameter.
"""

from __future__ import annotations

from typing import Any, Callable, TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from .eval import Context


# =============================================================================
# Distribution Functions
# =============================================================================


def normal(mean: float, std: float, *, ctx: "Context") -> float:
    """Sample from normal distribution."""
    return float(ctx.rng.normal(mean, std))


def uniform(low: float, high: float, *, ctx: "Context") -> float:
    """Sample from uniform distribution."""
    return float(ctx.rng.uniform(low, high))


def lognormal(mean: float, sigma: float, *, ctx: "Context") -> float:
    """Sample from log-normal distribution."""
    return float(ctx.rng.lognormal(mean, sigma))


def poisson(lam: float, *, ctx: "Context") -> int:
    """Sample from Poisson distribution."""
    return int(ctx.rng.poisson(lam))


def exponential(scale: float, *, ctx: "Context") -> float:
    """Sample from exponential distribution."""
    return float(ctx.rng.exponential(scale))


def choice(options: list[Any], *, ctx: "Context") -> Any:
    """Choose uniformly from a list."""
    idx = ctx.rng.integers(0, len(options))
    return options[idx]


def discrete(weights: list[float], *, ctx: "Context") -> int:
    """Sample index from discrete distribution with given weights."""
    probs = np.array(weights, dtype=float)
    probs = probs / probs.sum()
    return int(ctx.rng.choice(len(weights), p=probs))


# =============================================================================
# Function Registry
# =============================================================================


DEFAULT_FUNCTIONS: dict[str, Callable[..., Any]] = {
    "normal": normal,
    "uniform": uniform,
    "lognormal": lognormal,
    "poisson": poisson,
    "exponential": exponential,
    "choice": choice,
    "discrete": discrete,
}
