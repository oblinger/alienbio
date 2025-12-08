# Step
**Subsystem**: [[execution]] > Simulation
Single time advancement applying reactions.

## Description
Step represents a single time advancement in the simulation, computing reaction rates and updating concentrations accordingly.

| Properties | Type | Description |
|----------|------|-------------|
| dt | float | Time delta for this step |

| Methods | Description |
|---------|-------------|
| apply | Apply reactions to advance state by dt |

## Protocol Definition
```python
from typing import Protocol

class Step(Protocol):
    """Single time advancement."""

    dt: float  # time delta

    def apply(self, state: State, container: BioContainer) -> State:
        """Apply reactions to advance state by dt."""
        ...
```

## Methods
### apply(state, container) -> State
Computes all reaction rates from current concentrations, applies stoichiometric updates, handles transport, and returns the new state.

## Algorithm
1. For each reaction, compute rate from current concentrations
2. Compute concentration deltas: Δ[molecule] = rate × stoichiometry × dt
3. Apply transport reactions between compartments
4. Return new state with updated concentrations and timestamp

## See Also
- [[execution]]
- [[State]] - What gets updated
- [[Simulator]] - Orchestrates steps
