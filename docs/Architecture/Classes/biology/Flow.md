 [[Architecture Docs]] → [[ABIO biology]]

# Flow

Transport between compartments via membrane or general flows.

## Overview
Flows move molecules (or instances) between compartments. They complement Reactions, which transform molecules within a compartment. The Flow hierarchy includes MembraneFlow (well-defined stoichiometry) and GeneralFlow (arbitrary edits, placeholder).

| Property | Type | Description |
|----------|------|-------------|
| `origin` | CompartmentId | Origin compartment (where flow is anchored) |
| `name` | str | Human-readable name |
| `is_membrane_flow` | bool | True if origin ↔ parent |
| `is_general_flow` | bool | True if arbitrary edits |

| Method | Returns | Description |
|--------|---------|-------------|
| `compute_flux(state, tree)` | float | Compute flux |
| `apply(state, tree, dt)` | None | Apply flow to state |
| `attributes()` | Dict | Semantic content for serialization |

## Discussion

### Class Hierarchy
```
Flow (abstract base)
├── MembraneFlow - transport across parent-child membrane with stoichiometry
└── GeneralFlow - arbitrary state modifications (placeholder)
```

| Operation | Scope | Example |
|-----------|-------|---------|
| **Reaction** | Within compartment | A + B → C |
| **MembraneFlow** | Across membrane | 2 Na⁺ + glucose cotransport |
| **GeneralFlow** | Arbitrary | Lateral flows, instance transfers, etc. |

### MembraneFlow
Transport across parent-child membrane with stoichiometry. Like reactions, membrane flows can move multiple molecules together per event.

| Property | Type | Description |
|----------|------|-------------|
| `stoichiometry` | Dict[str, float] | Molecules and counts per event |
| `rate_constant` | float | Base rate of events per unit time |

Direction convention:
- **Positive** stoichiometry = molecules move **INTO** origin (from parent)
- **Negative** stoichiometry = molecules move **OUT OF** origin (into parent)

### GeneralFlow (Placeholder)
Catch-all for flows that don't fit the MembraneFlow pattern. This includes:
- Lateral flows between siblings
- Instance transfers (RBCs moving between compartments)
- Any other arbitrary edits to the system

**NOTE:** This is currently a placeholder. Full implementation will require a more general interpreter to handle arbitrary state modifications specified via Expr.

| Property | Type | Description |
|----------|------|-------------|
| `description` | str | Description of what this flow does |
| `apply_fn` | Callable | Function that modifies state (not serializable) |

### MembraneFlow Examples

**Simple Diffusion:**
```python
from alienbio import MembraneFlow

glucose_diffusion = MembraneFlow(
    origin=cell_id,
    stoichiometry={"glucose": 1},
    rate_constant=0.1,
    name="glucose_diffusion",
)
```

**Cotransporter (Multiple Molecules):**
```python
# Sodium-glucose cotransporter (SGLT1)
sglt1 = MembraneFlow(
    origin=cell_id,
    stoichiometry={"sodium": 2, "glucose": 1},
    rate_constant=10.0,
    name="sglt1",
)
```

**Pump (Opposite Directions):**
```python
# Sodium-potassium pump (Na+/K+-ATPase)
na_k_pump = MembraneFlow(
    origin=cell_id,
    stoichiometry={
        "sodium": -3,     # out of cell
        "potassium": 2,   # into cell
        "atp": -1,        # consumed inside
        "adp": 1,         # produced inside
    },
    rate_constant=5.0,
    name="na_k_atpase",
)
```

### GeneralFlow Example (Placeholder)
```python
from alienbio import GeneralFlow

# Arbitrary edit - needs more general interpreter for full support
def custom_transfer(state, tree, dt):
    # Custom logic here
    pass

flow = GeneralFlow(
    origin=cell_id,
    apply_fn=custom_transfer,
    name="custom_flow",
    description="Custom transfer logic",
)
```

### Volume and Concentration Changes
Membrane flows compute molecule counts, then convert to concentration changes using volumes.

Volume asymmetry causes different ΔC on each side:
```
PARENT (volume = 1000)      CHILD (volume = 1)
ΔC = -100/1000 = -0.1       ΔC = +100/1 = +100
```

### Membrane Model
```
         PARENT
           │
    ┌──────┴──────┐
    │   membrane  │  ← MembraneFlow anchored to child (origin)
    └──────┬──────┘
           │
         CHILD (origin)
```

Each child compartment "owns" its membrane.

### Serialization
```yaml
# MembraneFlow
type: membrane
name: sglt1
origin: 1
stoichiometry:
  sodium: 2
  glucose: 1
rate_constant: 10.0

# GeneralFlow (limited - apply_fn not serializable)
type: general
name: custom_flow
origin: 1
description: Custom transfer logic
```

Note: Custom rate/apply functions cannot be serialized. Full GeneralFlow support will need Expr-based specifications.

## Protocol
```python
from typing import Protocol, Dict, Any, runtime_checkable

@runtime_checkable
class Flow(Protocol):
    """Protocol for transport between compartments."""

    @property
    def origin(self) -> int:
        """The origin compartment (where this flow is anchored)."""
        ...

    @property
    def name(self) -> str:
        """Human-readable name."""
        ...

    @property
    def is_membrane_flow(self) -> bool:
        """True if this is a membrane flow (origin ↔ parent)."""
        ...

    @property
    def is_general_flow(self) -> bool:
        """True if this is a general flow (arbitrary edits)."""
        ...

    def compute_flux(self, state: WorldState, tree: CompartmentTree) -> float:
        """Compute flux for this flow."""
        ...

    def apply(self, state: WorldState, tree: CompartmentTree, dt: float) -> None:
        """Apply this flow to the state (mutates in place)."""
        ...

    def attributes(self) -> Dict[str, Any]:
        """Semantic content for serialization."""
        ...
```

## See Also
- [[Compartment]] - Membrane flows defined per compartment
- [[Reaction]] - Transformations within compartments
- [[CompartmentTree]] - Topology for simulation
- [[WorldState]] - Concentration and multiplicity storage
- [[WorldSimulator]] - Applies flows during simulation
- [[Interpreter]] - Will be needed for GeneralFlow Expr support
