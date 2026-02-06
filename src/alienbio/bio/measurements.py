"""Measurements: observe limited aspects of system state."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from .state import StateImpl


@dataclass
class MeasurementSpec:
    """Specification for a measurement type."""

    name: str
    description: str
    params: Dict[str, str]
    cost: float = 0.0


class ConcentrationMeasurement:
    """Measure the concentration of a molecule in the current state."""

    name = "concentration"
    description = "Measure the concentration of a specific molecule"
    params = {"molecule": "str"}

    def measure(self, state: StateImpl, molecule: str) -> float:
        """Return the concentration of the named molecule."""
        return state[molecule]


class AllConcentrationsMeasurement:
    """Measure all concentrations in the current state."""

    name = "all_concentrations"
    description = "Measure all molecule concentrations"
    params: Dict[str, str] = {}

    def measure(self, state: StateImpl) -> Dict[str, float]:
        """Return all molecule concentrations as a dict."""
        return {name: state[name] for name in state}


class RateMeasurement:
    """Measure the effective rate of a reaction at the current state."""

    name = "rate"
    description = "Measure the effective rate of a specific reaction"
    params = {"reaction": "str"}

    def measure(
        self,
        state: StateImpl,
        reaction_name: str,
    ) -> float:
        """Return the effective rate of the named reaction."""
        reaction = state.chemistry.reactions[reaction_name]
        return reaction.get_rate(state)


class MoleculeCountMeasurement:
    """Measure the number of molecules in the chemistry."""

    name = "molecule_count"
    description = "Count the number of molecule species"
    params: Dict[str, str] = {}

    def measure(self, state: StateImpl) -> int:
        """Return the number of molecules."""
        return len(state.chemistry.molecules)


class ReactionCountMeasurement:
    """Measure the number of reactions in the chemistry."""

    name = "reaction_count"
    description = "Count the number of reactions"
    params: Dict[str, str] = {}

    def measure(self, state: StateImpl) -> int:
        """Return the number of reactions."""
        return len(state.chemistry.reactions)
