# World
**Subsystem**: [[execution]] > Simulation
Complete runnable setup.

## Description
World combines a biological container, generators, initial conditions, and simulator configuration into a complete runnable setup.

| Properties | Type | Description |
|----------|------|-------------|
| container | BioContainer | The biology being simulated |
| generators | dict | Named generators for expansion |
| initial_state | State | Starting concentrations |
| config | SimulatorConfig | Simulation parameters |

| Methods | Description |
|---------|-------------|
| run | Run simulation for specified duration |
| run_until | Run until predicate returns True |

## Protocol Definition
```python
from typing import Protocol

class World(Protocol):
    """Complete runnable simulation setup."""

    container: BioContainer
    generators: dict[str, Generator]
    initial_state: State
    config: "SimulatorConfig"

    def run(self, duration: float) -> Timeline:
        """Run simulation for specified duration."""
        ...

    def run_until(self, predicate: Callable[[State], bool]) -> Timeline:
        """Run until predicate returns True."""
        ...
```

## Methods
### run(duration) -> Timeline
Runs the simulation for the specified duration, returning full timeline.

### run_until(predicate) -> Timeline
Runs until the predicate function returns True for a state.

## See Also
- [[execution]]
- [[Simulator]] - Execution engine
- [[BioContainer]] - Container being simulated
