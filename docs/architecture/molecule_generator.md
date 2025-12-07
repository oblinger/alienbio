# MoleculeGenerator

Factory for synthetic molecules.

**Subsystem**: [[biology|Biology]] > Molecules

## Description

MoleculeGenerator produces BioMolecules matching statistical distributions captured from KEGG, including atom counts, functional groups, and naming patterns.

## Protocol Definition

```python
from typing import Protocol

class MoleculeGenerator(Generator[BioMolecule], Protocol):
    """Factory for synthetic molecules."""

    def generate_primitive(self) -> BioMolecule:
        """Generate a bdepth=0 molecule."""
        ...

    def generate_at_depth(self, bdepth: int) -> BioMolecule:
        """Generate molecule at specific biosynthetic depth."""
        ...

    def generate_name(self) -> str:
        """Generate alien molecule name."""
        ...
```

## Methods

### generate_primitive() -> BioMolecule
Generates a bdepth=0 primitive molecule from alien atoms.

### generate_at_depth(bdepth: int) -> BioMolecule
Generates a molecule at the specified biosynthetic depth.

### generate_name() -> str
Generates an alien name using Markov chain or diffusion model.

## Statistical Matching

Molecules are generated to match KEGG distributions:
- Atom count distributions per bdepth
- Functional group frequencies
- Molecular weight distributions

## See Also

- [[generators|Generators Subsystem]]
- [[generator|Generator]] - Base protocol
- [[bio_molecule|BioMolecule]] - Generated type
