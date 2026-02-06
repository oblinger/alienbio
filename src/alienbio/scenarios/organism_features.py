"""Organism features: maintained molecules, operating envelope, reproduction, predation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, TYPE_CHECKING

if TYPE_CHECKING:
    from ..bio.world_state import WorldStateImpl

MoleculeId = int
CompartmentId = int


@dataclass
class MaintainedMolecule:
    """An enzyme or molecule kept at constant concentration in a compartment.

    At each step, the concentration is clamped back to the target value,
    simulating active regulation (e.g., enzyme homeostasis).
    """

    molecule_id: MoleculeId
    compartment_id: CompartmentId
    target_concentration: float


@dataclass
class EnvelopeBound:
    """A survival range for a molecule in a compartment.

    If the concentration goes outside [low, high], the organism is in
    violation — potentially lethal.
    """

    molecule_id: MoleculeId
    compartment_id: CompartmentId
    low: float
    high: float

    def contains(self, value: float) -> bool:
        return self.low <= value <= self.high


@dataclass
class OperatingEnvelope:
    """Survival ranges for an organism's molecules across compartments.

    Defines bounds on molecule concentrations. If any bound is violated,
    the organism is outside its operating envelope.
    """

    bounds: List[EnvelopeBound] = field(default_factory=list)

    def add(
        self,
        molecule_id: MoleculeId,
        compartment_id: CompartmentId,
        low: float,
        high: float,
    ) -> None:
        self.bounds.append(EnvelopeBound(molecule_id, compartment_id, low, high))

    def check(self, state: "WorldStateImpl") -> EnvelopeStatus:
        """Check all bounds against current state."""
        violations = []
        for bound in self.bounds:
            val = state.get(bound.compartment_id, bound.molecule_id)
            if not bound.contains(val):
                violations.append(EnvelopeViolation(
                    bound=bound,
                    actual=val,
                    deviation=val - bound.high if val > bound.high else bound.low - val,
                ))
        return EnvelopeStatus(
            viable=len(violations) == 0,
            violations=violations,
        )


@dataclass
class EnvelopeViolation:
    """A single violation of the operating envelope."""

    bound: EnvelopeBound
    actual: float
    deviation: float  # positive = how far outside range


@dataclass
class EnvelopeStatus:
    """Result of checking the operating envelope."""

    viable: bool
    violations: List[EnvelopeViolation]


@dataclass
class ReproductionThreshold:
    """Molecule levels required for reproduction.

    All thresholds must be met simultaneously for the organism
    to be able to reproduce.
    """

    thresholds: Dict[MoleculeId, float] = field(default_factory=dict)

    def add(self, molecule_id: MoleculeId, min_concentration: float) -> None:
        self.thresholds[molecule_id] = min_concentration

    def can_reproduce(
        self,
        state: "WorldStateImpl",
        compartment_id: CompartmentId,
    ) -> bool:
        """Check if all molecule thresholds are met in the given compartment."""
        for mol_id, min_conc in self.thresholds.items():
            if state.get(compartment_id, mol_id) < min_conc:
                return False
        return True

    def shortfall(
        self,
        state: "WorldStateImpl",
        compartment_id: CompartmentId,
    ) -> Dict[MoleculeId, float]:
        """Return how much each molecule falls short of its threshold.

        Returns empty dict if all thresholds are met.
        Only includes molecules that are below threshold.
        """
        result: Dict[MoleculeId, float] = {}
        for mol_id, min_conc in self.thresholds.items():
            actual = state.get(compartment_id, mol_id)
            if actual < min_conc:
                result[mol_id] = min_conc - actual
        return result


@dataclass
class PredationRule:
    """Predation: one species consuming another.

    Models predation as: predator in compartment consumes prey_molecule
    and gains energy_molecule at a rate proportional to both populations.

    Rate = predation_rate * [predator] * [prey]
    """

    predator_molecule_id: MoleculeId
    prey_molecule_id: MoleculeId
    energy_molecule_id: MoleculeId
    predation_rate: float
    conversion_efficiency: float = 0.5  # fraction of prey converted to energy


def apply_maintained_molecules(
    maintained: List[MaintainedMolecule],
    state: "WorldStateImpl",
) -> None:
    """Clamp maintained molecules back to their target concentrations."""
    for m in maintained:
        state.set(m.compartment_id, m.molecule_id, m.target_concentration)


def apply_predation(
    rules: List[PredationRule],
    state: "WorldStateImpl",
    compartment_id: CompartmentId,
    dt: float,
) -> None:
    """Apply predation rules in a compartment.

    For each rule: predator eats prey at rate proportional to both populations.
    Prey decreases, predator's energy molecule increases.
    """
    for rule in rules:
        predator_conc = state.get(compartment_id, rule.predator_molecule_id)
        prey_conc = state.get(compartment_id, rule.prey_molecule_id)

        # Lotka-Volterra style: consumption rate = k * predator * prey
        consumption = rule.predation_rate * predator_conc * prey_conc * dt

        # Don't consume more prey than exists
        consumption = min(consumption, prey_conc)

        # Update concentrations
        state.set(
            compartment_id,
            rule.prey_molecule_id,
            prey_conc - consumption,
        )
        current_energy = state.get(compartment_id, rule.energy_molecule_id)
        state.set(
            compartment_id,
            rule.energy_molecule_id,
            current_energy + consumption * rule.conversion_efficiency,
        )
