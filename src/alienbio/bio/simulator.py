"""Simulator: step-based simulation protocol and base implementation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, TYPE_CHECKING

from alienbio.protocols.bio import Simulator

if TYPE_CHECKING:
    from .chemistry import ChemistryImpl
    from .state import StateImpl


class SimulatorBase(ABC):
    """Abstract base class for simulators.

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

    def __init__(self, chemistry: ChemistryImpl, dt: float = 1.0) -> None:
        """Initialize simulator.

        Args:
            chemistry: The Chemistry to simulate
            dt: Time step size (default 1.0)
        """
        self._chemistry = chemistry
        self._dt = dt

    @property
    def chemistry(self) -> ChemistryImpl:
        """The Chemistry being simulated."""
        return self._chemistry

    @property
    def dt(self) -> float:
        """Time step size."""
        return self._dt

    @abstractmethod
    def step(self, state: StateImpl) -> StateImpl:
        """Advance the simulation by one time step.

        Args:
            state: Current system state

        Returns:
            New state after applying all reactions once
        """
        ...

    def run(self, state: StateImpl, steps: int) -> List[StateImpl]:
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


class ReferenceSimulatorImpl(SimulatorBase):
    """Reference implementation: Basic simulator applying reactions once per step.

    This is the reference implementation for testing and validation.
    Each step is order-independent and simultaneous (H4):

    - Every reaction's desired extent is computed from the SAME frozen
      start-of-step state (rate * dt).
    - Competition for shared reactants is resolved so no molecule goes
      negative, using single-pass proportional min-ratio scaling: for each
      molecule ``demand = Σ_reactions extent * consumption_coef`` and
      ``ratio = min(1, available / demand)``; each reaction scales by the
      tightest ratio over its own reactants. This is a provably
      non-negative, order-independent, mass-conserving simultaneous scheme
      (an "equivalent scheme" per the H4 spec). One pass suffices for
      correctness: for any molecule m the total consumption is
      ``Σ_r desired_r · scale_r · coef_r(m) ≤ ratio_m · demand_m ≤ available_m``
      because ``scale_r ≤ ratio_m`` for every reactant m of r. It also
      reduces exactly to the C1 single-substrate clamp when reactions do not
      compete. (A multiplicative iterative relaxation was rejected: it only
      shrinks scales monotonically and never reclaims freed capacity, so it
      is strictly more conservative than the single-pass fixed point.)
    - All final extents are applied simultaneously to a fresh copy.

    Note: This is a simple Euler-style implementation. For more
    accurate kinetics, use specialized simulators (JAX, etc.).
    """

    __slots__ = ()

    def step(self, state: StateImpl) -> StateImpl:
        """Apply all reactions once, with order-independent simultaneous extent.

        H4 fix: reactions are no longer applied one-at-a-time reading each
        other's partial updates (which made the result depend on reaction
        ordering and let two reactions sharing a reactant jointly over-consume).
        Instead every reaction's desired extent is computed from the SAME
        frozen start-of-step state, competition for shared reactants is resolved
        by a single-pass proportional min-ratio scaling (see module note below),
        and all final extents are applied simultaneously to a fresh copy.
        """
        new_state = state.copy()
        reactions = list(self._chemistry.reactions.values())

        # 1. Desired extent for every reaction, from the FROZEN start state.
        desired: List[float] = []
        for reaction in reactions:
            rate = reaction.get_rate(state) * self._dt
            desired.append(max(0.0, rate))

        # 2. Resolve competition. demand[m] = total consumption of molecule m
        #    across all reactions at their desired extents (frozen state).
        demand: dict = {}
        for reaction, ext in zip(reactions, desired):
            if ext <= 0.0:
                continue
            for molecule, coef in reaction.reactants.items():
                if coef > 0:
                    demand[molecule.name] = (
                        demand.get(molecule.name, 0.0) + ext * coef
                    )

        # Per-molecule feasible fraction: min(1, available / demand).
        ratio: dict = {}
        for reaction in reactions:
            for molecule, coef in reaction.reactants.items():
                if coef > 0 and molecule.name in demand and molecule.name not in ratio:
                    dem = demand[molecule.name]
                    avail = state.get_molecule(molecule)
                    ratio[molecule.name] = min(1.0, avail / dem) if dem > 0 else 1.0

        # Each reaction scales by the tightest fraction over its reactants.
        extents: List[float] = []
        for reaction, ext in zip(reactions, desired):
            scale = 1.0
            for molecule, coef in reaction.reactants.items():
                if coef > 0:
                    scale = min(scale, ratio.get(molecule.name, 1.0))
            extents.append(ext * scale)

        # 3. Apply all reactions SIMULTANEOUSLY to the fresh copy.
        for reaction, ext in zip(reactions, extents):
            for molecule, coef in reaction.reactants.items():
                new_state.set_molecule(
                    molecule, new_state.get_molecule(molecule) - ext * coef
                )
            for molecule, coef in reaction.products.items():
                new_state.set_molecule(
                    molecule, new_state.get_molecule(molecule) + ext * coef
                )

        return new_state
