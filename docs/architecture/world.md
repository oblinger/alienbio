# World

Complete runnable setup.

**Subsystem**: [[execution]] > Simulation

## Description
World combines a biological system, generators, initial conditions, and simulator configuration into a complete runnable setup.

## Protocol Definition
```python
from typing import Protocol

class World(Protocol):
    """Complete runnable simulation setup."""

    system: BioSystem | BioOrganism
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

## Properties
| Property | Type | Description |
|----------|------|-------------|
| system | BioSystem or BioOrganism | The biology being simulated |
| generators | dict | Named generators for expansion |
| initial_state | State | Starting concentrations |
| config | SimulatorConfig | Simulation parameters |

## Methods
### run(duration) -> Timeline
Runs the simulation for the specified duration, returning full timeline.

### run_until(predicate) -> Timeline
Runs until the predicate function returns True for a state.

## See Also
- [[execution]]
- [[Simulator]] - Execution engine
- [[BioSystem]] - System being simulated
