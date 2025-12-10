# Measurement
**Subsystem**: [[ABIO execution]] > Interface
Function to observe system state.

## Overview
Measurement represents an observation function that agents can use to query aspects of the biological system. Measurements intentionally provide limited visibility - agents don't get complete state.

| Property | Type | Description |
|----------|------|-------------|
| `name` | str | Measurement identifier |
| `description` | str | What this measures |

| Method | Returns | Description |
|--------|---------|-------------|
| `measure(world, **params)` | Any | Take a measurement from the world |

## Discussion

### Examples
- `measure_concentration("glucose", "cytoplasm")` → 0.42
- `detect_enzyme("kinase_A")` → True
- `measure_flux("glycolysis")` → 1.2

### Usage
```python
measurement = Measurement(
    name="blood_glucose",
    description="Measure blood glucose level"
)

glucose_level = measurement.measure(world, compartment="blood")
```

## Protocol
```python
from typing import Protocol, Any

class Measurement(Protocol):
    """Agent observation function."""

    name: str
    description: str

    def measure(self, world: World, **params: Any) -> Any:
        """Take a measurement from the world."""
        ...
```

## See Also
- [[Action]] - Counterpart for modifications
- [[Task]] - Uses measurements
- [[ABIO execution]] - Parent subsystem
