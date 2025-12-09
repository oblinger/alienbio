# WorldState
**Subsystem**: [[ABIO biology]] > Simulation

Concentration and multiplicity storage for multi-compartment simulations.

## Purpose

WorldState provides efficient storage for molecule concentrations and instance multiplicities across all compartments. Each WorldState holds a reference to its CompartmentTree, enabling self-contained historical snapshots.

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

## Design

WorldState uses **dense storage** for efficiency:

- Concentrations: Flat array `[num_compartments × num_molecules]`
- Multiplicities: Array `[num_compartments]`
- Row-major indexing: `concentrations[compartment * num_molecules + molecule]`
- GPU-friendly: regular memory access patterns, no indirection

For very large molecule vocabularies, can be extended with sparse overflow per compartment.

## Multiplicity

Each compartment has a multiplicity representing how many instances exist:

```python
# 1 million red blood cells in arteries
state.set_multiplicity(arterial_rbc, 1e6)

# Per-instance concentration
state.set(arterial_rbc, oxygen_id, 4.0)

# Total oxygen = 1e6 * 4.0 = 4e6
total = state.total_molecules(arterial_rbc, oxygen_id)
```

Multiplicity defaults to 1.0 for all compartments. Flows can transfer instances (using `MULTIPLICITY_ID`) as well as molecules.

## Usage

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
assert snapshot.tree is state.tree  # Same tree object
```

## Tree Sharing

Multiple WorldStates can share the same tree reference (immutable sharing):

```python
# Run simulation
history = sim.run(state, steps=1000)

# All states in history share the same tree
assert history[0].tree is history[-1].tree
```

When topology changes (e.g., cell division), create a new tree:

```python
# Original tree: organism -> cell
original_tree = state.tree

# Cell divides - create new tree
new_tree = CompartmentTreeImpl()
org = new_tree.add_root("organism")
cell1 = new_tree.add_child(org, "cell_1")
cell2 = new_tree.add_child(org, "cell_2")  # new cell

# New state uses new tree
new_state = WorldStateImpl(tree=new_tree, num_molecules=50)
# Copy concentrations from old state, distribute to daughter cells...

# Historical states still reference original_tree
# Current states reference new_tree
```

## Storage Layout

```
Compartment 0: [mol0, mol1, mol2, ..., molN]
Compartment 1: [mol0, mol1, mol2, ..., molN]
...
Compartment M: [mol0, mol1, mol2, ..., molN]
```

This layout enables:
- O(1) access to any concentration
- Efficient iteration over all molecules in a compartment
- SIMD-friendly operations on compartment slices
- Zero-copy NumPy array views

## Future: Sparse Overflow

For simulations with thousands of molecules where most compartments have sparse subsets:

```
WorldState:
  dense_core: [compartments × common_molecules]  # always present
  sparse_overflow: Dict[CompartmentId, Dict[MoleculeId, float]]  # rare molecules
```

Lookup: check dense first, fall back to sparse.

## See Also

- [[CompartmentTree]] - Compartment topology
- [[Flow]] - Transport between compartments
- [[WorldSimulator]] - Multi-compartment simulation
- [[State]] - Legacy single-compartment state
