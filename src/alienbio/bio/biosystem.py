"""BioSystem: unified container combining chemistry, state, and simulation."""

from __future__ import annotations

import random
from typing import List, Optional

from .chemistry import ChemistryImpl
from .state import StateImpl
from .simulator import ReferenceSimulatorImpl, SimulatorBase


class BioSystem:
    """A complete biological system: chemistry + state + simulator.

    BioSystem wraps a Chemistry (molecules and reactions), a State
    (concentrations), and a Simulator into a single convenient object.

    Example:
        system = BioSystem(chemistry, state)
        timeline = system.run(steps=100)

        # With random initial concentrations
        system = BioSystem.random(chemistry, seed=42)
    """

    __slots__ = ("_chemistry", "_state", "_simulator")

    def __init__(
        self,
        chemistry: ChemistryImpl,
        state: Optional[StateImpl] = None,
        *,
        simulator: Optional[SimulatorBase] = None,
        dt: float = 1.0,
    ) -> None:
        self._chemistry = chemistry
        self._state = state if state is not None else StateImpl(chemistry)
        self._simulator = simulator or ReferenceSimulatorImpl(chemistry, dt=dt)

    @classmethod
    def random(
        cls,
        chemistry: ChemistryImpl,
        *,
        seed: Optional[int] = None,
        min_conc: float = 0.0,
        max_conc: float = 10.0,
        dt: float = 1.0,
    ) -> BioSystem:
        """Create a BioSystem with random initial concentrations."""
        rng = random.Random(seed)
        initial = {
            name: rng.uniform(min_conc, max_conc)
            for name in chemistry.molecules
        }
        state = StateImpl(chemistry, initial=initial)
        return cls(chemistry, state, dt=dt)

    @property
    def chemistry(self) -> ChemistryImpl:
        return self._chemistry

    @property
    def state(self) -> StateImpl:
        return self._state

    @state.setter
    def state(self, value: StateImpl) -> None:
        self._state = value

    @property
    def simulator(self) -> SimulatorBase:
        return self._simulator

    @property
    def num_molecules(self) -> int:
        return len(self._chemistry.molecules)

    @property
    def num_reactions(self) -> int:
        return len(self._chemistry.reactions)

    def step(self) -> StateImpl:
        """Advance one time step, updating internal state."""
        self._state = self._simulator.step(self._state)
        return self._state

    def run(self, steps: int) -> List[StateImpl]:
        """Run simulation for multiple steps.

        Updates internal state to the final state.
        Returns the full timeline including initial state.
        """
        timeline = self._simulator.run(self._state, steps)
        self._state = timeline[-1].copy()
        return timeline

    def __repr__(self) -> str:
        return (
            f"BioSystem(molecules={self.num_molecules}, "
            f"reactions={self.num_reactions}, dt={self._simulator.dt})"
        )
