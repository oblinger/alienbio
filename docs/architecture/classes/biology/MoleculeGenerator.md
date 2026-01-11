 [[Architecture Docs]] → [[ABIO biology]]

# MoleculeGenerator

Factory for synthetic molecules.

## Overview
MoleculeGenerator produces BioMolecules with configurable properties. Different named instances can match specific distributions (e.g., KEGG-like) or generate purely synthetic molecules.

| Methods | Description |
|---------|-------------|
| generate_primitive | Generate a bdepth=0 molecule |
| generate_at_depth | Generate molecule at specific biosynthetic depth |
| generate_name | Generate alien molecule name |

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

### generate_at_depth(bdepth) -> BioMolecule
Generates a molecule at the specified biosynthetic depth.

### generate_name() -> str
Generates an alien name using Markov chain or diffusion model.

## Configurable Properties
Implementations can parameterize:
- Atom count distributions per bdepth
- Functional group frequencies
- Molecular weight distributions
- Naming patterns (Markov, diffusion, etc.)

## See Also
- [[ABIO biology]]
- [[Generator]] - Base protocol
- [[BioMolecule]] - Generated type
