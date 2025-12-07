# BioOrganism

Complete organism with compartmentalized physiology.

**Subsystem**: [[biology]] > Organisms

## Description
BioOrganism represents a complete organism as a hierarchical DAG of compartments, from organelles up to the whole organism. It tracks cross-compartment transport, homeostatic targets, and signaling.

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

## Properties
| Property | Type | Description |
|----------|------|-------------|
| hierarchy | dict | Parent-child relationships between compartments |
| systems | dict | BioSystem for each compartment |
| homeostatic_targets | dict | Target concentration ranges |

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
- [[infra]]
- [[BioSystem]] - Individual compartment systems
- [[execution]] - Running organisms
