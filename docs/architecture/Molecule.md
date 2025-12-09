# Molecule
**Subsystem**: [[ABIO biology]] > Molecules
Chemical compound composed of atoms with derived properties.

## Description
Molecule represents a chemical compound in the alien biology. It is composed of Atoms and has:
- **atoms**: Atom composition as `Dict[Atom, int]`
- **bdepth**: Biosynthetic depth (0 = primitive, higher = more complex)
- **name**: Human-readable name (e.g., "glucose", "water")
- **symbol**: Chemical formula derived from atoms (e.g., "C6H12O6")
- **molecular_weight**: Computed from atom weights

Molecules are Entity subclasses that can participate in reactions.

| Properties | Type | Description |
|----------|------|-------------|
| local_name | str | Entity identifier within parent |
| atoms | Dict[Atom, int] | Atom composition: {atom: count} |
| bdepth | int | Biosynthetic depth (0 = primitive) |
| name | str | Human-readable name |
| symbol | str | Chemical formula (derived from atoms) |
| molecular_weight | float | Computed from atom weights (derived) |

## Protocol Definition
```python
from typing import Protocol, Dict

@runtime_checkable
class Molecule(Protocol):
    """Protocol for molecule entities."""

    @property
    def local_name(self) -> str:
        """The molecule's local name within its parent entity."""
        ...

    @property
    def atoms(self) -> Dict[Atom, int]:
        """Atom composition: {atom: count}."""
        ...

    @property
    def bdepth(self) -> int:
        """Biosynthetic depth (0 = primitive, 4+ = complex)."""
        ...

    @property
    def name(self) -> str:
        """Human-readable name: 'glucose', 'water'."""
        ...

    @property
    def symbol(self) -> str:
        """Chemical formula derived from atoms: 'C6H12O6', 'H2O'."""
        ...

    @property
    def molecular_weight(self) -> float:
        """Molecular mass computed from atom weights."""
        ...
```

## Implementation

```python
from alienbio import MoleculeImpl, get_atom

# Create atoms
C = get_atom("C")
H = get_atom("H")
O = get_atom("O")

# Create glucose molecule
glucose = MoleculeImpl(
    "glucose",
    dat=dat,
    atoms={C: 6, H: 12, O: 6},
    bdepth=2,
    name="Glucose"
)

glucose.symbol           # "C6H12O6" (Hill system ordering)
glucose.molecular_weight # ~180.156
```

## Biosynthetic Depth
- **bdepth=0**: Primitive molecules built from atoms (CO2, H2O analogs)
- **bdepth=1-3**: Metabolites, intermediate compounds
- **bdepth=4+**: Complex molecules (proteins, lipids)

## See Also
- [[Atom]] - Chemical elements
- [[ABIO biology]]
- [[MoleculeGenerator]] - Factory for molecules
- [[Reaction]] - Transforms molecules
