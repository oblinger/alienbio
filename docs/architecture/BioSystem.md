# BioSystem
**Subsystem**: [[biology]] > Systems
DAG of bioparts with molecule concentrations.

## Description
BioSystem represents a biological system as a directed acyclic graph of bioparts (compartments), each containing molecule concentrations and active reactions.

| Properties | Type | Description |
|----------|------|-------------|
| compartments | dict[str, Compartment] | Named compartments in the system |
| molecules | set[BioMolecule] | All molecules in the system |
| reactions | set[BioReaction] | All reactions in the system |

| Methods | Description |
|---------|-------------|
| get_concentration | Get concentration of molecule in compartment |
| set_concentration | Set concentration of molecule in compartment |

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

## Methods
### get_concentration(molecule, compartment) -> float
Get concentration of molecule in compartment.

### set_concentration(molecule, compartment, value)
Set concentration of molecule in compartment.

## Compartments
Compartments are named regions with their own concentration vectors:
- Cytoplasm
- Nucleus
- Mitochondria
- Extracellular space

Transport reactions move molecules between compartments.

## See Also
- [[biology]]
- [[BioOrganism]] - Complete organism built from systems
- [[State]] - Snapshot of system concentrations
