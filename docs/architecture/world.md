# World
**Subsystem**: [[ABIO execution]] > Simulation
Complete runnable setup for simulation.

## Overview
World combines a biological container, generators, initial conditions, and simulator configuration into a complete runnable setup.

| Property | Type | Description |
|----------|------|-------------|
| `container` | BioContainer | The biology being simulated |
| `generators` | Dict[str, Generator] | Named generators for expansion |
| `initial_state` | State | Starting concentrations |
| `config` | SimulatorConfig | Simulation parameters |

| Method | Returns | Description |
|--------|---------|-------------|
| `run(duration)` | Timeline | Run simulation for specified duration |
| `run_until(predicate)` | Timeline | Run until predicate returns True |

## Discussion

### Usage Example
```python
from alienbio import World

world = World(
    container=chem,
    initial_state=state,
    config=SimulatorConfig(dt=0.1),
)

timeline = world.run(duration=100.0)
final_state = timeline.states[-1]
```

## Protocol
```python
from typing import Protocol, Dict, Callable

class World(Protocol):
    """Complete runnable simulation setup."""

    container: BioContainer
    generators: Dict[str, Generator]
    initial_state: State
    config: SimulatorConfig

    def run(self, duration: float) -> Timeline:
        """Run simulation for specified duration."""
        ...

    def run_until(self, predicate: Callable[[State], bool]) -> Timeline:
        """Run until predicate returns True."""
        ...
```

## See Also
- [[Simulator]] - Execution engine
- [[Timeline]] - Simulation results
- [[Chemistry]] - Container being simulated
- [[ABIO execution]] - Parent subsystem
