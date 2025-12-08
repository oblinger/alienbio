# BioOrganism
**Subsystem**: [[biology]] > Organisms
Complete organism with compartmentalized physiology.

## Description
BioOrganism represents a complete organism as a hierarchical DAG of compartments, from organelles up to the whole organism. It tracks cross-compartment transport, homeostatic targets, and signaling.

| Properties | Type | Description |
|----------|------|-------------|
| hierarchy | dict | Parent-child relationships between compartments |
| systems | dict | BioSystem for each compartment |
| homeostatic_targets | dict | Target concentration ranges |

| Methods | Description |
|---------|-------------|
| get_compartment_path | Get path from root to compartment |

## Protocol Definition
```python
from typing import Protocol

class BioOrganism(Entity, Protocol):
    """Complete organism with hierarchical physiology."""

    hierarchy: dict[str, list[str]]  # parent -> children
    systems: dict[str, BioSystem]  # compartment -> system
    homeostatic_targets: dict[str, tuple[float, float]]  # molecule -> (min, max)

    def get_compartment_path(self, compartment: str) -> list[str]:
        """Get path from root to compartment."""
        ...
```

## Methods
### get_compartment_path(compartment) -> list[str]
Get path from root to compartment.

## Hierarchy
Organisms have nested compartments:
```
organism
├── cell_1
│   ├── cytoplasm
│   ├── nucleus
│   └── mitochondria
├── cell_2
│   └── ...
└── extracellular
```

## See Also
- [[biology]]
- [[BioSystem]] - Individual compartment systems
- [[execution]] - Running organisms
