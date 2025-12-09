# State
**Subsystem**: [[ABIO execution]] > Simulation
Snapshot of molecule concentrations (single-compartment, legacy).

## Overview
State represents a snapshot of all molecule concentrations at a point in time for single-compartment simulations. For multi-compartment simulations, use WorldState instead.

| Property | Type | Description |
|----------|------|-------------|
| `timestamp` | float | Simulation time of this snapshot |
| `concentrations` | Dict[str, float] | Molecule name to concentration |

| Method | Returns | Description |
|--------|---------|-------------|
| `get(molecule, compartment)` | float | Get concentration of molecule |
| `copy()` | State | Create a deep copy of this state |

## Discussion

### Usage Example
```python
from alienbio import StateImpl

state = StateImpl(
    chemistry=chem,
    initial={"glucose": 10.0, "atp": 5.0}
)

# Access concentration
glucose_conc = state.get("glucose")

# Copy for simulation
new_state = state.copy()
```

### Relationship to WorldState
- **State**: Single-compartment, uses molecule names as strings
- **WorldState**: Multi-compartment, uses integer IDs for efficiency

## Protocol
```python
from typing import Protocol, Dict

class State(Protocol):
    """Snapshot of system concentrations (single-compartment)."""

    timestamp: float
    concentrations: Dict[str, float]

    def get(self, molecule: str) -> float:
        """Get concentration of molecule."""
        ...

    def copy(self) -> "State":
        """Create a deep copy of this state."""
        ...
```

## See Also
- [[WorldState]] - Multi-compartment state storage
- [[Simulator]] - Advances state
- [[Timeline]] - Sequence of states
- [[ABIO execution]] - Parent subsystem
