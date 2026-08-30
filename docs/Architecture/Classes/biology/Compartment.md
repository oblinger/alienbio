 [[Architecture Docs]] → [[ABIO biology]]

# Compartment

Entity representing a biological compartment in the hierarchy.

## Overview
Compartment is an Entity that defines a region in the biological hierarchy (organism, organ, cell, organelle). It serves as both initial state specification (multiplicity, concentrations) and behavior specification (membrane flows, active reactions). The entity tree of Compartments is the complete simulation specification.

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

## Discussion

### Usage Example
```python
from alienbio import CompartmentImpl, GeneralFlow

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

### Multiplicity
Multiplicity represents how many instances of a compartment exist. Concentrations are per-instance. Total molecules = multiplicity × concentration.

```python
# 1 billion red blood cells in arteries
arterial_rbc = CompartmentImpl(
    "arterial_rbc",
    parent=arteries,
    kind="cell",
    multiplicity=1e9,
)
```

Nested multiplicities are conceptually multiplicative:
- Liver has 1e9 hepatocytes
- Each hepatocyte has 500 mitochondria
- Total mitochondria = 1e9 × 500 = 5e11

### Volume
Volume specifies the size of each compartment instance. It is **required** (no default) because the appropriate scale varies widely:
- Macroscopic systems (organs): mL or L
- Cellular systems: femtoliters (10⁻¹⁵ L)
- Abstract simulations: arbitrary units

### Two Concentration Concepts

**1. Molecular concentration within a compartment**
```
concentration = molecules / compartment_volume
```
Used by reactions. Example: glucose concentration inside a hepatocyte.

**2. Instance concentration of children within parent**
```
child_concentration = child_multiplicity / parent_volume
```
Used by lateral flows. Example: concentration of oxygenated RBCs in arterial blood.

### Membrane Flow Calculations
When molecules flow across a membrane, volume asymmetry causes different concentration changes:

```
PARENT (volume = 1000)      CHILD (volume = 1)
ΔC = -100/1000 = -0.1       ΔC = +100/1 = +100
```

This asymmetry is fundamental: a small cell taking up molecules from a large extracellular space barely affects outside concentration but dramatically changes inside concentration.

### Container Kinds
The `kind` field is a semantic label:
- **organism** - Top-level biological entity
- **organ** - Functional unit within organism
- **cell** - Individual cellular unit
- **organelle** - Sub-cellular compartment
- **compartment** - Generic sub-region

### Entity Tree → Simulation
The Compartment entity tree compiles to simulation structures:

```
CompartmentImpl tree  ──compile──►  WorldSimulator
                                      ├── CompartmentTree
                                      ├── WorldState
                                      ├── ReactionSpecs
                                      └── FlowSpecs
```

## Protocol
```python
from typing import Protocol, Dict, List, Optional, runtime_checkable

@runtime_checkable
class Compartment(Protocol):
    """Protocol for compartment entities."""

    @property
    def kind(self) -> str:
        """Compartment type: organism, organ, cell, organelle."""
        ...

    @property
    def volume(self) -> float:
        """Volume of each instance."""
        ...

    @property
    def multiplicity(self) -> float:
        """Number of instances."""
        ...

    @property
    def concentrations(self) -> Dict[str, float]:
        """Initial molecule concentrations."""
        ...

    @property
    def membrane_flows(self) -> List[Flow]:
        """Flows across this membrane."""
        ...

    @property
    def active_reactions(self) -> Optional[List[str]]:
        """Active reaction names (None = all)."""
        ...
```

## See Also
- [[CompartmentTree]] - Efficient topology for simulation
- [[WorldState]] - Concentration storage
- [[Flow]] - Membrane and lateral transport
- [[Chemistry]] - Reactions and molecules
- [[WorldSimulator]] - Multi-compartment simulation
