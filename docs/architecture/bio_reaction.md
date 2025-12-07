# BioReaction

Transformation between molecules.

**Subsystem**: [[biology|Biology]] > Reactions

## Description

BioReaction represents a chemical transformation that converts reactants to products, modulated by effectors. Reactions have rate functions that determine how fast they proceed.

## Protocol Definition

```python
from typing import Protocol, Callable
from enum import Enum

class ReactionClass(Enum):
    ANABOLIC = "anabolic"
    CATABOLIC = "catabolic"
    ENERGY = "energy"

class BioReaction(Entity, Protocol):
    """Transformation between molecules."""

    reactants: list[tuple[BioMolecule, int]]  # (molecule, stoichiometry)
    products: list[tuple[BioMolecule, int]]
    effectors: list[tuple[BioMolecule, str]]  # (molecule, role)
    rate_fn: Callable[[dict[str, float]], float]
    reaction_class: ReactionClass

    def compute_rate(self, concentrations: dict[str, float]) -> float:
        """Compute reaction rate given current concentrations."""
        ...
```

## Properties

| Property | Type | Description |
|----------|------|-------------|
| reactants | list[tuple] | (molecule, stoichiometry) pairs consumed |
| products | list[tuple] | (molecule, stoichiometry) pairs produced |
| effectors | list[tuple] | (molecule, role) where role is catalyst/inhibitor/cofactor |
| rate_fn | Callable | Rate function from concentrations to rate |
| reaction_class | ReactionClass | Anabolic, catabolic, or energy |

## Reaction Classes

- **Anabolic**: Build complex from simple, increase bdepth, consume energy
- **Catabolic**: Break down complex, decrease bdepth, release energy
- **Energy**: Closed-loop carriers (ATP/NADH analogs)

## See Also

- [[reactions|Reactions Subsystem]]
- [[reaction_generator|ReactionGenerator]] - Factory for reactions
- [[pathway|Pathway]] - Connected reaction sequences
