 [[Architecture Docs]] → [[ABIO biology]]

# Chemistry

Container for atoms, molecules, and reactions forming a chemical system.

## Overview
Chemistry provides a container for grouping related chemical components together. It acts as the "world" for a chemical system, enabling organization, validation, and state management for simulation. Chemistry supports alien chemistries with custom atoms.

| Property | Type | Description |
|----------|------|-------------|
| `local_name` | str | Entity identifier |
| `atoms` | Dict[str, Atom] | Chemical elements by symbol |
| `molecules` | Dict[str, Molecule] | Chemical compounds by name |
| `reactions` | Dict[str, Reaction] | Transformations by name |

| Method | Returns | Description |
|--------|---------|-------------|
| `validate()` | List[str] | Check that all reaction molecules exist |
| `attributes()` | Dict[str, Any] | Semantic content for serialization |

## Discussion

### Design Decisions
- **Public attributes** - Direct dict access, no property wrappers
- **Constructor takes all three** - Built as a complete unit
- **Conceptually immutable** - Though technically mutable, treat as fixed after construction
- **No parent relationships** - Molecules/reactions stored in dicts, not as entity children
- **Still an Entity** - For serialization and DAT support

### Usage Example
```python
from alienbio import ChemistryImpl, MoleculeImpl, ReactionImpl, get_atom

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
)

# Direct access to components
chem.atoms["C"]                    # -> Carbon atom
chem.molecules["glucose"]          # -> glucose molecule
chem.reactions["glycolysis_step"]  # -> reaction

# Validate
errors = chem.validate()  # Returns [] if valid
```

### Alien Chemistries
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

### Validation
The `validate()` method checks:
- All molecule atoms are atoms in this chemistry
- All reaction reactants are molecules in this chemistry
- All reaction products are molecules in this chemistry

```python
errors = chem.validate()
# ["Molecule water: atom O not in chemistry"]
# ["Reaction r1: reactant glucose not in chemistry"]
```

### Serialization
```yaml
head: Chemistry
name: glycolysis
atoms:
  C: {name: Carbon, atomic_weight: 12.011}
  H: {name: Hydrogen, atomic_weight: 1.008}
molecules:
  glucose: {atoms: {C: 6, H: 12, O: 6}}
reactions:
  glycolysis_step: {reactants: {glucose: 1}, products: {pyruvate: 2}, rate: 0.1}
```

### Relationship to Compartment

| Container | Scope | Use Case |
|-----------|-------|----------|
| **Chemistry** | Atoms + molecules + reactions | A chemical system (e.g., glycolysis) |
| **Compartment** | Nested structures | Organisms, organs, cells, organelles |

Chemistry is simpler than Compartment - it doesn't handle nesting or kind labels. Use Chemistry when you need a collection of chemical components; use Compartment for hierarchical biological structures.

## Method Details

### `validate() -> List[str]`
Check that all reaction molecules exist in this chemistry.

**Returns:** List of error messages (empty if valid)

**Example:**
```python
errors = chem.validate()
if errors:
    for e in errors:
        print(e)
```

## ChemistryImpl Class Methods

### `hydrate(data, *, dat=None, parent=None, local_name=None) -> ChemistryImpl` (classmethod)
Create a ChemistryImpl from a dict, recursively hydrating molecules and reactions.

**Args:**
- `data`: Dict with keys: `molecules`, `reactions`, `atoms`, `description`
- `dat`: DAT anchor (if root entity)
- `parent`: Parent entity (if child)
- `local_name`: Override name

**Returns:** New ChemistryImpl with hydrated molecules and reactions

The hydration process:
1. First pass: hydrate all molecules from `data["molecules"]`
2. Second pass: hydrate reactions from `data["reactions"]`, linking to hydrated molecules

```yaml
# YAML spec data (loaded by bio.fetch)
name: glycolysis
molecules:
  glucose:
    bdepth: 2
  pyruvate:
    bdepth: 1
reactions:
  step1:
    reactants: [glucose]
    products:
      - pyruvate: 2
    rate: 0.1
```

```python
# Hydrate from loaded YAML dict
chemistry = ChemistryImpl.hydrate(chem_data)

# Access hydrated components
chemistry.molecules["glucose"]  # -> MoleculeImpl
chemistry.reactions["step1"]    # -> ReactionImpl with molecule refs
```

## Protocol
```python
from typing import Protocol, Dict, List, runtime_checkable

@runtime_checkable
class Chemistry(Protocol):
    """Protocol for chemistry containers."""

    @property
    def local_name(self) -> str:
        """The chemistry's local name."""
        ...

    @property
    def atoms(self) -> Dict[str, Atom]:
        """All atoms in this chemistry (by symbol)."""
        ...

    @property
    def molecules(self) -> Dict[str, Molecule]:
        """All molecules in this chemistry (by name)."""
        ...

    @property
    def reactions(self) -> Dict[str, Reaction]:
        """All reactions in this chemistry (by name)."""
        ...

    def validate(self) -> List[str]:
        """Validate the chemistry for consistency."""
        ...
```

## See Also
- [[Atom]] - Chemical elements
- [[Molecule]] - Chemical compounds
- [[Reaction]] - Transformations between molecules
- [[State]] - Molecule concentrations
- [[Simulator]] - Step-based simulation
- [[Compartment]] - Hierarchical biological structures
