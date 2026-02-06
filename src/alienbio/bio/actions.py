"""Actions: perturb system state."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from .state import StateImpl


@dataclass
class ActionSpec:
    """Specification for an action type."""

    name: str
    description: str
    params: Dict[str, str]
    cost: float = 1.0


class AddMoleculeAction:
    """Add a specified amount of a molecule to the state."""

    name = "add_molecule"
    description = "Add molecules to the system"
    params = {"molecule": "str", "amount": "float"}

    def apply(self, state: StateImpl, molecule: str, amount: float) -> StateImpl:
        """Add amount to the named molecule's concentration.

        Returns a new state (does not modify the original).
        """
        new_state = state.copy()
        current = new_state[molecule]
        new_state[molecule] = current + amount
        return new_state


class RemoveMoleculeAction:
    """Remove a specified amount of a molecule from the state."""

    name = "remove_molecule"
    description = "Remove molecules from the system"
    params = {"molecule": "str", "amount": "float"}

    def apply(self, state: StateImpl, molecule: str, amount: float) -> StateImpl:
        """Remove amount from the named molecule's concentration.

        Clamps at zero. Returns a new state.
        """
        new_state = state.copy()
        current = new_state[molecule]
        new_state[molecule] = max(0.0, current - amount)
        return new_state


class SetConcentrationAction:
    """Set a molecule's concentration to a specific value."""

    name = "set_concentration"
    description = "Set a molecule's concentration"
    params = {"molecule": "str", "value": "float"}

    def apply(self, state: StateImpl, molecule: str, value: float) -> StateImpl:
        """Set the named molecule to the specified concentration.

        Returns a new state.
        """
        new_state = state.copy()
        new_state[molecule] = value
        return new_state


class AdjustRateAction:
    """Adjust a reaction's rate constant."""

    name = "adjust_rate"
    description = "Adjust a reaction's rate"
    params = {"reaction": "str", "factor": "float"}

    def apply(
        self,
        state: StateImpl,
        reaction_name: str,
        factor: float,
    ) -> StateImpl:
        """Scale the named reaction's rate by factor.

        Modifies the reaction in-place (rates are shared across states).
        Returns the same state unchanged (rate is on the reaction, not the state).
        """
        reaction = state.chemistry.reactions[reaction_name]
        current_rate = reaction.rate
        if callable(current_rate):
            # For function rates, wrap with scaling factor
            original_fn = current_rate
            reaction.set_rate(lambda s, _fn=original_fn, _f=factor: _fn(s) * _f)
        else:
            reaction.set_rate(current_rate * factor)
        return state
