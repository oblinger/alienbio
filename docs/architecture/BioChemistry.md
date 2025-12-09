# BioChemistry
**Parent**: [[ABIO biology]]

Container entity for a set of molecules and their reactions.

## Purpose

BioChemistry provides a namespace for grouping related molecules and reactions together. It acts as the "world" for a chemical system, enabling:
- Organization of molecules and reactions into logical units
- Validation that reactions reference valid molecules
- State management (concentrations) for simulation

## Relationship to Other Containers

| Container | Scope | Use Case |
|-----------|-------|----------|
| **BioChemistry** | Molecules + reactions | A chemical system (e.g., glycolysis) |
| **BioContainer** | Nested structures | Organisms, organs, cells, organelles |

BioChemistry is simpler than BioContainer - it doesn't handle nesting or kind labels. Use BioChemistry when you need a flat collection of molecules and reactions; use BioContainer for hierarchical biological structures.

## Class Definition

```python
class BioChemistry(Entity, type_name="BioChemistry"):
    """Container for a set of molecules and their reactions."""
```

## Key Properties

| Property | Type | Description |
|----------|------|-------------|
| `molecules` | `Dict[str, BioMolecule]` | All molecule children by name |
| `reactions` | `Dict[str, BioReaction]` | All reaction children by name |

## Key Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `iter_molecules()` | `Iterator[BioMolecule]` | Iterate over molecules |
| `iter_reactions()` | `Iterator[BioReaction]` | Iterate over reactions |
| `get_molecule(name)` | `BioMolecule | None` | Get molecule by name |
| `get_reaction(name)` | `BioReaction | None` | Get reaction by name |
| `validate()` | `List[str]` | Check consistency, return errors |

## Usage Example

```python
from alienbio import BioChemistry, BioMolecule, BioReaction, State, SimpleSimulator

# Create chemistry with DAT anchor
dat = Dat.create(path="chemistry/glycolysis")
chem = BioChemistry("glycolysis", dat=dat, description="Sugar breakdown")

# Add molecules (as children)
glucose = BioMolecule("glucose", parent=chem, properties={"mw": 180.16})
pyruvate = BioMolecule("pyruvate", parent=chem)
atp = BioMolecule("atp", parent=chem)

# Add reaction
BioReaction(
    "glycolysis_step",
    reactants={glucose: 1},
    products={pyruvate: 2, atp: 2},
    rate=0.1,
    parent=chem,
)

# Validate
errors = chem.validate()  # Returns [] if valid

# Create state and simulate
state = State(chem, initial={"glucose": 10.0})
sim = SimpleSimulator(chem, dt=1.0)
timeline = sim.run(state, steps=100)
```

## Validation

The `validate()` method checks:
- All reaction reactants are molecules in this chemistry
- All reaction products are molecules in this chemistry

Returns a list of error messages (empty if valid).

## Serialization

BioChemistry serializes with type information and child counts:

```yaml
type: BioChemistry
name: glycolysis
description: Sugar breakdown
molecule_count: 3
reaction_count: 1
children:
  glucose:
    type: Molecule
    name: glucose
    properties:
      mw: 180.16
  # ... other children
```

## See Also

- [[BioMolecule]] - Molecules in the chemistry
- [[BioReaction]] - Reactions between molecules
- [[State]] - Molecule concentrations
- [[Simulator]] - Step-based simulation
- [[BioContainer]] - Hierarchical biological structures
