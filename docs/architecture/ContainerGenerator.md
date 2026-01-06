# ContainerGenerator
**Subsystem**: [[ABIO biology]] > Containers
Composable factory for BioContainers.

## Overview
ContainerGenerator creates BioContainers by composing simpler generators. Generators are recursively composable: a ContainerGenerator uses MoleculeGenerators and ReactionGenerators internally, and can itself be used by other ContainerGenerators to build deeper hierarchies. This allows complex biological structures to emerge from simple, reusable building blocks.

| Properties | Type | Description |
|----------|------|-------------|
| molecule_gen | MoleculeGenerator | Source for molecules |
| reaction_gen | ReactionGenerator | Source for reactions |
| child_gen | ContainerGenerator | Optional source for child containers |

| Methods | Description |
|--------|-------------|
| generate | Generate a container with specified parameters |
| compose | Combine with another generator to create nested structures |

## Protocol Definition
```python
from typing import Protocol, Optional

class ContainerGenerator(Generator[BioContainer], Protocol):
    """Composable factory for BioContainers."""

    molecule_gen: MoleculeGenerator
    reaction_gen: ReactionGenerator
    child_gen: Optional["ContainerGenerator"]

    def generate(self, n_molecules: int, n_reactions: int,
                 n_children: int = 0, depth: int = 1) -> BioContainer:
        """Generate a container, optionally with nested children."""
        ...

    def compose(self, child_generator: "ContainerGenerator") -> "ContainerGenerator":
        """Return a new generator that uses this for children."""
        ...
```

## Methods
### generate(n_molecules, n_reactions, n_children, depth) -> BioContainer
Creates a container with the specified number of molecules and reactions. If n_children > 0, recursively generates child containers using child_gen (or self if no child_gen specified). The depth parameter limits recursion.

### compose(child_generator) -> ContainerGenerator
Returns a new ContainerGenerator that uses child_generator to produce its nested containers. This enables building generators for complex hierarchies from simpler ones.

## Composability Pattern
```python
# Simple generators for different scales
organelle_gen = ContainerGenerator(molecule_gen, reaction_gen)
cell_gen = organelle_gen.compose(organelle_gen)  # cells contain organelles
organ_gen = cell_gen.compose(cell_gen)           # organs contain cells

# Generate a complete organ with nested structure
organ = organ_gen.generate(n_molecules=10, n_reactions=5, n_children=100, depth=3)
```

## See Also
- [[ABIO biology]]
- [[Generator]] - Base protocol
- [[BioContainer]] - Generated type
- [[MoleculeGenerator]] - Composed for molecules
- [[ReactionGenerator]] - Composed for reactions
