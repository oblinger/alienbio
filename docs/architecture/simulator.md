# Simulator
**Subsystem**: [[ABIO execution]] > Simulation
Execution engine for biology dynamics (single-compartment, legacy).

## Overview
Simulator is the protocol for execution engines that advance biological state through time. Two implementations exist: PythonSimulator (reference) and RustSimulator (performance). For multi-compartment simulations, use WorldSimulator instead.

| Property | Type | Description |
|----------|------|-------------|
| `chemistry` | Chemistry | The chemistry being simulated |
| `dt` | float | Time step size |

| Method | Returns | Description |
|--------|---------|-------------|
| `step(state)` | State | Advance state by one timestep |
| `run(state, steps)` | List[State] | Run simulation for multiple steps |

## Discussion

### Usage Example
```python
from alienbio import ReferenceSimulatorImpl, StateImpl

sim = ReferenceSimulatorImpl(chemistry=chem, dt=0.1)
state = StateImpl(chemistry=chem, initial={"glucose": 10.0})

# Single step
new_state = sim.step(state)

# Multiple steps
history = sim.run(state, steps=1000)
```

### Implementations

**PythonSimulator:**
- NumPy-based vectorized operations
- Clear, readable reference implementation
- Suitable for debugging and small systems

**RustSimulator:**
- PyO3 bindings expose same interface
- SIMD-optimized concentration updates
- 10-100x faster for large systems

### Relationship to WorldSimulator
- **Simulator**: Single-compartment, uses Chemistry
- **WorldSimulator**: Multi-compartment, uses CompartmentTree + Flows

## Protocol
```python
from typing import Protocol, List

class Simulator(Protocol):
    """Execution engine protocol (single-compartment)."""

    @property
    def chemistry(self) -> Chemistry:
        """The Chemistry being simulated."""
        ...

    @property
    def dt(self) -> float:
        """Time step size."""
        ...

    def step(self, state: State) -> State:
        """Advance state by one timestep."""
        ...

    def run(self, state: State, steps: int) -> List[State]:
        """Run simulation for specified steps."""
        ...
```

## See Also
- [[WorldSimulator]] - Multi-compartment simulator
- [[State]] - What gets simulated
- [[Chemistry]] - Molecules and reactions
- [[ABIO execution]] - Parent subsystem
