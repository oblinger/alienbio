# Generator

Base protocol for synthetic biology factories.

**Subsystem**: [[biology]] > Generators

## Description
Generator is the base protocol for factories that produce synthetic biology components matching statistical distributions captured from Earth biochemistry.

## Protocol Definition
```python
from typing import Protocol, TypeVar, Generic

T = TypeVar("T")

class Generator(Protocol, Generic[T]):
    """Base protocol for biology factories."""

    model: "BioChemistryModel"
    seed: int

    def generate(self) -> T:
        """Generate a new instance."""
        ...

    def generate_batch(self, n: int) -> list[T]:
        """Generate multiple instances."""
        ...
```

## Properties
| Property | Type | Description |
|----------|------|-------------|
| model | BioChemistryModel | Statistical distributions to match |
| seed | int | Random seed for reproducibility |

## Methods
### generate() -> T
Generates a single new instance matching the statistical model.

### generate_batch(n: int) -> list[T]
Generates multiple instances efficiently.

## See Also
- [[generators|Generators Subsystem]]
- [[molecule_generator|MoleculeGenerator]]
- [[reaction_generator|ReactionGenerator]]
- [[system_generator|SystemGenerator]]
