"""Environmental-pressure injection library (M32.4).

A single, **removable** scenario-level perturbation dial for the simulator seam
(:func:`alienbio.suite.verify.simulate`). An environmental pressure is an opaque
NAMED perturbation carried with an INTENSITY and a PERSISTENCE — an
intensity/persistence ladder — that displaces the reported world state while the
pressure is active and, crucially, **relaxes back toward the unperturbed
trajectory once the pressure is removed** so that recovery / resilience can be
measured.

Design (all domain-neutral — pressures carry no biology semantics):

- A pressure is a *displacement overlay* on the natural trajectory. The natural
  (unperturbed) integration is computed EXACTLY as before, so an absent pressure
  is byte-identical to today's simulation. The overlay is applied on top of the
  sampled states as a per-step multiplicative factor ``exp(coef * p_t)``.
- ``p_t`` is a scalar displacement that **builds up** toward ``intensity`` while
  the pressure is active and **decays geometrically toward zero** after the
  pressure is removed. ``persistence`` is the geometric keep-factor governing
  both timescales, so a more persistent pressure both accrues and dissipates
  more slowly.
- Because the overlay relaxes to zero after removal, the reported state provably
  returns toward the unperturbed trajectory regardless of the base world's own
  stability — recovery is a property of the dial, not of the world.

Named pressures are opaque coefficients (the sign/magnitude of the per-step
log-multiplier); named intensity / persistence levels are opaque ordinals.
Unknown names or out-of-range levels RAISE — there is no silent fallback.

Any stochastic element is seeded through the framework's :class:`~alienbio.suite.dist.Seed`
(``jitter > 0`` draws a bounded per-step multiplicative noise), so identical
``(pressure, seed)`` yield an identical overlay.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping, Union

import numpy as np

from .dist import Seed

# A named intensity or persistence level, or a raw number.
Level = Union[str, float, int]


# ─────────────────────────────────────────────────────────────────────────────
# Opaque ladders / registry (no domain semantics — just named ordinals)
# ─────────────────────────────────────────────────────────────────────────────

#: Named pressures → per-step log-multiplier coefficient (direction + weight).
NAMED_PRESSURES: Mapping[str, float] = {
    "suppress": -1.0,
    "amplify": 1.0,
    "drain": -0.5,
    "enrich": 0.5,
    "shock": -2.0,
}

#: Intensity ladder → plateau displacement magnitude. ``none`` = identity.
INTENSITY_LEVELS: Mapping[str, float] = {
    "none": 0.0,
    "low": 0.25,
    "moderate": 0.5,
    "high": 1.0,
    "severe": 2.0,
}

#: Persistence ladder → geometric keep-factor in ``[0, 1)``. Higher = slower
#: build-up AND slower recovery. ``permanent`` still decays (never == 1.0).
PERSISTENCE_LEVELS: Mapping[str, float] = {
    "transient": 0.3,
    "brief": 0.6,
    "moderate": 0.8,
    "lasting": 0.95,
    "permanent": 0.99,
}


def _resolve_intensity(level: Level) -> float:
    """Resolve a named/numeric intensity to a non-negative magnitude."""
    if isinstance(level, str):
        if level not in INTENSITY_LEVELS:
            raise ValueError(
                f"unknown intensity level {level!r}; "
                f"expected one of {sorted(INTENSITY_LEVELS)} or a number >= 0"
            )
        return INTENSITY_LEVELS[level]
    value = float(level)
    if not math.isfinite(value) or value < 0.0:
        raise ValueError(f"intensity must be a finite number >= 0; got {level!r}")
    return value


def _resolve_persistence(level: Level) -> float:
    """Resolve a named/numeric persistence to a keep-factor in ``[0, 1)``."""
    if isinstance(level, str):
        if level not in PERSISTENCE_LEVELS:
            raise ValueError(
                f"unknown persistence level {level!r}; "
                f"expected one of {sorted(PERSISTENCE_LEVELS)} or a number in [0, 1)"
            )
        return PERSISTENCE_LEVELS[level]
    value = float(level)
    if not math.isfinite(value) or not (0.0 <= value < 1.0):
        raise ValueError(
            f"persistence must be a number in [0, 1); got {level!r}"
        )
    return value


@dataclass(frozen=True)
class EnvironmentalPressure:
    """A removable, named environmental perturbation with an overlay trajectory.

    Attributes:
        name: Opaque pressure name (must be a key of :data:`NAMED_PRESSURES`).
        coef: Per-step log-multiplier coefficient for ``name`` (resolved).
        intensity: Plateau displacement magnitude (>= 0). ``0`` == identity.
        persistence: Geometric keep-factor in ``[0, 1)`` governing build-up and
            recovery timescales.
        remove_at: Step index at which the pressure is lifted (``None`` = never;
            the pressure stays active for the whole run). After removal the
            overlay decays toward zero and the state recovers.
        jitter: Bounded per-step multiplicative noise on the drive while active
            (``0`` == deterministic). Seeded via the framework RNG.
    """

    name: str
    coef: float
    intensity: float
    persistence: float
    remove_at: int | None = None
    jitter: float = 0.0

    def overlay(self, steps: int, seed: Seed = Seed(0)) -> np.ndarray:
        """The displacement ``p_t`` for ``t`` in ``0..steps`` (inclusive).

        ``p`` relaxes toward ``intensity`` while active and decays toward ``0``
        after ``remove_at``. Deterministic unless ``jitter > 0``, in which case
        the drive is perturbed by seeded noise (identical ``seed`` → identical
        overlay).
        """
        keep = self.persistence
        drive_target = self.intensity
        rng = seed.rng() if self.jitter > 0.0 else None

        out = np.empty(steps + 1, dtype=np.float64)
        p = 0.0
        for t in range(steps + 1):
            active = self.remove_at is None or t < self.remove_at
            drive = drive_target if active else 0.0
            if rng is not None and active and drive != 0.0:
                drive *= 1.0 + self.jitter * float(rng.uniform(-1.0, 1.0))
            p = p * keep + drive * (1.0 - keep)
            out[t] = p
        return out


def make_pressure(
    name: str,
    intensity: Level = "moderate",
    persistence: Level = "moderate",
    remove_at: int | None = None,
    jitter: float = 0.0,
) -> EnvironmentalPressure:
    """Build an :class:`EnvironmentalPressure`, resolving the named ladders.

    Args:
        name: Opaque pressure name; must be a key of :data:`NAMED_PRESSURES`.
        intensity: Named level (:data:`INTENSITY_LEVELS`) or a number >= 0.
        persistence: Named level (:data:`PERSISTENCE_LEVELS`) or a number in
            ``[0, 1)``.
        remove_at: Step index at which the pressure is lifted (``None`` = never).
        jitter: Bounded per-step multiplicative noise on the drive (>= 0).

    Raises:
        ValueError: unknown pressure name, an out-of-range level, a negative
            ``remove_at``, or a negative ``jitter``. No silent fallback.
    """
    if name not in NAMED_PRESSURES:
        raise ValueError(
            f"unknown environmental pressure {name!r}; "
            f"expected one of {sorted(NAMED_PRESSURES)}"
        )
    intens = _resolve_intensity(intensity)
    persist = _resolve_persistence(persistence)
    if remove_at is not None and remove_at < 0:
        raise ValueError(f"remove_at must be a non-negative step index; got {remove_at!r}")
    if not math.isfinite(jitter) or jitter < 0.0:
        raise ValueError(f"jitter must be a finite number >= 0; got {jitter!r}")
    return EnvironmentalPressure(
        name=name,
        coef=NAMED_PRESSURES[name],
        intensity=intens,
        persistence=persist,
        remove_at=remove_at,
        jitter=jitter,
    )
