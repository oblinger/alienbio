# Simulator
**Subsystem**: [[execution]] > Simulation
Execution engine for biology dynamics.

## Description
Simulator is the protocol for execution engines that advance biological state through time. Two implementations exist: PythonSimulator (reference) and RustSimulator (performance).

| Methods | Description |
|---------|-------------|
| step | Advance state by one timestep |
| run | Run simulation for specified duration |
| run_until | Run until predicate is satisfied |

## Protocol Definition
```python
from typing import Protocol

class Simulator(Protocol):
    """Execution engine protocol."""

    def step(self, state: State, container: BioContainer, dt: float) -> State:
        """Advance state by one timestep."""
        ...

    def run(self, world: World, duration: float) -> Timeline:
        """Run simulation for specified duration."""
        ...

    def run_until(self, world: World, predicate: Callable[[State], bool]) -> Timeline:
        """Run until predicate is satisfied."""
        ...
```

## Methods
### step(state, container, dt) -> State
Advances the state by a single timestep dt.

### run(world, duration) -> Timeline
Runs the full simulation, recording states and applying interventions.

### run_until(world, predicate) -> Timeline
Runs until the predicate returns True.

## Implementations
### PythonSimulator
- NumPy-based vectorized operations
- Clear, readable reference implementation
- Suitable for debugging and small systems

### RustSimulator
- PyO3 bindings expose same interface
- SIMD-optimized concentration updates
- 10-100x faster for large systems

## See Also
- [[execution]]
- [[State]] - What gets simulated
- [[World]] - Complete setup
