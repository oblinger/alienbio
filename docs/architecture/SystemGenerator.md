# SystemGenerator
**Subsystem**: [[biology]] > Systems
Factory for complete bio-systems.

## Description
SystemGenerator assembles complete BioSystems by combining molecules and reactions from other generators, establishing initial conditions and compartment structure.

| Properties | Type | Description |
|----------|------|-------------|
| molecule_gen | MoleculeGenerator | Source for molecules |
| reaction_gen | ReactionGenerator | Source for reactions |

| Methods | Description |
|--------|-------------|
| generate_simple | Generate a simple single-compartment system |
| generate_compartmentalized | Generate system with specified compartments |

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

## Methods
### generate_simple(n_molecules, n_reactions) -> BioSystem
Generates a simple system with specified complexity. Creates a single compartment with the requested number of molecules and reactions connecting them.

### generate_compartmentalized(compartments) -> BioSystem
Generates a system with named compartments and transport reactions between them.

## See Also
- [[biology]]
- [[Generator]] - Base protocol
- [[BioSystem]] - Generated type
