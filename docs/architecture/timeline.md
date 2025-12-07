# Timeline

Sequence of states with intervention hooks.

**Subsystem**: [[execution]] > Simulation

## Description
Timeline records the history of states throughout a simulation run, supporting intervention hooks for applying perturbations at specific times.

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

## Properties
| Property | Type | Description |
|----------|------|-------------|
| states | list[State] | Recorded state history |
| interventions | list[tuple] | (time, function) pairs to apply |
| events | list[tuple] | (time, description) event log |

## Methods
### add_intervention(time, fn)
Schedules a state transformation to apply at the specified simulation time.

### get_state_at(time) -> State
Returns the state at or immediately before the specified time.

## See Also
- [[simulation|Simulation Subsystem]]
- [[state|State]] - Individual snapshots
- [[world|World]] - Contains timeline during run
