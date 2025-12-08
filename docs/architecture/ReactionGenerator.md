# ReactionGenerator
**Subsystem**: [[ABIO biology]] > Reactions
Factory for synthetic reactions.

## Description
ReactionGenerator produces BioReactions with configurable kinetics and stoichiometry. Different named instances can match specific distributions (e.g., KEGG-like) or generate purely synthetic reactions.

| Methods | Description |
|---------|-------------|
| generate_anabolic | Generate anabolic reaction from given inputs |
| generate_catabolic | Generate catabolic reaction breaking down input |
| generate_energy | Generate energy carrier reaction |

## Protocol Definition
```python
from typing import Protocol

class ReactionGenerator(Generator[BioReaction], Protocol):
    """Factory for synthetic reactions."""

    def generate_anabolic(self, inputs: list[BioMolecule]) -> BioReaction:
        """Generate anabolic reaction from given inputs."""
        ...

    def generate_catabolic(self, input: BioMolecule) -> BioReaction:
        """Generate catabolic reaction breaking down input."""
        ...

    def generate_energy(self) -> BioReaction:
        """Generate energy carrier reaction."""
        ...
```

## Methods
### generate_anabolic(inputs) -> BioReaction
Generates a reaction that builds a higher-depth molecule from inputs.

### generate_catabolic(input) -> BioReaction
Generates a reaction that breaks down a molecule into simpler products.

### generate_energy() -> BioReaction
Generates an energy carrier reaction (alien ATP/NADH analog).

## Configurable Properties
Implementations can parameterize:
- (n_reactants, n_products) template frequencies
- Delta-depth patterns per reaction class
- Activation energy and delta-G distributions
- Effector role frequencies

## See Also
- [[ABIO biology]]
- [[Generator]] - Base protocol
- [[BioReaction]] - Generated type
