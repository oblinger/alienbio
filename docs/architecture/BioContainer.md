# BioContainer
**Subsystem**: [[ABIO biology]] > BioContainers
Nestable container for molecules, reactions, and child containers.

## Description
BioContainer is an **Entity subclass** representing biological containment structures - from organelles to whole organisms. As an Entity, it participates in the standard tree structure with parent/child relationships, DAT anchoring, and serialization.

Containers can nest arbitrarily, with transport reactions moving molecules across boundaries. The `kind` label documents the biological level but doesn't affect behavior.

### Relationship to Other Entity Types
| Entity Type | Purpose |
|-------------|---------|
| **BioMolecule** | Chemical species |
| **BioReaction** | Transformations |
| **BioChemistry** | Flat container (molecules + reactions) |
| **BioContainer** | Hierarchical container with nesting and kind labels |
| **BioPathway** | Analytical grouping of reactions |

| Properties | Type | Description |
|----------|------|-------------|
| name | str | Container identifier |
| kind | str | Level label: organism, organ, cell, organelle, etc. |
| molecules | set[BioMolecule] | Molecules present in this container |
| reactions | set[BioReaction] | Reactions active in this container |
| children | list[BioContainer] | Nested sub-containers |
| transport | list[BioReaction] | Cross-boundary transport reactions |
| concentrations | dict[str, float] | Current molecule concentrations |
| homeostatic_targets | dict[str, tuple] | Optional target concentration ranges |

| Methods | Description |
|---------|-------------|
| get_concentration | Get concentration of molecule |
| set_concentration | Set concentration of molecule |
| flatten | Get all molecules/reactions including children |

## Protocol Definition
```python
from typing import Protocol

class BioContainer(Entity, Protocol):
    """Nestable biological container."""

    name: str
    kind: str  # "organism", "organ", "cell", "organelle", etc.
    molecules: set[BioMolecule]
    reactions: set[BioReaction]
    children: list["BioContainer"]
    transport: list[BioReaction]  # cross-boundary reactions
    concentrations: dict[str, float]
    homeostatic_targets: dict[str, tuple[float, float]]  # molecule -> (min, max)

    def get_concentration(self, molecule: str) -> float:
        """Get concentration of molecule in this container."""
        ...

    def set_concentration(self, molecule: str, value: float) -> None:
        """Set concentration of molecule in this container."""
        ...

    def flatten(self) -> tuple[set[BioMolecule], set[BioReaction]]:
        """Get all molecules and reactions including from children."""
        ...
```

## Methods
### get_concentration(molecule) -> float
Get concentration of molecule in this container.

### set_concentration(molecule, value)
Set concentration of molecule in this container.

### flatten() -> tuple[set, set]
Recursively collects all molecules and reactions from this container and all children.

## Container Kinds
The `kind` field is a semantic label, not a behavioral distinction:
- **organism** - Top-level biological entity
- **organ** - Functional unit within organism
- **cell** - Individual cellular unit
- **organelle** - Sub-cellular compartment (mitochondria, nucleus, etc.)
- **compartment** - Generic sub-region

## Nesting Example
```
BioContainer(kind="organism")
├── BioContainer(kind="cell", name="cell_1")
│   ├── BioContainer(kind="organelle", name="cytoplasm")
│   ├── BioContainer(kind="organelle", name="nucleus")
│   └── BioContainer(kind="organelle", name="mitochondria")
├── BioContainer(kind="cell", name="cell_2")
│   └── ...
└── BioContainer(kind="compartment", name="extracellular")
```

## Transport
Transport reactions move molecules between a container and its parent or siblings. They're stored in the `transport` list and reference molecules in both containers.

## See Also
- [[ABIO biology]]
- [[BioMolecule]] - What containers hold
- [[BioReaction]] - What happens inside containers
- [[World]] - Wraps a container for simulation
