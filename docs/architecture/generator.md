# Generator
**Subsystem**: [[biology]] > Generators
Base protocol for synthetic biology factories.

## Description
Generator is the base protocol for factories that produce synthetic biology components matching statistical distributions captured from Earth biochemistry.

| Properties | Type | Description |
|----------|------|-------------|
| model | BioChemistryModel | Statistical distributions to match |
| seed | int | Random seed for reproducibility |

| Methods | Description |
|---------|-------------|
| generate | Generate a new instance |
| generate_batch | Generate multiple instances |

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

## Methods
### generate() -> T
Generates a single new instance matching the statistical model.

### generate_batch(n) -> list[T]
Generates multiple instances efficiently.

## See Also
- [[biology]]
- [[MoleculeGenerator]]
- [[ReactionGenerator]]
- [[SystemGenerator]]
