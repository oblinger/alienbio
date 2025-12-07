# BioSystem

DAG of bioparts with molecule concentrations.

**Subsystem**: [[biology|Biology]] > Systems

## Description

BioSystem represents a biological system as a directed acyclic graph of bioparts (compartments), each containing molecule concentrations and active reactions.

## Protocol Definition

```python
from typing import Protocol

class BioSystem(Entity, Protocol):
    """DAG of bioparts with concentrations."""

    compartments: dict[str, "Compartment"]
    molecules: set[BioMolecule]
    reactions: set[BioReaction]

    def get_concentration(self, molecule: str, compartment: str) -> float:
        """Get concentration of molecule in compartment."""
        ...

    def set_concentration(self, molecule: str, compartment: str, value: float) -> None:
        """Set concentration of molecule in compartment."""
        ...
```

## Properties

| Property | Type | Description |
|----------|------|-------------|
| compartments | dict[str, Compartment] | Named compartments in the system |
| molecules | set[BioMolecule] | All molecules in the system |
| reactions | set[BioReaction] | All reactions in the system |

## Compartments

Compartments are named regions with their own concentration vectors:
- Cytoplasm
- Nucleus
- Mitochondria
- Extracellular space

Transport reactions move molecules between compartments.

## See Also

- [[entities|Entities Subsystem]]
- [[bio_organism|BioOrganism]] - Complete organism built from systems
- [[state|State]] - Snapshot of system concentrations
