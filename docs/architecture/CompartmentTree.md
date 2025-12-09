# CompartmentTree
**Subsystem**: [[ABIO biology]] > Simulation

Hierarchical topology of compartments.

## Purpose

CompartmentTree represents the nested structure of biological compartments:
- Organism > Organ > Cell > Organelle
- Stored separately from concentrations for efficient updates
- Provides parent/child relationships for flow calculations

## Design

The tree uses integer IDs for compartments (0, 1, 2, ...) and stores:

| Attribute | Type | Description |
|-----------|------|-------------|
| `parents` | List[Optional[int]] | `parent[child]` = parent_id or None for root |
| `children` | Dict[int, List[int]] | `children[parent]` = list of child IDs |
| `names` | List[str] | Human-readable names |

| Property | Type | Description |
|----------|------|-------------|
| `num_compartments` | int | Total compartment count |

| Method | Returns | Description |
|--------|---------|-------------|
| `parent(child)` | Optional[int] | Get parent (None for root) |
| `children(parent)` | List[int] | Get children |
| `root()` | int | Get root compartment ID |
| `is_root(comp)` | bool | Check if root |
| `add_root(name)` | int | Add root, returns ID |
| `add_child(parent, name)` | int | Add child, returns ID |

## Usage

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

## Example Structure

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

## Tree Invariants

1. Exactly one root (parent = None)
2. All non-root compartments have exactly one parent
3. No cycles
4. IDs are contiguous: 0, 1, 2, ..., N-1

## Serialization

```yaml
parents: [null, 0, 0, 1, 1]  # null = root
names: ["organism", "heart", "liver", "cell_1", "cell_2"]
```

## Topology Changes

The tree structure changes rarely (e.g., cell division). When it does:
1. Add new compartments with `add_child()`
2. Expand WorldState to include new compartments
3. Initialize new compartment concentrations

## See Also

- [[WorldState]] - Concentration storage
- [[Flow]] - Transport across membranes
- [[WorldSimulator]] - Uses tree for flow calculations
- [[Compartment]] - Entity-based compartments (different abstraction)
