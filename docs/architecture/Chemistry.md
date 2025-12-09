# Chemistry
**Subsystem**: [[ABIO biology]]

Container for atoms, molecules, and reactions forming a chemical system.

## Overview

Chemistry provides a container for grouping related chemical components together. It acts as the "world" for a chemical system, enabling:
- Organization of atoms, molecules, and reactions into logical units
- Validation that reactions reference valid molecules
- State management (concentrations) for simulation
- Support for alien chemistries with custom atoms

| Attribute | Type | Index By | Description |
|-----------|------|----------|-------------|
| `atoms` | `Dict[str, Atom]` | symbol | Chemical elements ("C", "H", "O") |
| `molecules` | `Dict[str, Molecule]` | name | Chemical compounds ("glucose", "atp") |
| `reactions` | `Dict[str, Reaction]` | name | Transformations ("step1", "atp_synth") |

| Method         | Returns          | Description                                          |
| -------------- | ---------------- | ---------------------------------------------------- |
| `validate()`   | `List[str]`      | Check that all reaction molecules exist in chemistry |
| `attributes()` | `Dict[str, Any]` | Semantic content for serialization                   |


Key design points:
- **Public attributes** - Direct dict access, no property wrappers
- **Constructor takes all three** - Built as a complete unit
- **Conceptually immutable** - Though technically mutable, treat as fixed after construction
- **No parent relationships** - Molecules/reactions stored in dicts, not as entity children
- **Still an Entity** - For serialization and DAT support


## Design

Chemistry is a simple data structure with **public dict attributes**:

## Class Definition

```python
class ChemistryImpl(Entity, head="Chemistry"):
    """Container for a chemical system."""

    atoms: Dict[str, AtomImpl]
    molecules: Dict[str, MoleculeImpl]
    reactions: Dict[str, ReactionImpl]

    def __init__(
        self,
        name: str,
        *,
        atoms: Optional[Dict[str, AtomImpl]] = None,
        molecules: Optional[Dict[str, MoleculeImpl]] = None,
        reactions: Optional[Dict[str, ReactionImpl]] = None,
        dat: Optional[Dat] = None,
        description: str = "",
    ) -> None: ...
```

## Key Methods

## Usage Example

```python
from alienbio import ChemistryImpl, MoleculeImpl, ReactionImpl, AtomImpl
from alienbio import StateImpl, SimpleSimulatorImpl, get_atom

# Create atoms (use common atoms or define custom)
C = get_atom("C")
H = get_atom("H")
O = get_atom("O")

# Create molecules (standalone, not children)
glucose = MoleculeImpl("glucose", dat=dat, atoms={C: 6, H: 12, O: 6})
pyruvate = MoleculeImpl("pyruvate", dat=dat)
atp = MoleculeImpl("atp", dat=dat)

# Create reaction
r1 = ReactionImpl(
    "glycolysis_step",
    reactants={glucose: 1},
    products={pyruvate: 2, atp: 2},
    rate=0.1,
    dat=dat,
)

# Build chemistry with all components
chem = ChemistryImpl(
    "glycolysis",
    atoms={"C": C, "H": H, "O": O},
    molecules={"glucose": glucose, "pyruvate": pyruvate, "atp": atp},
    reactions={"glycolysis_step": r1},
    dat=dat,
    description="Simplified glycolysis",
)

# Direct access to components
chem.atoms["C"]                    # -> Carbon atom
chem.molecules["glucose"]          # -> glucose molecule
chem.reactions["glycolysis_step"]  # -> reaction

# Validate
errors = chem.validate()  # Returns [] if valid

# Create state and simulate
state = StateImpl(chem, initial={"glucose": 10.0, "pyruvate": 0.0, "atp": 0.0})
sim = SimpleSimulatorImpl(chem, dt=1.0)
timeline = sim.run(state, steps=100)
```

## Alien Chemistries

Chemistry supports custom atoms for alien biology:

```python
# Define alien atoms
Xn = AtomImpl("Xn", "Xenonium", 150.5)
Zy = AtomImpl("Zy", "Zylonite", 89.3)

# Create alien molecules
alien_compound = MoleculeImpl("xzcompound", dat=dat, atoms={Xn: 2, Zy: 1})

# Build alien chemistry
alien_chem = ChemistryImpl(
    "alien_metabolism",
    atoms={"Xn": Xn, "Zy": Zy},
    molecules={"xzcompound": alien_compound},
    dat=dat,
)
```

## Validation

The `validate()` method checks:
- All molecule atoms are atoms in this chemistry
- All reaction reactants are molecules in this chemistry
- All reaction products are molecules in this chemistry

Returns a list of error messages (empty if valid).

```python
errors = chem.validate()
# ["Molecule water: atom O not in chemistry"]
# ["Reaction r1: reactant glucose not in chemistry"]
```

## Serialization

Chemistry serializes via `attributes()` which includes atoms, molecules, and reactions:

```yaml
head: Chemistry
name: glycolysis
description: Simplified glycolysis
atoms:
  C: {name: Carbon, atomic_weight: 12.011}
  H: {name: Hydrogen, atomic_weight: 1.008}
  O: {name: Oxygen, atomic_weight: 15.999}
molecules:
  glucose: {name: glucose, atoms: {C: 6, H: 12, O: 6}}
  pyruvate: {name: pyruvate}
  atp: {name: atp}
reactions:
  glycolysis_step: {name: glycolysis_step, reactants: {glucose: 1}, products: {pyruvate: 2, atp: 2}, rate: 0.1}
```

## Relationship to Other Containers

| Container | Scope | Use Case |
|-----------|-------|----------|
| **Chemistry** | Atoms + molecules + reactions | A chemical system (e.g., glycolysis) |
| **Compartment** | Nested structures | Organisms, organs, cells, organelles |

Chemistry is simpler than Compartment - it doesn't handle nesting or kind labels. Use Chemistry when you need a collection of chemical components; use Compartment for hierarchical biological structures.

## See Also

- [[Atom]] - Chemical elements
- [[Molecule]] - Chemical compounds
- [[Reaction]] - Transformations between molecules
- [[State]] - Molecule concentrations
- [[Simulator]] - Step-based simulation
- [[Compartment]] - Hierarchical biological structures
