# Flow
**Subsystem**: [[ABIO biology]] > Biology

Transport between compartments.

## Purpose

Flows move molecules (or instances) between compartments. They complement Reactions, which transform molecules within a compartment.

| Operation | Scope | Example |
|-----------|-------|---------|
| **Reaction** | Within compartment | A + B → C |
| **MembraneFlow** | Across membrane | 2 Na⁺ + glucose cotransport |
| **LateralFlow** | Between siblings | RBCs: arteries ↔ veins |

## Class Hierarchy

```
Flow (abstract base)
├── MembraneFlow - transport across parent-child membrane with stoichiometry
└── LateralFlow - transport between sibling compartments
```

### Flow (Base)

Common interface for all flows:

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

## MembraneFlow Examples

### Simple Diffusion

```python
from alienbio import MembraneFlow

# Glucose diffusion into cell
glucose_diffusion = MembraneFlow(
    origin=cell_id,
    stoichiometry={"glucose": 1},  # 1 glucose moves in per event
    rate_constant=0.1,
    name="glucose_diffusion",
)
```

### Cotransporter (Multiple Molecules)

```python
# Sodium-glucose cotransporter (SGLT1)
# Moves 2 Na+ and 1 glucose into the cell together
sglt1 = MembraneFlow(
    origin=cell_id,
    stoichiometry={"sodium": 2, "glucose": 1},
    rate_constant=10.0,
    name="sglt1",
)
```

### Pump (Opposite Directions)

```python
# Sodium-potassium pump (Na+/K+-ATPase)
# Pumps 3 Na+ out, 2 K+ in per ATP hydrolyzed
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

## LateralFlow Examples

### Instance Transfer

```python
from alienbio import LateralFlow, MULTIPLICITY_ID

# RBC transfer from arteries to veins
rbc_flow = LateralFlow(
    origin=arterial_rbc_id,
    target=venous_rbc_id,
    molecule=MULTIPLICITY_ID,  # transfer instances
    rate_constant=0.01,
    name="rbc_circulation",
)
```

### Molecule Diffusion Between Siblings

```python
# Calcium diffusion through gap junction between adjacent cells
gap_junction = LateralFlow(
    origin=cell1_id,
    target=cell2_id,
    molecule=calcium_id,
    rate_constant=0.1,
    name="gap_junction_ca",
)
```

## Custom Rate Functions

For non-linear kinetics (pumps, channels, etc.):

```python
def michaelis_menten_rate(state, origin, parent):
    # Get substrate concentration
    substrate = state.get(parent, glucose_id)
    vmax, km = 10.0, 5.0
    return vmax * substrate / (km + substrate)

flow = MembraneFlow(
    origin=cell_id,
    stoichiometry={"glucose": 1},
    rate_fn=michaelis_menten_rate,
    name="glut_transporter",
)
```

## Membrane Model

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

## Volume and Concentration Changes

Flows compute **molecule counts** (or instance counts), then the framework converts to concentration changes using volumes.

### Membrane Flows (Molecules)

When N molecules flow across a membrane, the concentration change differs on each side:

```
PARENT (volume = 1000)      CHILD (volume = 1)
    │                           │
    │  ─── 100 molecules ───►   │
    │                           │
ΔC = -100/1000 = -0.1      ΔC = +100/1 = +100
```

The same molecule transfer causes dramatically different concentration changes due to volume asymmetry. A small cell taking molecules from a large extracellular space barely affects outside concentration but significantly changes inside.

Formula:
```
ΔC_source = -molecules / source_volume
ΔC_dest   = +molecules / dest_volume
```

### Lateral Flows (Instances)

When instances transfer between siblings (using `MULTIPLICITY_ID`), both compartments exist within the same parent, so the parent's volume determines concentration:

```
PARENT (volume = 1000 mL)
├── oxygenated_rbc (mult = 2e9)      → conc = 2e6/mL
└── deoxygenated_rbc (mult = 0.5e9)  → conc = 0.5e6/mL
```

Formula:
```
ΔC_source = -instances / parent_volume
ΔC_dest   = +instances / parent_volume
```

Same parent volume on both sides since siblings share a container.

### Lateral Flows (Molecules)

When molecules flow between siblings (not instances), the source and destination have their own volumes:

```
ΔC_source = -molecules / source_volume
ΔC_dest   = +molecules / dest_volume
```

## Serialization

### MembraneFlow

```yaml
type: membrane
name: sglt1
origin: 1
stoichiometry:
  sodium: 2
  glucose: 1
rate_constant: 10.0
```

### LateralFlow

```yaml
type: lateral
name: rbc_circulation
origin: 1
target: 2
molecule: -1  # MULTIPLICITY_ID
rate_constant: 0.01
```

Note: Custom rate functions (`rate_fn`) cannot be serialized.

## See Also

- [[Compartment]] - Membrane flows defined per compartment
- [[Reaction]] - Transformations within compartments
- [[CompartmentTree]] - Topology for simulation
- [[WorldState]] - Concentration and multiplicity storage
- [[WorldSimulator]] - Applies flows during simulation
