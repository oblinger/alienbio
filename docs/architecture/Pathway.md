# Pathway
**Subsystem**: [[ABIO biology]] > Pathways
Connected sequence of reactions (analytical abstraction).

## Overview
A Pathway is a connected subgraph of the reaction network that performs a coherent metabolic function, such as a biosynthetic pathway, energy cycle, or signaling cascade.

Pathway is an **analytical abstraction** - it's useful for understanding, generating, and describing reaction networks, but the simulation itself operates directly on Reactions without needing pathway information.

| Properties | Type | Description |
|----------|------|-------------|
| reactions | list | Ordered reactions in the pathway |
| entry_molecules | set | Molecules consumed from outside |
| exit_molecules | set | Molecules produced for outside |
| pathway_type | PathwayType | Linear, branching, cyclic, or signaling |
| net_stoichiometry | dict | Net consumption/production |

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

    reactions: list[Reaction]
    entry_molecules: set[Molecule]
    exit_molecules: set[Molecule]
    pathway_type: PathwayType

    @property
    def net_stoichiometry(self) -> dict[str, int]:
        """Net input/output across the pathway."""
        ...
```

## Use Cases

- **Understanding**: Identify which reactions form glycolysis, TCA cycle, etc.
- **Generation**: Create coherent synthetic biologies with sensible pathway structures
- **Analysis**: Find bottlenecks, understand metabolic flow
- **Task design**: "Diagnose a defect in this pathway"

## See Also
- [[ABIO biology]]
- [[Reaction]] - Individual reactions
- [[Chemistry]] - Container for molecules and reactions
