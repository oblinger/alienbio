# Expr
**Subsystem**: [[ABIO infra]] > Entities
Simple functional expression protocol.

## Description
Expr provides a uniform way to represent functional information - function calls, declarations, and structured data. The print format mirrors Python function call syntax for familiarity.

| Properties | Type | Description |
|----------|------|-------------|
| head | str | Function/operation name |
| args | tuple[Any, ...] | Positional arguments |
| kwargs | dict[str, Any] | Keyword arguments |

## Protocol Definition
```python
from typing import Protocol, Any

class Expr(Protocol):
    """Simple functional expression."""

    head: str                      # function/operation name
    args: tuple[Any, ...]          # positional arguments
    kwargs: dict[str, Any]         # keyword arguments

    def __str__(self) -> str:
        """Print as function call: head(args..., key=val...)"""
        ...
```

## Print Format
Expressions print as Python-style function calls:

```python
# Just head
expr("checkpoint")           # checkpoint()

# With positional args
expr("measure", "glucose")   # measure(glucose)

# With keyword args
expr("set_rate", k=0.5)      # set_rate(k=0.5)

# Mixed
expr("react", "A", "B", rate=1.2)  # react(A, B, rate=1.2)
```

## Common Uses
**Prefix definitions:**
```
define_prefix(M, world1.molecules)
define_prefix(R, world1.reactions)
```

**Measurements:**
```
measure(M:glucose, compartment=cytoplasm)
```

**Actions:**
```
add(M:inhibitor, concentration=0.1)
remove(R:glycolysis_step3)
```

**Declarations:**
```
reaction(M:A, M:B, produces=M:C, rate=0.5)
```

## Parsing
Expressions can be parsed from their string representation back into Expr objects, enabling round-trip serialization.

## See Also
- [[Entity]] - Base protocol
- [[Print-format]] - Display conventions using Expr
