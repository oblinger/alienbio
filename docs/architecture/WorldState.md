# WorldState
**Subsystem**: [[ABIO biology]] > Simulation
Concentration and multiplicity storage for multi-compartment simulations.

## Overview
WorldState provides efficient storage for molecule concentrations and instance multiplicities across all compartments. Each WorldState holds a reference to its CompartmentTree, enabling self-contained historical snapshots with immutable tree sharing.

| Property | Type | Description |
|----------|------|-------------|
| `tree` | CompartmentTree | Compartment topology (shared reference) |
| `num_compartments` | int | Number of compartments (from tree) |
| `num_molecules` | int | Size of molecule vocabulary |

| Method | Returns | Description |
|--------|---------|-------------|
| `get(comp, mol)` | float | Get concentration |
| `set(comp, mol, val)` | None | Set concentration |
| `get_compartment(comp)` | List[float] | All concentrations for compartment |
| `get_multiplicity(comp)` | float | Get instance count for compartment |
| `set_multiplicity(comp, val)` | None | Set instance count |
| `total_molecules(comp, mol)` | float | Get multiplicity × concentration |
| `copy()` | WorldState | Copy concentrations/multiplicities, share tree |
| `as_array()` | 2D array | NumPy-compatible view |

## Discussion

### Storage Layout
WorldState uses **dense storage** for efficiency:

```
Compartment 0: [mol0, mol1, mol2, ..., molN]
Compartment 1: [mol0, mol1, mol2, ..., molN]
...
Compartment M: [mol0, mol1, mol2, ..., molN]
```

- Concentrations: Flat array `[num_compartments × num_molecules]`
- Multiplicities: Array `[num_compartments]`
- Row-major indexing: `concentrations[compartment * num_molecules + molecule]`
- GPU-friendly: regular memory access patterns, no indirection

### Usage Example
```python
from alienbio import WorldStateImpl, CompartmentTreeImpl

# Build compartment tree first
tree = CompartmentTreeImpl()
organism = tree.add_root("organism")
cell = tree.add_child(organism, "cell")

# Create state: requires tree, specifies molecule count
state = WorldStateImpl(tree=tree, num_molecules=50)

# Set initial concentrations
state.set(compartment=organism, molecule=5, value=100.0)

# Access as numpy array
arr = state.as_array()  # [2 x 50] array
arr[0, :] = initial_values

# Copy for history (shares tree reference)
snapshot = state.copy()
assert snapshot.tree is state.tree
```

### Multiplicity
Each compartment has a multiplicity representing how many instances exist:

```python
# 1 million red blood cells in arteries
state.set_multiplicity(arterial_rbc, 1e6)

# Per-instance concentration
state.set(arterial_rbc, oxygen_id, 4.0)

# Total oxygen = 1e6 * 4.0 = 4e6
total = state.total_molecules(arterial_rbc, oxygen_id)
```

Multiplicity defaults to 1.0. Flows can transfer instances (using `MULTIPLICITY_ID`) as well as molecules.

### Tree Sharing
Multiple WorldStates can share the same tree reference (immutable sharing):

```python
history = sim.run(state, steps=1000)
assert history[0].tree is history[-1].tree
```

When topology changes (e.g., cell division), create a new tree. Historical states keep their original tree reference.

### Future: Sparse Overflow
For simulations with thousands of molecules where most compartments have sparse subsets:

```
WorldState:
  dense_core: [compartments × common_molecules]
  sparse_overflow: Dict[CompartmentId, Dict[MoleculeId, float]]
```

## Protocol
```python
from typing import Protocol, List, Any, runtime_checkable

@runtime_checkable
class WorldState(Protocol):
    """Protocol for world concentration state."""

    @property
    def tree(self) -> CompartmentTree:
        """The compartment tree this state belongs to."""
        ...

    @property
    def num_compartments(self) -> int:
        """Number of compartments."""
        ...

    @property
    def num_molecules(self) -> int:
        """Number of molecules in vocabulary."""
        ...

    def get(self, compartment: int, molecule: int) -> float:
        """Get concentration of molecule in compartment."""
        ...

    def set(self, compartment: int, molecule: int, value: float) -> None:
        """Set concentration of molecule in compartment."""
        ...

    def get_multiplicity(self, compartment: int) -> float:
        """Get multiplicity (instance count) for a compartment."""
        ...

    def set_multiplicity(self, compartment: int, value: float) -> None:
        """Set multiplicity (instance count) for a compartment."""
        ...

    def copy(self) -> 'WorldState':
        """Create a copy of this state (shares tree reference)."""
        ...

    def as_array(self) -> Any:
        """Get concentrations as 2D array [compartments x molecules]."""
        ...
```

## See Also
- [[CompartmentTree]] - Compartment topology
- [[Flow]] - Transport between compartments
- [[WorldSimulator]] - Multi-compartment simulation
- [[State]] - Legacy single-compartment state
