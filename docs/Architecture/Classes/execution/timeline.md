 [[Architecture Docs]] → [[ABIO execution]]

# Timeline

Sequence of states with intervention hooks.

## Overview
Timeline records the history of states throughout a simulation run, supporting intervention hooks for applying perturbations at specific times.

| Property | Type | Description |
|----------|------|-------------|
| `states` | List[State] | Recorded state history |
| `interventions` | List[tuple] | (time, function) pairs to apply |
| `events` | List[tuple] | (time, description) event log |

| Method | Returns | Description |
|--------|---------|-------------|
| `add_intervention(time, fn)` | None | Schedule intervention at time |
| `get_state_at(time)` | State | Get state at or before time |

## Discussion

### Usage Example
```python
from alienbio import Timeline

timeline = Timeline()

# Schedule an intervention
def add_glucose(state):
    state.set("glucose", state.get("glucose") + 100)
    return state

timeline.add_intervention(time=50.0, fn=add_glucose)

# Access history
final_state = timeline.states[-1]
state_at_25 = timeline.get_state_at(25.0)
```

### Interventions
Interventions are functions that transform state at specific times:

```python
# Drug addition at t=100
timeline.add_intervention(100.0, lambda s: add_drug(s, "insulin", 50.0))

# Stress response at t=200
timeline.add_intervention(200.0, lambda s: apply_stress(s, factor=2.0))
```

## Protocol
```python
from typing import Protocol, List, Tuple, Callable

class Timeline(Protocol):
    """Sequence of states with interventions."""

    states: List[State]
    interventions: List[Tuple[float, Callable[[State], State]]]
    events: List[Tuple[float, str]]

    def add_intervention(self, time: float, fn: Callable[[State], State]) -> None:
        """Schedule an intervention at specified time."""
        ...

    def get_state_at(self, time: float) -> State:
        """Get state at or before specified time."""
        ...
```

## See Also
- [[State]] - Individual snapshots
- [[WorldState]] - Multi-compartment state
- [[Simulator]] - Produces timelines
- [[ABIO execution]] - Parent subsystem
