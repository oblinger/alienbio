# WorldSimulator
**Subsystem**: [[ABIO biology]] > Simulation

Multi-compartment simulation with reactions and flows.

## Purpose

WorldSimulator advances the state of a multi-compartment world over time. Each simulation step:
1. Applies reactions within each compartment
2. Applies flows across compartment membranes

## Design

| Property | Type | Description |
|----------|------|-------------|
| `tree` | CompartmentTree | Compartment topology |
| `reactions` | List[ReactionSpec] | Reaction specifications |
| `flows` | List[Flow] | Membrane transport specs |
| `num_molecules` | int | Molecule vocabulary size |
| `dt` | float | Time step size |

| Method | Returns | Description |
|--------|---------|-------------|
| `step(state)` | WorldState | Advance one time step |
| `run(state, steps, sample_every)` | List[WorldState] | Run simulation |
| `from_chemistry(chem, tree, flows, dt)` | WorldSimulator | Build from Chemistry |

## Usage

```python
from alienbio import (
    WorldSimulatorImpl, WorldStateImpl, CompartmentTreeImpl,
    FlowImpl, ReactionSpec
)

# Build compartment tree
tree = CompartmentTreeImpl()
organism = tree.add_root("organism")
cell = tree.add_child(organism, "cell")

# Define reactions (molecule IDs: 0=glucose, 1=pyruvate)
reactions = [
    ReactionSpec(
        name="glycolysis",
        reactants={0: 1},      # 1 glucose
        products={1: 2},       # 2 pyruvate
        rate_constant=0.1,
        compartments=None,     # all compartments
    ),
]

# Define flows
flows = [
    FlowImpl(child=cell, molecule=0, rate_constant=0.05),  # glucose uptake
]

# Create simulator
sim = WorldSimulatorImpl(
    tree=tree,
    reactions=reactions,
    flows=flows,
    num_molecules=10,
    dt=0.1,
)

# Initialize state (references the tree)
state = WorldStateImpl(tree=tree, num_molecules=10)
state.set(organism, 0, 100.0)  # glucose in organism

# Run simulation
history = sim.run(state, steps=1000, sample_every=100)

# history contains 11 snapshots: [0, 100, 200, ..., 1000]
# All states share the same tree reference (efficient)
assert history[0].tree is history[-1].tree
```

## ReactionSpec

Lightweight reaction specification using molecule IDs:

```python
ReactionSpec(
    name="r1",
    reactants={0: 2, 1: 1},   # 2A + B
    products={2: 1},          # C
    rate_constant=0.5,
    compartments=[1, 2],      # only in these compartments (None = all)
)
```

## Building from Chemistry

```python
from alienbio import ChemistryImpl

# Create chemistry with molecules and reactions
chem = ChemistryImpl(
    "glycolysis",
    molecules={"glucose": glucose, "pyruvate": pyruvate},
    reactions={"step1": reaction},
    dat=dat,
)

# Build simulator
sim = WorldSimulatorImpl.from_chemistry(
    chemistry=chem,
    tree=tree,
    flows=flows,
    dt=0.1,
)
```

## Simulation Loop

Each `step()`:

```
1. For each reaction:
   - For each applicable compartment:
     - Compute rate = k * ∏(concentration^stoich)
     - Consume reactants
     - Produce products

2. For each flow:
   - Compute flux = rate * (parent_conc - child_conc)
   - Transfer molecules between parent and child
```

## Tree Sharing in History

Each WorldState holds a reference to its CompartmentTree. All states in a simulation history share the same tree reference (no copying):

```python
history = sim.run(state, steps=1000, sample_every=100)

# All 11 snapshots reference the same tree object
for s in history:
    assert s.tree is state.tree
```

When topology changes (e.g., cell division), create a new tree and new states will reference it while historical states keep their original tree.

## History Sampling

For long simulations, sample every Nth step to save memory:

```python
# Full history (all 1001 states)
history = sim.run(state, steps=1000)

# Sampled history (11 states: 0, 100, 200, ..., 1000)
history = sim.run(state, steps=1000, sample_every=100)

# Current state only (just run, don't store)
for _ in range(1000):
    state = sim.step(state)
```

## GPU Considerations

The Python implementation is designed for clarity. For high-performance simulations:

1. **Rust implementation** with PyO3 bindings
2. **Batched operations** for SIMD
3. **GPU kernels** for massive parallelism

The dense WorldState layout is GPU-friendly: regular memory access patterns, no pointer chasing.

## See Also

- [[WorldState]] - Concentration storage
- [[CompartmentTree]] - Compartment topology
- [[Flow]] - Membrane transport
- [[Reaction]] - Chemical transformations
- [[Simulator]] - Legacy single-compartment simulator
