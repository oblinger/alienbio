"""Simulator: step-based simulation protocol and base implementation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from .chemistry import BioChemistry
    from .state import State


class Simulator(ABC):
    """Abstract base for simulators.

    A Simulator advances the state of a chemical system over time.
    Subclasses implement the actual simulation algorithm.

    The basic interface:
    - step(state) -> state: advance one time step
    - run(state, n) -> [states]: run n steps, return timeline

    Example:
        sim = MySimulator(chemistry, dt=0.01)
        timeline = sim.run(initial_state, steps=100)
    """

    __slots__ = ("_chemistry", "_dt")

    def __init__(self, chemistry: BioChemistry, dt: float = 1.0) -> None:
        """Initialize simulator.

        Args:
            chemistry: The BioChemistry to simulate
            dt: Time step size (default 1.0)
        """
        self._chemistry = chemistry
        self._dt = dt

    @property
    def chemistry(self) -> BioChemistry:
        """The BioChemistry being simulated."""
        return self._chemistry

    @property
    def dt(self) -> float:
        """Time step size."""
        return self._dt

    @abstractmethod
    def step(self, state: State) -> State:
        """Advance the simulation by one time step.

        Args:
            state: Current system state

        Returns:
            New state after applying all reactions once
        """
        ...

    def run(self, state: State, steps: int) -> List[State]:
        """Run simulation for multiple steps.

        Args:
            state: Initial state
            steps: Number of steps to run

        Returns:
            Timeline of states (length = steps + 1, including initial)
        """
        timeline = [state.copy()]
        current = state.copy()

        for _ in range(steps):
            current = self.step(current)
            timeline.append(current.copy())

        return timeline


class SimpleSimulator(Simulator):
    """Basic simulator applying reactions once per step.

    This is a simple implementation suitable for testing.
    For each reaction:
    - Compute rate (constant or from rate function)
    - Subtract rate * coefficient from each reactant
    - Add rate * coefficient to each product

    Note: This is a naive implementation that doesn't handle
    kinetics properly. Real simulations need proper ODE solvers.
    """

    __slots__ = ()

    def step(self, state: State) -> State:
        """Apply all reactions once."""
        new_state = state.copy()

        for reaction in self._chemistry.iter_reactions():
            # Get effective rate for this state
            rate = reaction.get_rate(state) * self._dt

            # Apply reaction: consume reactants, produce products
            for molecule, coef in reaction.reactants.items():
                current = new_state.get_molecule(molecule)
                new_state.set_molecule(molecule, max(0.0, current - rate * coef))

            for molecule, coef in reaction.products.items():
                current = new_state.get_molecule(molecule)
                new_state.set_molecule(molecule, current + rate * coef)

        return new_state
