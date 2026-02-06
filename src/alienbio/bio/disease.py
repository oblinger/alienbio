"""Disease: baseline definitions, perturbation generation, symptom measurement."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .biosystem import BioSystem


@dataclass
class HealthRange:
    """Acceptable range for a molecule concentration."""

    molecule: str
    low: float
    high: float

    def contains(self, value: float) -> bool:
        return self.low <= value <= self.high


@dataclass
class Baseline:
    """Healthy baseline for a biological system.

    Defines steady-state concentrations and acceptable ranges.
    """

    steady_state: Dict[str, float]
    ranges: List[HealthRange]

    def is_healthy(self, concentrations: Dict[str, float]) -> bool:
        """Check if all concentrations are within healthy ranges."""
        for r in self.ranges:
            val = concentrations.get(r.molecule, 0.0)
            if not r.contains(val):
                return False
        return True


@dataclass
class Perturbation:
    """A perturbation that creates disease from a healthy system.

    Can alter reaction rates or remove reactions entirely.
    """

    name: str
    kind: str  # "rate_change" or "reaction_removal"
    target_reaction: str
    factor: Optional[float] = None  # for rate_change: multiply rate by this

    def apply(self, system: "BioSystem") -> None:
        """Apply perturbation to a system (modifies in-place)."""
        if self.kind == "reaction_removal":
            # Set rate to zero effectively
            rxn = system.chemistry.reactions[self.target_reaction]
            rxn.set_rate(0.0)
        elif self.kind == "rate_change":
            rxn = system.chemistry.reactions[self.target_reaction]
            current = rxn.rate
            factor = self.factor if self.factor is not None else 0.1
            if callable(current):
                orig = current
                rxn.set_rate(lambda s, _fn=orig, _f=factor: _fn(s) * _f)
            else:
                rxn.set_rate(current * factor)
        else:
            raise ValueError(f"Unknown perturbation kind: {self.kind!r}")


@dataclass
class Symptom:
    """An observable symptom — a measurement outside healthy range."""

    molecule: str
    value: float
    healthy_range: HealthRange
    deviation: float  # how far outside range


def measure_baseline(system: "BioSystem", steps: int = 500) -> Baseline:
    """Run system to steady state and measure baseline concentrations.

    Args:
        system: A healthy biological system
        steps: Number of steps to reach steady state

    Returns:
        Baseline with steady-state concentrations and default ranges (±20%)
    """
    system.run(steps)

    steady = {}
    for mol_name in system.chemistry.molecules:
        steady[mol_name] = system.state[mol_name]

    ranges = []
    for name, val in steady.items():
        margin = max(abs(val) * 0.2, 0.1)  # ±20% or at least ±0.1
        ranges.append(HealthRange(name, val - margin, val + margin))

    return Baseline(steady_state=steady, ranges=ranges)


def generate_perturbations(
    system: "BioSystem",
    *,
    seed: Optional[int] = None,
    kinds: Optional[List[str]] = None,
) -> List[Perturbation]:
    """Generate perturbations from a system's reactions.

    Creates one perturbation per reaction: either rate_change or reaction_removal.

    Args:
        system: The healthy system to perturb
        seed: Random seed for reproducibility
        kinds: Allowed perturbation kinds (default: both)

    Returns:
        List of possible perturbations
    """
    rng = random.Random(seed)
    allowed = kinds or ["rate_change", "reaction_removal"]

    perturbations = []
    for rxn_name in system.chemistry.reactions:
        kind = rng.choice(allowed)
        if kind == "rate_change":
            factor = rng.choice([0.1, 0.5, 2.0, 5.0])
            perturbations.append(Perturbation(
                name=f"{rxn_name}_rate_x{factor}",
                kind="rate_change",
                target_reaction=rxn_name,
                factor=factor,
            ))
        else:
            perturbations.append(Perturbation(
                name=f"{rxn_name}_removed",
                kind="reaction_removal",
                target_reaction=rxn_name,
            ))

    return perturbations


def detect_symptoms(
    concentrations: Dict[str, float],
    baseline: Baseline,
) -> List[Symptom]:
    """Detect symptoms by comparing concentrations to healthy ranges.

    Args:
        concentrations: Current molecule concentrations
        baseline: Healthy baseline with ranges

    Returns:
        List of symptoms (molecules outside healthy range)
    """
    symptoms = []
    for r in baseline.ranges:
        val = concentrations.get(r.molecule, 0.0)
        if not r.contains(val):
            if val < r.low:
                deviation = r.low - val
            else:
                deviation = val - r.high
            symptoms.append(Symptom(
                molecule=r.molecule,
                value=val,
                healthy_range=r,
                deviation=deviation,
            ))
    return symptoms
