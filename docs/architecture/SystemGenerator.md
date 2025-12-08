# SystemGenerator
**Subsystem**: [[biology]] > Containers
Factory for complete container hierarchies.

## Description
SystemGenerator assembles complete BioContainers by combining molecules and reactions from other generators, establishing initial conditions and container structure.

| Properties | Type | Description |
|----------|------|-------------|
| molecule_gen | MoleculeGenerator | Source for molecules |
| reaction_gen | ReactionGenerator | Source for reactions |

| Methods | Description |
|--------|-------------|
| generate_simple | Generate a simple single-container system |
| generate_nested | Generate nested container hierarchy |

## Protocol Definition
```python
from typing import Protocol

class SystemGenerator(Generator[BioContainer], Protocol):
    """Factory for complete container hierarchies."""

    molecule_gen: MoleculeGenerator
    reaction_gen: ReactionGenerator

    def generate_simple(self, n_molecules: int, n_reactions: int) -> BioContainer:
        """Generate a simple single-container system."""
        ...

    def generate_nested(self, structure: dict) -> BioContainer:
        """Generate nested container hierarchy from structure spec."""
        ...
```

## Methods
### generate_simple(n_molecules, n_reactions) -> BioContainer
Generates a simple container with specified complexity. Creates a single container with the requested number of molecules and reactions.

### generate_nested(structure) -> BioContainer
Generates a nested container hierarchy based on a structure specification.

## See Also
- [[biology]]
- [[Generator]] - Base protocol
- [[BioContainer]] - Generated type
