# Flow
**Subsystem**: [[ABIO biology]] > Transport
Transport between compartments via membrane or lateral flows.

## Overview
Flows move molecules (or instances) between compartments. They complement Reactions, which transform molecules within a compartment. The Flow hierarchy includes MembraneFlow (across parent-child membrane) and LateralFlow (between siblings).

| Property | Type | Description |
|----------|------|-------------|
| `origin` | CompartmentId | Origin compartment (where flow is anchored) |
| `name` | str | Human-readable name |
| `is_membrane_flow` | bool | True if origin ↔ parent |
| `is_lateral_flow` | bool | True if origin ↔ sibling |
| `is_instance_transfer` | bool | True if transferring multiplicity |

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
└── LateralFlow - transport between sibling compartments
```

| Operation | Scope | Example |
|-----------|-------|---------|
| **Reaction** | Within compartment | A + B → C |
| **MembraneFlow** | Across membrane | 2 Na⁺ + glucose cotransport |
| **LateralFlow** | Between siblings | RBCs: arteries ↔ veins |

### MembraneFlow
Transport across parent-child membrane with stoichiometry. Like reactions, membrane flows can move multiple molecules together per event.

| Property | Type | Description |
|----------|------|-------------|
| `stoichiometry` | Dict[str, float] | Molecules and counts per event |
| `rate_constant` | float | Base rate of events per unit time |

Direction convention:
- **Positive** stoichiometry = molecules move **INTO** origin (from parent)
- **Negative** stoichiometry = molecules move **OUT OF** origin (into parent)

### LateralFlow
Transport between sibling compartments (molecules or instances).

| Property | Type | Description |
|----------|------|-------------|
| `target` | CompartmentId | Target compartment (sibling of origin) |
| `molecule` | MoleculeId | Molecule transported (MULTIPLICITY_ID for instances) |
| `rate_constant` | float | Base permeability/transport rate |

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

### LateralFlow Examples

**Instance Transfer:**
```python
from alienbio import LateralFlow, MULTIPLICITY_ID

rbc_flow = LateralFlow(
    origin=arterial_rbc_id,
    target=venous_rbc_id,
    molecule=MULTIPLICITY_ID,
    rate_constant=0.01,
    name="rbc_circulation",
)
```

**Molecule Diffusion Between Siblings:**
```python
gap_junction = LateralFlow(
    origin=cell1_id,
    target=cell2_id,
    molecule=calcium_id,
    rate_constant=0.1,
    name="gap_junction_ca",
)
```

### Volume and Concentration Changes
Flows compute molecule counts, then convert to concentration changes using volumes.

**Membrane Flows:** Volume asymmetry causes different ΔC on each side:
```
PARENT (volume = 1000)      CHILD (volume = 1)
ΔC = -100/1000 = -0.1       ΔC = +100/1 = +100
```

**Lateral Flows (Instances):** Both use parent's volume:
```
ΔC_source = -instances / parent_volume
ΔC_dest   = +instances / parent_volume
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

# LateralFlow
type: lateral
name: rbc_circulation
origin: 1
target: 2
molecule: -1  # MULTIPLICITY_ID
rate_constant: 0.01
```

Note: Custom rate functions (`rate_fn`) cannot be serialized.

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
    def is_lateral_flow(self) -> bool:
        """True if this is a lateral flow (origin ↔ sibling)."""
        ...

    @property
    def is_instance_transfer(self) -> bool:
        """True if this transfers instances rather than molecules."""
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
