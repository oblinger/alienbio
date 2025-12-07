# State

Snapshot of molecule concentrations.

**Subsystem**: [[execution]] > Simulation

## Description
State represents a snapshot of all molecule concentrations at a point in time. It's the fundamental data structure that simulation operates on.

## Protocol Definition
```python
from typing import Protocol
import numpy as np

class State(Protocol):
    """Snapshot of system concentrations."""

    timestamp: float
    concentrations: dict[str, np.ndarray]  # compartment -> concentration vector

    def get(self, molecule: str, compartment: str) -> float:
        """Get concentration of molecule in compartment."""
        ...

    def copy(self) -> "State":
        """Create a deep copy of this state."""
        ...
```

## Properties
| Property | Type | Description |
|----------|------|-------------|
| timestamp | float | Simulation time of this snapshot |
| concentrations | dict | Compartment name to numpy concentration vector |

## Methods
### get(molecule, compartment) -> float
Returns the concentration of a specific molecule in a compartment.

### copy() -> State
Creates a deep copy suitable for modification without affecting original.

## See Also
- [[simulation|Simulation Subsystem]]
- [[step|Step]] - Advances state
- [[timeline|Timeline]] - Sequence of states
