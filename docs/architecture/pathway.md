# Pathway

Connected sequence of reactions.

**Subsystem**: [[biology]] > Pathways

## Description
Pathway represents a connected subgraph of the reaction network, forming a coherent metabolic function like a biosynthesis chain, energy cycle, or signaling cascade.

## Protocol Definition
```python
from typing import Protocol
from enum import Enum

class PathwayType(Enum):
    LINEAR = "linear"
    BRANCHING = "branching"
    CYCLIC = "cyclic"
    SIGNALING = "signaling"

class Pathway(Entity, Protocol):
    """Connected sequence of reactions."""

    reactions: list[BioReaction]
    entry_molecules: set[BioMolecule]
    exit_molecules: set[BioMolecule]
    pathway_type: PathwayType

    @property
    def net_stoichiometry(self) -> dict[str, int]:
        """Net input/output across the pathway."""
        ...
```

## Properties
| Property | Type | Description |
|----------|------|-------------|
| reactions | list | Ordered reactions in the pathway |
| entry_molecules | set | Molecules consumed from outside |
| exit_molecules | set | Molecules produced for outside |
| pathway_type | PathwayType | Linear, branching, cyclic, or signaling |
| net_stoichiometry | dict | Net consumption/production |

## See Also
- [[pathways|Pathways Subsystem]]
- [[bio_reaction|BioReaction]] - Individual reactions
