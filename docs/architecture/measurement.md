# Measurement

Function to observe system state.

**Subsystem**: [[execution]] > Interface

## Description
Measurement represents an observation function that agents can use to query aspects of the biological system. Measurements intentionally provide limited visibility.

## Protocol Definition
```python
from typing import Protocol, Any

class Measurement(Protocol):
    """Agent observation function."""

    name: str
    description: str

    def measure(self, world: World, **params) -> Any:
        """Take a measurement from the world."""
        ...
```

## Properties
| Property | Type | Description |
|----------|------|-------------|
| name | str | Measurement identifier |
| description | str | What this measures |

## Methods
### measure(world, **params) -> Any
Executes the measurement and returns the observation.

## Examples
- `measure_concentration("glucose", "cytoplasm")` → 0.42
- `detect_enzyme("kinase_A")` → True
- `measure_flux("glycolysis")` → 1.2

## See Also
- [[execution]]
- [[Action]] - Counterpart for modifications
- [[Task]] - Uses measurements
