# SystemGenerator

Factory for complete bio-systems.

**Subsystem**: [[biology]] > Systems

## Description
SystemGenerator assembles complete BioSystems by combining molecules and reactions from other generators, establishing initial conditions and compartment structure.

## Protocol Definition
```python
from typing import Protocol

class SystemGenerator(Generator[BioSystem], Protocol):
    """Factory for complete bio-systems."""

    molecule_gen: MoleculeGenerator
    reaction_gen: ReactionGenerator

    def generate_simple(self, n_molecules: int, n_reactions: int) -> BioSystem:
        """Generate a simple single-compartment system."""
        ...

    def generate_compartmentalized(self, compartments: list[str]) -> BioSystem:
        """Generate system with specified compartments."""
        ...
```

## Properties
| Property | Type | Description |
|----------|------|-------------|
| molecule_gen | MoleculeGenerator | Source for molecules |
| reaction_gen | ReactionGenerator | Source for reactions |

## Methods
### generate_simple(n_molecules, n_reactions) -> BioSystem
Generates a simple system with specified complexity.

### generate_compartmentalized(compartments) -> BioSystem
Generates a system with named compartments and transport reactions.

## See Also
- [[generators|Generators Subsystem]]
- [[generator|Generator]] - Base protocol
- [[bio_system|BioSystem]] - Generated type
