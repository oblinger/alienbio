# Compartment
**Subsystem**: [[ABIO biology]] > Biology

Entity representing a biological compartment in the hierarchy.

## Purpose

Compartment is an Entity that defines a region in the biological hierarchy (organism, organ, cell, organelle). It serves as both:
- **Initial state specification**: multiplicity, concentrations
- **Behavior specification**: membrane flows, active reactions

The entity tree of Compartments is the complete simulation specification.

## Design

| Property | Type | Description |
|----------|------|-------------|
| `kind` | str | Type: "organism", "organ", "cell", "organelle" |
| `multiplicity` | float | Number of instances (default 1.0) |
| `volume` | float | Volume of each instance (required - no default) |
| `concentrations` | Dict[str, float] | Initial molecule concentrations |
| `membrane_flows` | List[Flow] | Flows across this membrane |
| `active_reactions` | Optional[List[str]] | Active reaction names (None = all) |
| `children` | List[Compartment] | Child compartments |

| Method | Returns | Description |
|--------|---------|-------------|
| `add_child(child)` | None | Add a child compartment |
| `add_flow(flow)` | None | Add a membrane flow |
| `all_descendants()` | List[Compartment] | All descendant compartments |
| `all_compartments()` | List[Compartment] | Self and all descendants |
| `depth()` | int | Depth in tree (root = 0) |

## Usage

```python
from alienbio import CompartmentImpl, FlowImpl

# Define an organism with organs and cells
organism = CompartmentImpl(
    "body",
    volume=70000,  # 70 liters in mL
    kind="organism",
    concentrations={"glucose": 5.0, "oxygen": 2.0},
)

liver = CompartmentImpl(
    "liver",
    volume=1500,  # 1.5 liters in mL
    parent=organism,
    kind="organ",
)

hepatocyte = CompartmentImpl(
    "hepatocyte",
    volume=3e-9,  # ~3000 cubic microns in mL
    parent=liver,
    kind="cell",
    multiplicity=1e9,  # 1 billion liver cells
    concentrations={"glucose": 1.0},
    active_reactions=["glycolysis", "gluconeogenesis"],
)
```

## Multiplicity

Multiplicity represents how many instances of a compartment exist:

```python
# 1 billion red blood cells in arteries
arterial_rbc = CompartmentImpl(
    "arterial_rbc",
    parent=arteries,
    kind="cell",
    multiplicity=1e9,
)
```

Concentrations are per-instance. Total molecules = multiplicity × concentration.

Nested multiplicities are conceptually multiplicative:
- Liver has 1e9 hepatocytes
- Each hepatocyte has 500 mitochondria
- Total mitochondria = 1e9 × 500 = 5e11

## Volume

Volume specifies the size of each compartment instance. It is **required** (no default) because the appropriate scale varies widely:
- Macroscopic systems (organs, blood vessels): might use mL or L
- Cellular systems: might use femtoliters (10⁻¹⁵ L)
- Abstract simulations: might use arbitrary units like 10,000 for percentage-like concentrations

### Two Concentration Concepts

Volume participates in two different concentration calculations:

**1. Molecular concentration within a compartment**
```
concentration = molecules / compartment_volume
```
Used by reactions. Example: glucose concentration inside a hepatocyte.

**2. Instance concentration of children within parent**
```
child_concentration = child_multiplicity / parent_volume
```
Used by lateral flows between siblings. Example: concentration of oxygenated RBCs in arterial blood.

```
ARTERIES (volume = 1000 mL)
├── oxygenated_rbc (multiplicity = 2e9)    → concentration = 2e6/mL
└── deoxygenated_rbc (multiplicity = 0.5e9) → concentration = 0.5e6/mL
```

### Membrane Flow Calculations

When molecules flow across a membrane, the same molecule count causes different concentration changes on each side due to volume asymmetry:

```
PARENT (volume = 1000)
│
├── membrane ← 100 molecules flow from parent to child
│
└── CHILD (volume = 1)
```

```
ΔC_parent = -100 / 1000 = -0.1
ΔC_child  = +100 / 1    = +100
```

This asymmetry is fundamental: a small cell taking up molecules from a large extracellular space barely affects outside concentration but dramatically changes inside concentration.

### Lateral Flow Calculations

When instances transfer between siblings, both use the parent's volume:

```
ΔC_source = -instances / parent_volume
ΔC_dest   = +instances / parent_volume
```

Same parent volume on both sides since siblings share a container.

### Usage

```python
# Explicit volume is required
hepatocyte = CompartmentImpl(
    "hepatocyte",
    parent=liver,
    kind="cell",
    volume=1e-12,  # femtoliters
    concentrations={"glucose": 1.0},
)
```

## Membrane Flows

Each compartment owns its membrane. Flows across the membrane are listed in `membrane_flows`:

```python
hepatocyte = CompartmentImpl(
    "hepatocyte",
    parent=liver,
    kind="cell",
    membrane_flows=[
        FlowImpl(origin=0, molecule=glucose_id, rate_constant=0.1),
        FlowImpl(origin=0, molecule=oxygen_id, rate_constant=0.5),
    ],
)
```

## Active Reactions

By default, all reactions from Chemistry are active in all compartments. To restrict:

```python
# Only glycolysis and gluconeogenesis in hepatocytes
hepatocyte = CompartmentImpl(
    "hepatocyte",
    parent=liver,
    kind="cell",
    active_reactions=["glycolysis", "gluconeogenesis"],
)

# All reactions active (default)
generic_cell = CompartmentImpl(
    "cell",
    parent=organ,
    kind="cell",
    active_reactions=None,  # all from chemistry
)
```

## Container Kinds

The `kind` field is a semantic label:
- **organism** - Top-level biological entity
- **organ** - Functional unit within organism
- **cell** - Individual cellular unit
- **organelle** - Sub-cellular compartment (mitochondria, nucleus, etc.)
- **compartment** - Generic sub-region

## Entity Tree → Simulation

The Compartment entity tree compiles to simulation structures:

```
CompartmentImpl tree  ──compile──►  WorldSimulator
                                      ├── CompartmentTree (efficient topology)
                                      ├── WorldState (concentrations + multiplicities)
                                      ├── ReactionSpecs (per compartment)
                                      └── FlowSpecs (from membrane_flows)
```

## See Also

- [[CompartmentTree]] - Efficient topology for simulation
- [[WorldState]] - Concentration storage (includes multiplicities)
- [[Flow]] - Membrane and lateral transport
- [[Chemistry]] - Reactions and molecules
- [[WorldSimulator]] - Multi-compartment simulation
