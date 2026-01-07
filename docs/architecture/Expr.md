# Expr

# ============================================================
# DO NOT IMPLEMENT — POSSIBLE FUTURE EXTENSION
# ============================================================
#
# This document describes a structured expression tree format
# that was considered but DEFERRED in favor of Python strings.
#
# Current approach: Use Python expression strings everywhere.
# See [[Spec Evaluation]] for the actual implementation.
#
# This design is preserved because:
# 1. It may be needed if we add a Rust-native backend
# 2. The thinking about multi-backend support is valuable
# 3. Dict/list forms may be useful for programmatic generation
#
# ============================================================

**Subsystem**: [[ABIO infra]] > Entities  (See **[[Spec Evaluation]]**)

**Status**: DEFERRED — Not implemented. Using Python strings instead.

---

## Why This Was Deferred

We considered structured Expr trees for multi-backend support:
- NumPy backend: interpret with np ops
- JAX backend: interpret with jnp ops
- Rust backend: interpret natively with SIMD

**Decision**: Use Python expression strings instead because:

1. **JAX compilation**: At simulator creation time, we generate a Python module containing all rate functions. JAX traces this module and compiles to GPU kernels. No per-step Python overhead.

2. **Simpler architecture**: Strings are readable, familiar, and sufficient. No need for parallel interpreters.

3. **Generated module is inspectable**: Humans can read the generated Python for debugging.

4. **If we need Rust later**: We can parse Python strings → derive Expr trees → send to Rust. The Expr tree becomes an internal IR, not a user-facing format.

See [[Simulator]] for details on the JAX compilation approach.

---

## Deferred Design (For Reference)

The following documents what Expr *would* be if implemented.

### Overview

Expr is a simple data structure representing a functional expression. It has a `head` (function name) and arguments. Expression trees can be parsed from strings, serialized to YAML/JSON, and evaluated.

| Property | Type | Description |
|----------|------|-------------|
| `head` | str | Function/operation name |
| `args` | Tuple[ExprArg, ...] | Positional arguments (may include nested Expr) |
| `kwargs` | Dict[str, ExprArg] | Keyword arguments (may include nested Expr) |

---

### The `_` Marker

The underscore `_` is the universal marker indicating "this is an expression, not a constant."

| Form | Expression | Constant |
|------|------------|----------|
| Dict | `_` is first key | No `_` key |
| List | `_` is first element | First element ≠ `_` |
| String | `!_` YAML tag | No tag |
| Number | — | Always constant |
| Boolean | — | Always constant |

---

### Three Representations

All three forms map to the same `Expr` structure and are interchangeable.

#### 1. Tagged String Form

Use YAML's tag syntax:

```yaml
# Evaluate immediately
k: !_ normal(0.1, 0.5)

# Preserve for later (e.g., rate expressions)
rate: !quote Vmax * S / (Km + S)
```

#### 2. Dict Form

A dictionary with `_` as the first key:

```yaml
k:
  _: normal
  mean: 0.1
  std: 0.5
```

Or inline: `{_: normal, mean: 0.1, std: 0.5}`

Keys other than `_` are keyword arguments. Positional arguments use numeric keys:

```yaml
equation:
  _: discrete
  weights: [0.4, 0.4, 0.2]
  1: {_: normal, mean: 0.1, std: 0.5}
  2: {_: lognormal, mu: 1.0, sigma: 0.3}
  3: {_: hill, Vmax: 1.0, n: 2}
```

#### 3. List Form

A list with `_` as the first element:

```yaml
k: [_, normal, 0.1, 0.5]
```

---

### Use Case: Rust Backend

If we later need a Rust-native backend that can't use JAX:

```
User writes:     "Vmax * S / (Km + S)"  (Python string)
                          ↓ Python AST parse (at sim creation)
Internal IR:     Expr(head="div", args=[Expr("mul", ...), ...])
                          ↓
Rust:            Serialize Expr tree via PyO3, interpret with SIMD
```

This keeps user experience simple (strings) while enabling native performance.

---

### Protocol (If Implemented)

```python
from typing import Any, Dict, Protocol, Tuple, Union

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
```

---

### Design Rationale (Historical)

**Why three representations were considered:**
1. **Tagged string** for concise inline expressions: `!_ normal(50, 10)`
2. **Dict form** for structured/nested cases with clear labeling
3. **List form** for programmatic construction: `[_, "normal", 50, 10]`

**Why Expr over raw Python lambdas:**
1. **Serialization**: Expr saves to YAML/JSON, lambdas cannot
2. **Inspection**: Can analyze, transform, optimize Expr trees
3. **Portability**: Compile to Rust/WASM for native runtime
4. **Safety**: Restricted operation set, no arbitrary code execution

**Why we chose strings instead:**
1. JAX compilation eliminates runtime overhead
2. Generated Python modules are human-readable
3. Simpler implementation
4. Can derive Expr as internal IR if needed later

---

## See Also

- [[Spec Evaluation]] - Current implementation using Python strings
- [[Simulator]] - JAX compilation approach
- [[Spec Language]] - YAML syntax for specs
