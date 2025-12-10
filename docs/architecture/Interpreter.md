# Interpreter
**Subsystem**: [[ABIO infra]] > Execution
Evaluates [[Expr]] trees and handles language dispatch.

## Overview
Interpreter bridges expression representation and execution. It detects input forms (Expr, string, escape hatches), expands templates via do.load(), and evaluates or compiles expressions. The Interpreter is the single dispatch point for all expression evaluation.

| Property | Type | Description |
|----------|------|-------------|
| `do_manager` | DoManager | do-system for template lookup |
| `enable_lua` | bool | Allow `lua:` escape hatch |
| `enable_python` | bool | Allow `python:` escape hatch |
| `enable_rhai` | bool | Allow `rhai:` escape hatch |

| Method | Returns | Description |
|--------|---------|-------------|
| `eval(expr, context)` | float | Evaluate expression in context |
| `compile(expr)` | CompiledExpr | Compile to callable |
| `expand(expr)` | Expr | Expand templates without evaluating |
| `to_code(expr, language)` | str | Generate code in target language |

## Discussion

### Input Forms
The Interpreter accepts multiple input forms:

| Form | Example | Handling |
|------|---------|----------|
| Expr | `Expr("add", 1, 2)` | Evaluate directly |
| String | `"michaelis_menten(vmax=10)"` | Parse, expand, evaluate |
| Escape hatch | `"lua:return x + 1"` | Compile in target language |
| Callable | `lambda ctx: ...` | Pass through |

### Escape Hatches
Prefixed strings bypass Expr parsing and use the specified language:

```python
# Lua code
interpreter.eval("lua:return vmax * S / (km + S)", context)

# Python lambda
interpreter.eval("python:lambda ctx: ctx['vmax'] * ctx['S'] / (ctx['km'] + ctx['S'])", context)

# Rhai expression
interpreter.eval("rhai:|S, vmax, km| vmax * S / (km + S)", context)
```

### Dispatch Flow
```
interpreter.eval(input, context)
        │
        ▼ detect type
┌───────┴───────┐
│               │
callable?       string or Expr?
│               │
▼               ▼
call(context)   is string with prefix?
                │
        ┌───────┴───────┐
        │               │
        "lua:..."       no prefix
        "python:..."    │
        "rhai:..."      ▼
        │               Expr.parse() if string
        ▼               │
        compile_lang()  ▼
        │               expand templates
        ▼               │
        execute         eval_expr(expanded, context)
```

### Template Expansion
When an Expr head refers to a template, the Interpreter expands it:

```python
# Input
expr = Expr.parse("hill_equation(n=2, k=0.5)")

# 1. Look up "hill_equation" via do.load()
template_fn = do.load("hill_equation")

# 2. Call template with kwargs
expanded = template_fn(n=2, k=0.5)
# Returns full Expr tree

# 3. Recursively expand any nested templates
```

### Code Generation
The Interpreter can generate code for target languages:

```python
expr = interpreter.expand("michaelis_menten(vmax=10, km=5)")

interpreter.to_code(expr, "python")  # → "10.0 * S / (5.0 + S)"
interpreter.to_code(expr, "lua")     # → "return 10.0 * S / (5.0 + S)"
interpreter.to_code(expr, "rust")    # → "|s: f64| 10.0 * s / (5.0 + s)"
```

### Design Decisions
**Why a separate Interpreter class?**
1. **Single dispatch point**: All evaluation goes through one place
2. **Extensibility**: Easy to add new languages/backends
3. **Configurability**: Control which escape hatches are allowed
4. **Caching**: Centralized optimization

**Why escape hatches?**
Some expressions are genuinely complex (stochastic, history-dependent). The escape hatch provides full language power with clear visibility (prefix syntax) and opt-in security.

## Method Details

### `eval(expr: Interpretable, context: Dict[str, Any]) -> float`
Evaluate an expression in the given context.

**Args:**
- `expr`: Expression to evaluate (Expr, string, or callable)
- `context`: Variable bindings `{"S": 1.5, "P": 0.3, ...}`

**Returns:** Computed value

**Raises:**
- `ValueError`: If expression is invalid
- `KeyError`: If required variable not in context

**Example:**
```python
context = {"S": 2.0, "vmax": 10.0, "km": 5.0}

# Expr object
interpreter.eval(Expr("mul", 10, Expr("var", "S")), context)
# → 20.0

# String (parsed and expanded)
interpreter.eval("michaelis_menten(vmax=10, km=5)", context)
# → 2.857...

# Escape hatch
interpreter.eval("lua:return vmax * S / (km + S)", context)
# → 2.857...
```

### `compile(expr: Interpretable) -> CompiledExpr`
Compile an expression to a callable for repeated evaluation.

**Args:**
- `expr`: Expression to compile

**Returns:** Function `(context: Dict[str, float]) -> float`

**Example:**
```python
rate_fn = interpreter.compile("michaelis_menten(vmax=10, km=5)")

# Fast repeated evaluation
for s in substrate_values:
    rate = rate_fn({"S": s})
```

### `expand(expr: Interpretable) -> Expr`
Expand templates/macros without evaluating.

**Args:**
- `expr`: Expression to expand

**Returns:** Fully expanded Expr tree (no template references)

**Example:**
```python
expanded = interpreter.expand("michaelis_menten(vmax=10, km=5)")
# → Expr("mul", 10, Expr("div", Expr("var", "S"), Expr("add", 5, Expr("var", "S"))))
```

### `to_code(expr: Interpretable, language: str = "python") -> str`
Generate code in target language.

**Args:**
- `expr`: Expression to convert
- `language`: Target language (`"python"`, `"lua"`, `"rhai"`, `"rust"`)

**Returns:** Code string in target language

**Example:**
```python
interpreter.to_code("michaelis_menten(vmax=10, km=5)", "lua")
# → "return 10 * S / (5 + S)"
```

## Protocol
```python
from typing import Any, Callable, Dict, Protocol, Union
from .expr import Expr

Interpretable = Union[str, Expr, Callable]
CompiledExpr = Callable[[Dict[str, float]], float]


class Interpreter(Protocol):
    """Evaluates expressions in various forms."""

    def eval(
        self,
        expr: Interpretable,
        context: Dict[str, Any],
    ) -> float:
        """Evaluate an expression in the given context."""
        ...

    def compile(
        self,
        expr: Interpretable,
    ) -> CompiledExpr:
        """Compile an expression to a callable."""
        ...

    def expand(
        self,
        expr: Interpretable,
    ) -> Expr:
        """Expand templates/macros without evaluating."""
        ...

    def to_code(
        self,
        expr: Interpretable,
        language: str = "python",
    ) -> str:
        """Generate code in target language."""
        ...
```

## See Also
- [[Expr]] - Expression tree representation
- [[IO]] - do.load for template resolution
- [[Flow]] - Uses Interpreter for rate equations
- [[Reaction]] - Uses Interpreter for rate equations
- [[WorldSimulator]] - Uses Interpreter during simulation
