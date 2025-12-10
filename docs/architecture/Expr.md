# Expr
**Subsystem**: [[ABIO infra]] > Entities
Functional expression trees for representing computations, rate equations, and structured data.

## Overview
Expr provides a uniform way to represent functional expressions as data. Expression trees can be parsed from strings, serialized to YAML/JSON, and evaluated or compiled by an [[Interpreter]]. The format mirrors Python function call syntax for familiarity.

| Property | Type | Description |
|----------|------|-------------|
| `head` | str | Function/operation name |
| `args` | Tuple[ExprArg, ...] | Positional arguments (may include nested Expr) |
| `kwargs` | Dict[str, ExprArg] | Keyword arguments (may include nested Expr) |

| Method       | Returns | Description                               |
| ------------ | ------- | ----------------------------------------- |
| `parse(s)`   | Expr    | (classmethod) Parse string into Expr tree |
| `print()`    | str     | Format as Python-style function call      |
| `__str__()`  | str     | Alias for `print()`                       |
| `__repr__()` | str     | Debug representation                      |

## Discussion
### String Format

Expressions print as Python-style function calls:

```python
Expr("constant")                    # → "constant()"
Expr("measure", "glucose")          # → "measure(glucose)"
Expr("rate", k=0.5)                 # → "rate(k=0.5)"
Expr("react", "A", "B", rate=1.2)   # → "react(A, B, rate=1.2)"

# Nested expressions
Expr("div", Expr("var", "S"), Expr("add", Expr("var", "S"), 0.5))
# → "div(var(S), add(var(S), 0.5))"
```

### Common Operations

Standard operations available as Expr heads:

| Head | Args | Description |
|------|------|-------------|
| `var` | name | Variable reference |
| `const` | value | Constant value |
| `add` | a, b, ... | Sum |
| `mul` | a, b, ... | Product |
| `div` | a, b | Division |
| `sub` | a, b | Subtraction |
| `power` | base, exp | Exponentiation |
| `neg` | a | Negation |
| `exp` | a | e^a |
| `log` | a | Natural log |
| `min` | a, b | Minimum |
| `max` | a, b | Maximum |
| `if` | cond, then, else | Conditional |
| `gt`, `lt`, `ge`, `le`, `eq` | a, b | Comparisons |
| `and`, `or`, `not` | ... | Boolean logic |

### Templates (Macros)

Template functions expand parameterized expressions into full Expr trees:

```python
# Template definition (in catalog/rate_equations.py)
def michaelis_menten(vmax: float, km: float) -> Expr:
    """Michaelis-Menten: vmax * S / (km + S)"""
    return Expr("mul", vmax,
        Expr("div",
            Expr("var", "S"),
            Expr("add", km, Expr("var", "S"))))
```

Usage:
```python
# As string (parsed, then template expanded by Interpreter)
rate = "michaelis_menten(vmax=10.0, km=5.0)"

# As explicit Expr
rate = Expr("michaelis_menten", vmax=10.0, km=5.0)
```

### Serialization

Expr trees serialize naturally to YAML/JSON:

```yaml
# As string (compact)
rate: "michaelis_menten(vmax=10.0, km=5.0)"

# As structured data (explicit)
rate:
  head: michaelis_menten
  kwargs:
    vmax: 10.0
    km: 5.0
```

### Design Decisions

**Why Expr over raw Python lambdas?**
1. **Serialization**: Expr saves to YAML/JSON, lambdas cannot
2. **Inspection**: Can analyze, transform, optimize Expr trees
3. **Portability**: Compile to Lua/Rhai/WASM for Rust runtime
4. **Safety**: Restricted operation set, no arbitrary code execution

**Why Python-like syntax?**
1. Users already know it
2. Python's `ast` module handles parsing
3. Natural mapping to Expr structure

**Separation from Interpreter**: Expr is pure data representation. [[Interpreter]] handles evaluation, template expansion, and language dispatch.

## Method Details

### `parse(s: str) -> Expr`

Parse a string into an Expr tree.

**Args:**
- `s`: String in Python-like function call syntax

**Returns:** Expr tree

**Raises:**
- `ValueError`: If string cannot be parsed as valid Expr

**Example:**
```python
Expr.parse("constant")
# → Expr(head="constant", args=(), kwargs={})

Expr.parse("michaelis_menten(vmax=10.0, km=5.0)")
# → Expr(head="michaelis_menten", args=(), kwargs={"vmax": 10.0, "km": 5.0})

Expr.parse("hill(2, k=0.5)")
# → Expr(head="hill", args=(2,), kwargs={"k": 0.5})
```

The parser uses Python's `ast` module on a restricted subset:
- **Allowed**: identifiers, numbers, strings, booleans, function calls
- **Rejected**: imports, assignments, operators, complex expressions

Round-trip property: `Expr.parse(s).print()` produces equivalent string.

### `print() -> str`

Format as Python-style function call.

**Returns:** String representation

**Example:**
```python
Expr("div", Expr("var", "S"), 5.0).print()
# → "div(var(S), 5.0)"
```

Future versions may add parameters for indentation and multiline formatting of complex expressions.

### `__str__() -> str`

Alias for `print()`. Allows use with Python's `str()` function.

### `__repr__() -> str`

Debug representation showing the Expr structure explicitly.

**Example:**
```python
repr(Expr("add", 1, 2))
# → "Expr('add', args=(1, 2), kwargs={})"
```

## Protocol

```python
from typing import Any, Dict, Protocol, Tuple, Union

# Expr nodes can contain literals or nested expressions
ExprArg = Union['Expr', float, int, str, bool, None]


class Expr(Protocol):
    """Functional expression tree node."""

    @property
    def head(self) -> str:
        """Function/operation name."""
        ...

    @property
    def args(self) -> Tuple[ExprArg, ...]:
        """Positional arguments."""
        ...

    @property
    def kwargs(self) -> Dict[str, ExprArg]:
        """Keyword arguments."""
        ...

    @classmethod
    def parse(cls, s: str) -> 'Expr':
        """Parse a string into an Expr tree."""
        ...

    def print(self) -> str:
        """Format as Python-style function call."""
        ...

    def __str__(self) -> str:
        """Alias for print()."""
        ...

    def __repr__(self) -> str:
        """Debug representation."""
        ...
```

## See Also

- [[Interpreter]] - Evaluates Expr trees
- [[Flow]] - Uses Expr for rate equations
- [[Reaction]] - Uses Expr for rate equations
- [[IO]] - do.load for template resolution
