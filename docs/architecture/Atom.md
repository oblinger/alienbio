# Atom
**Subsystem**: [[ABIO biology]] > Atoms
Chemical element with symbol, name, and atomic weight.

## Description
Atom represents a chemical element - the building block of molecules. Atoms are immutable value objects that can be shared across multiple molecules and chemistries. They are constants, not entities in the tree structure.

| Properties | Type | Description |
|----------|------|-------------|
| symbol | str | Chemical symbol (1-2 letters): 'C', 'H', 'Na' |
| name | str | Human-readable name: 'Carbon', 'Hydrogen' |
| atomic_weight | float | Atomic mass in atomic mass units |

## Protocol Definition
```python
from typing import Protocol

@runtime_checkable
class Atom(Protocol):
    """Protocol for atomic elements."""

    @property
    def symbol(self) -> str:
        """Chemical symbol (1-2 letters): 'C', 'H', 'O', 'Na'."""
        ...

    @property
    def name(self) -> str:
        """Human-readable name: 'Carbon', 'Hydrogen'."""
        ...

    @property
    def atomic_weight(self) -> float:
        """Atomic mass in atomic mass units."""
        ...
```

## Implementation

```python
from alienbio import AtomImpl, get_atom, COMMON_ATOMS

# Create a custom atom
helium = AtomImpl("He", "Helium", 4.003)

# Use pre-defined common atoms
carbon = get_atom("C")
hydrogen = get_atom("H")

# Access the full set
print(COMMON_ATOMS.keys())
# {'H', 'C', 'N', 'O', 'P', 'S', 'Na', 'K', 'Ca', 'Mg', 'Cl', 'Fe', 'Zn', 'Cu'}
```

## Common Atoms

The system provides a set of common biological atoms:

| Symbol | Name | Atomic Weight |
|--------|------|---------------|
| H | Hydrogen | 1.008 |
| C | Carbon | 12.011 |
| N | Nitrogen | 14.007 |
| O | Oxygen | 15.999 |
| P | Phosphorus | 30.974 |
| S | Sulfur | 32.065 |
| Na | Sodium | 22.990 |
| K | Potassium | 39.098 |
| Ca | Calcium | 40.078 |
| Mg | Magnesium | 24.305 |
| Cl | Chlorine | 35.453 |
| Fe | Iron | 55.845 |
| Zn | Zinc | 65.38 |
| Cu | Copper | 63.546 |

## Usage in Molecules

Atoms are used as dictionary keys in molecule composition:

```python
from alienbio import MoleculeImpl, get_atom

C = get_atom("C")
H = get_atom("H")
O = get_atom("O")

# Water: H2O
water = MoleculeImpl("water", dat=dat, atoms={H: 2, O: 1})

# Glucose: C6H12O6
glucose = MoleculeImpl("glucose", dat=dat, atoms={C: 6, H: 12, O: 6})
```

## See Also
- [[Molecule]] - Composed of atoms
- [[ABIO biology]]
