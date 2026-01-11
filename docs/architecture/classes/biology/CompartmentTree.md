 [[Architecture Docs]] → [[ABIO biology]]

# CompartmentTree

Hierarchical topology of compartments for efficient simulation.

## Overview
CompartmentTree represents the nested structure of biological compartments (Organism > Organ > Cell > Organelle). It uses integer IDs for efficient access and is stored separately from concentrations for fast updates. Provides parent/child relationships for flow calculations.

| Property | Type | Description |
|----------|------|-------------|
| `num_compartments` | int | Total compartment count |
| `parents` | List[Optional[int]] | Parent ID for each compartment |
| `children` | Dict[int, List[int]] | Children list for each parent |
| `names` | List[str] | Human-readable names |

| Method | Returns | Description |
|--------|---------|-------------|
| `parent(child)` | Optional[int] | Get parent (None for root) |
| `children(parent)` | List[int] | Get children |
| `root()` | int | Get root compartment ID |
| `is_root(comp)` | bool | Check if root |
| `add_root(name)` | int | Add root, returns ID |
| `add_child(parent, name)` | int | Add child, returns ID |

## Discussion

### Usage Example
```python
from alienbio import CompartmentTreeImpl

# Build tree: organism with organs and cells
tree = CompartmentTreeImpl()
organism = tree.add_root("organism")        # ID: 0
heart = tree.add_child(organism, "heart")   # ID: 1
liver = tree.add_child(organism, "liver")   # ID: 2
cell_1 = tree.add_child(heart, "cell_1")    # ID: 3
cell_2 = tree.add_child(heart, "cell_2")    # ID: 4

# Navigate
print(tree.parent(cell_1))     # 1 (heart)
print(tree.children(organism)) # [1, 2] (heart, liver)
print(tree.children(heart))    # [3, 4] (cell_1, cell_2)

# Visualize
print(tree)
# organism (0)
# ├── heart (1)
# │   ├── cell_1 (3)
# │   └── cell_2 (4)
# └── liver (2)
```

### Example Structure
```
organism (0)
├── organ_a (1)
│   ├── cell_1 (3)
│   │   ├── mitochondria (5)
│   │   └── nucleus (6)
│   └── cell_2 (4)
└── organ_b (2)
```

Each membrane (parent-child boundary) can have Flows that transport molecules.

### Tree Invariants
1. Exactly one root (parent = None)
2. All non-root compartments have exactly one parent
3. No cycles
4. IDs are contiguous: 0, 1, 2, ..., N-1

### Topology Changes
The tree structure changes rarely (e.g., cell division). When it does:
1. Add new compartments with `add_child()`
2. Expand WorldState to include new compartments
3. Initialize new compartment concentrations

### Serialization
```yaml
parents: [null, 0, 0, 1, 1]  # null = root
names: ["organism", "heart", "liver", "cell_1", "cell_2"]
```

## Protocol
```python
from typing import Protocol, List, Optional, runtime_checkable

@runtime_checkable
class CompartmentTree(Protocol):
    """Protocol for compartment topology."""

    @property
    def num_compartments(self) -> int:
        """Total number of compartments."""
        ...

    def parent(self, child: int) -> Optional[int]:
        """Get parent of a compartment (None for root)."""
        ...

    def children(self, parent: int) -> List[int]:
        """Get children of a compartment."""
        ...

    def root(self) -> int:
        """Get the root compartment."""
        ...

    def is_root(self, compartment: int) -> bool:
        """Check if compartment is the root."""
        ...
```

## See Also
- [[WorldState]] - Concentration storage
- [[Flow]] - Transport across membranes
- [[WorldSimulator]] - Uses tree for flow calculations
- [[Compartment]] - Entity-based compartments
