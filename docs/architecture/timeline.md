# Timeline
**Subsystem**: [[execution]] > Simulation
Sequence of states with intervention hooks.

## Description
Timeline records the history of states throughout a simulation run, supporting intervention hooks for applying perturbations at specific times.

| Properties | Type | Description |
|----------|------|-------------|
| states | list[State] | Recorded state history |
| interventions | list[tuple] | (time, function) pairs to apply |
| events | list[tuple] | (time, description) event log |

| Methods | Description |
|---------|-------------|
| add_intervention | Schedule an intervention at specified time |
| get_state_at | Get state at or before specified time |

## Protocol Definition
```python
from typing import Protocol, Callable

class Timeline(Protocol):
    """Sequence of states with interventions."""

    states: list[State]
    interventions: list[tuple[float, Callable[[State], State]]]
    events: list[tuple[float, str]]

    def add_intervention(self, time: float, fn: Callable[[State], State]) -> None:
        """Schedule an intervention at specified time."""
        ...

    def get_state_at(self, time: float) -> State:
        """Get state at or before specified time."""
        ...
```

## Methods
### add_intervention(time, fn)
Schedules a state transformation to apply at the specified simulation time.

### get_state_at(time) -> State
Returns the state at or immediately before the specified time.

## See Also
- [[execution]]
- [[State]] - Individual snapshots
- [[World]] - Contains timeline during run
