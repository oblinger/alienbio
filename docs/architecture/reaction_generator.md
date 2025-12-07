# ReactionGenerator

Factory for synthetic reactions.

**Subsystem**: [[biology|Biology]] > Reactions

## Description

ReactionGenerator produces BioReactions matching statistical distributions from KEGG, including template patterns, energy distributions, and effector roles.

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

## Statistical Matching

Reactions match KEGG distributions:
- (n_reactants, n_products) template frequencies
- Delta-depth patterns per reaction class
- Activation energy and delta-G distributions
- Effector role frequencies

## See Also

- [[generators|Generators Subsystem]]
- [[generator|Generator]] - Base protocol
- [[bio_reaction|BioReaction]] - Generated type
