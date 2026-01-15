"""Test actions for integration tests.

These actions are stubs that modify mock state for testing the agent interface.
Real implementations would interact with actual simulation state.
"""

from typing import Any

from alienbio import action


@action(summary="Add molecules to the system", targets="regions", cost=1.0)
def add_feedstock(state: dict[str, Any], molecule: str, amount: float) -> dict[str, Any]:
    """Add molecules to substrate."""
    new_state = dict(state)
    current = new_state.get(molecule, 0.0)
    new_state[molecule] = current + amount
    return new_state


@action(summary="Add molecules to the system", cost=2.0)
def add_molecule(state: dict[str, Any], molecule: str, amount: float) -> dict[str, Any]:
    """Add molecules to the system."""
    new_state = dict(state)
    current = new_state.get(molecule, 0.0)
    new_state[molecule] = current + amount
    return new_state


@action(summary="Remove molecules from the system", cost=2.0)
def remove_molecule(state: dict[str, Any], molecule: str, amount: float) -> dict[str, Any]:
    """Remove molecules from the system."""
    new_state = dict(state)
    current = new_state.get(molecule, 0.0)
    new_state[molecule] = max(0.0, current - amount)
    return new_state


@action(summary="Change temperature", targets="regions", cost=0.5)
def adjust_temp(state: dict[str, Any], temp: float) -> dict[str, Any]:
    """Adjust system temperature."""
    new_state = dict(state)
    current = new_state.get("temperature", 25.0)
    new_state["temperature"] = current + temp
    return new_state


@action(summary="Multiply a reaction rate", cost=3.0)
def adjust_rate(state: dict[str, Any], reaction: str, factor: float) -> dict[str, Any]:
    """Multiply a reaction rate by a factor."""
    new_state = dict(state)
    rates = new_state.get("_rates", {})
    current = rates.get(reaction, 1.0)
    rates[reaction] = current * factor
    new_state["_rates"] = rates
    return new_state


@action(summary="Set concentration of a molecule", cost=1.0)
def set_concentration(state: dict[str, Any], molecule: str, amount: float) -> dict[str, Any]:
    """Set the concentration of a molecule to a specific value."""
    new_state = dict(state)
    new_state[molecule] = amount
    return new_state


@action(summary="Advance simulation by N steps", cost=0.5)
def step(state: dict[str, Any], n: int = 1) -> dict[str, Any]:
    """Advance simulation by N steps (stub - just increments step counter)."""
    new_state = dict(state)
    current_step = new_state.get("_step", 0)
    new_state["_step"] = current_step + n
    return new_state


@action(summary="Submit findings report", cost=0.0)
def report(state: dict[str, Any], text: str) -> dict[str, Any]:
    """Submit a report (stores it in state for scoring)."""
    new_state = dict(state)
    reports = new_state.get("_reports", [])
    reports.append(text)
    new_state["_reports"] = reports
    return new_state


@action(summary="Submit hypothesis about hidden reaction", cost=0.0)
def submit_hypothesis(
    state: dict[str, Any], reactants: list[str], products: list[str]
) -> dict[str, Any]:
    """Submit a hypothesis about a hidden reaction."""
    new_state = dict(state)
    new_state["_hypothesis"] = {"reactants": reactants, "products": products}
    return new_state


# Timing test actions
@action(summary="Slow action for timing tests", cost=1.0, duration=2.0)
def slow_action(state: dict[str, Any]) -> dict[str, Any]:
    """Slow action that takes 2.0 time units."""
    new_state = dict(state)
    new_state["_slow_executed"] = True
    return new_state


@action(summary="Fast action for timing tests", cost=0.5, duration=0.1)
def fast_action(state: dict[str, Any]) -> dict[str, Any]:
    """Fast action that takes 0.1 time units."""
    new_state = dict(state)
    new_state["_fast_executed"] = True
    return new_state


@action(summary="Terminate all organisms", cost=5.0)
def kill_all(state: dict[str, Any]) -> dict[str, Any]:
    """Terminate all organisms (sets populations to zero)."""
    new_state = dict(state)
    for key in list(new_state.keys()):
        if not key.startswith("_"):
            new_state[key] = 0.0
    return new_state
