# BioMolecule

Chemical compound with atoms, bonds, and properties.

**Subsystem**: [[biology]] > Molecules

## Description
BioMolecule represents a chemical compound in the alien biology. It tracks atom composition, bond structure, and derived properties. Molecules are typically PersistentEntities (the type definition) but can also be ScopedEntities (a specific instance with concentration).

## Protocol Definition
```python
from typing import Protocol

class BioMolecule(Entity, Protocol):
    """Chemical compound in the biology."""

    atoms: dict[str, int]  # element -> count
    bonds: list[tuple[int, int, int]]  # (atom1, atom2, bond_order)
    bdepth: int  # biosynthetic depth

    @property
    def molecular_weight(self) -> float:
        """Computed molecular weight."""
        ...

    @property
    def functional_groups(self) -> list[str]:
        """Identified functional groups."""
        ...
```

## Properties
| Property | Type | Description |
|----------|------|-------------|
| atoms | dict[str, int] | Element symbol to count |
| bonds | list[tuple] | Bond graph as (atom1, atom2, order) |
| bdepth | int | Biosynthetic depth (0 = primitive) |
| molecular_weight | float | Computed from atom masses |
| functional_groups | list[str] | Reactive sites identified |

## Biosynthetic Depth
- **bdepth=0**: Primitive molecules built from atoms (CO2, H2O analogs)
- **bdepth=1-3**: Metabolites, intermediate compounds
- **bdepth=4+**: Complex molecules (proteins, lipids)

## See Also
- [[biology]]
- [[MoleculeGenerator]] - Factory for molecules
- [[BioReaction]] - Transforms molecules
