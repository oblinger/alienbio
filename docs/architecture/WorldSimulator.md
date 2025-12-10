# WorldSimulator
**Subsystem**: [[ABIO biology]] > Simulation
Multi-compartment simulation with reactions and flows.

## Overview
WorldSimulator advances the state of a multi-compartment world over time. Each simulation step applies reactions within compartments and flows across membranes. Supports history sampling for efficient memory usage.

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

## Discussion

### Usage Example
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
        reactants={0: 1},
        products={1: 2},
        rate_constant=0.1,
        compartments=None,  # all compartments
    ),
]

# Define flows
flows = [
    FlowImpl(child=cell, molecule=0, rate_constant=0.05),
]

# Create simulator
sim = WorldSimulatorImpl(
    tree=tree,
    reactions=reactions,
    flows=flows,
    num_molecules=10,
    dt=0.1,
)

# Initialize state and run
state = WorldStateImpl(tree=tree, num_molecules=10)
state.set(organism, 0, 100.0)
history = sim.run(state, steps=1000, sample_every=100)
```

### ReactionSpec
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

### Building from Chemistry
```python
sim = WorldSimulatorImpl.from_chemistry(
    chemistry=chem,
    tree=tree,
    flows=flows,
    dt=0.1,
)
```

### Simulation Loop
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

### History Sampling
For long simulations, sample every Nth step to save memory:

```python
# Full history (all 1001 states)
history = sim.run(state, steps=1000)

# Sampled history (11 states: 0, 100, 200, ..., 1000)
history = sim.run(state, steps=1000, sample_every=100)

# Current state only
for _ in range(1000):
    state = sim.step(state)
```

### Tree Sharing in History
All states in a simulation history share the same tree reference:

```python
for s in history:
    assert s.tree is state.tree
```

When topology changes (e.g., cell division), create a new tree.

### GPU Considerations
The Python implementation is designed for clarity. For high-performance:
- **Rust implementation** with PyO3 bindings
- **Batched operations** for SIMD
- **GPU kernels** for massive parallelism

The dense WorldState layout is GPU-friendly.

## Method Details

### `step(state: WorldState) -> WorldState`
Advance the simulation by one time step.

**Args:**
- `state`: Current world state

**Returns:** New state after applying reactions and flows

### `run(state: WorldState, steps: int, sample_every: Optional[int] = None) -> List[WorldState]`
Run simulation for multiple steps.

**Args:**
- `state`: Initial state
- `steps`: Number of steps to run
- `sample_every`: If set, only keep every Nth state in history

**Returns:** List of states (includes initial state)

## Protocol
```python
from typing import Protocol, List, Optional, runtime_checkable

@runtime_checkable
class Simulator(Protocol):
    """Protocol for simulators."""

    @property
    def chemistry(self) -> Chemistry:
        """The Chemistry being simulated."""
        ...

    @property
    def tree(self) -> CompartmentTree:
        """The compartment topology."""
        ...

    @property
    def dt(self) -> float:
        """Time step size."""
        ...

    def step(self, state: WorldState) -> WorldState:
        """Advance the simulation by one time step."""
        ...

    def run(
        self,
        state: WorldState,
        steps: int,
        sample_every: Optional[int] = None,
    ) -> List[WorldState]:
        """Run simulation for multiple steps."""
        ...
```

## See Also
- [[WorldState]] - Concentration storage
- [[CompartmentTree]] - Compartment topology
- [[Flow]] - Membrane transport
- [[Reaction]] - Chemical transformations
- [[Simulator]] - Legacy single-compartment simulator
