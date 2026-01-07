# Spec Evaluation
**Subsystem**: [[ABIO infra]] > Entities
Evaluation semantics for spec processing: hydrate, eval, dehydrate.

## Overview

Spec Evaluation defines how specs are processed. It uses Lisp-style semantics with a unified traversal that handles both macros and functions. The key insight is that evaluation operates like being inside a Lisp backquote: structure is implicitly "quoted" (returned as-is), and tagged expressions are the "unquote" points that trigger evaluation.

**All expressions are Python strings.** See [[Expr]] for the deferred structured format.

**Related**: [[Spec Language]] defines syntax; this document defines semantics.

---

## Execution Model

### Processing Pipeline

```
YAML  →.fetch→  dict_tree  →.hydrate→  object_tree  →.macro_expand→  expanded_tree  →.eval→  result
```

| Stage | Form | Description |
|-------|------|-------------|
| YAML | text | Raw spec file on disk |
| dict tree | nested dicts/lists | After YAML parse, types and tags are plain data |
| hydrated | Python objects | Dicts replaced with typed instances; tags become placeholder objects |
| macro expanded | expanded objects | Macros expanded, quoted expressions preserved |
| evaluated | concrete values | Functions executed, final result |

### Core Operations

| Operation | Input | Output | Description |
|-----------|-------|--------|-------------|
| `hydrate` | YAML/dict structure | Python object tree | Instantiate typed objects; convert tags to placeholders |
| `dehydrate` | Python object tree | YAML/dict structure | Convert back to serializable form |
| `macro_expand` | Object tree | Expanded tree | Expand macros only, preserve functions and quotes |
| `eval` | Object tree | Concrete values | Full evaluation: macros + functions |

These operations are available on the [[Bio]] class:
- `Bio.hydrate(data)` - Instantiate Python objects from dicts; resolve `!include`; convert tags to placeholders
- `Bio.dehydrate(data)` - Convert back to serializable form
- `Bio.macro_expand(node, ctx)` - Expand macros only (debugging/dry-run; not used in normal flow)
- `Bio.eval(node, ctx)` - Full evaluation (macros + functions)

**Note**: `macro_expand` is primarily for debugging. Normal execution uses `eval` directly, which handles both macros and functions in a single pass.

---

## Expression Tags

### `!_` — Evaluate Python Expression

The `!_` tag evaluates a Python expression immediately:

```yaml
# Evaluate at load time
count: !_ normal(50, 10)
area: !_ pi * radius * radius
clamped: !_ max(0, min(value, 100))

# Conditionals work too
ratio: !_ x / y if y != 0 else 0
```

**Evaluation**: Python `eval()` with lexical bindings from context. Registered `@function` handlers are available in the namespace.

### `!quote` — Preserve Expression as String

The `!quote` tag preserves an expression without evaluating it. The expression string is returned as-is:

```yaml
reaction.glycolysis:
  substrates: [Glucose, ATP]
  products: [G6P, ADP]
  rate: !quote k * S1 * S2   # Preserved as string "k * S1 * S2"

reaction.michaelis:
  substrates: [S]
  products: [P]
  rate: !quote Vmax * S / (Km + S)   # Preserved for simulator compilation
```

**Use cases:**
- Rate expressions that need to be compiled at simulator creation time
- Any expression you want to preserve for later processing
- Template expressions that will be evaluated in a different context

### `!ref` — Reference Named Value

The `!ref` tag references a named constant or object:

```yaml
high_permeability: 0.8
standard_diffusion: {default: 0.1, membrane: 0.01}

scenario.example:
  permeability: !ref high_permeability     # → 0.8
  diffusion: !ref standard_diffusion       # → the entire dict
```

### `!include` — Include File Content

The `!include` tag includes external file content:

```yaml
scenario.example:
  constitution: !include safety.md
```

---

## Tag Summary

| Tag | Behavior | Returns | Use Case |
|-----|----------|---------|----------|
| `!_` | Evaluate Python expression | Computed value | Immediate computation |
| `!quote` | Preserve expression unchanged | The expression (for later compilation) | Rate expressions, templates |
| `!ref` | Lookup named value | Referenced value | Constants, reusable structures |
| `!include` | Include file | File contents as string | External documents |

---

## Hydrate Phase

The `hydrate` operation transforms raw YAML/dict structure into a tree of Python objects. **The primary purpose is type instantiation** — replacing dict specifications with typed Python instances based on their `_type` field or registered biotypes.

**What hydration does:**
1. **Type instantiation**: Dicts with type markers (e.g., `scenario.name:` syntax or `_type` field) become Python class instances
2. **Tag conversion**: YAML tags (`!_`, `!quote`, `!ref`) become placeholder objects (Evaluable, Quoted, Reference)
3. **File inclusion**: `!include` tags are resolved — file contents read and inserted
4. **Recursive descent**: Children are hydrated recursively

**`!include` is resolved during hydration** — file contents are read and inserted before any evaluation happens. This keeps the pipeline simple: hydration handles all file I/O.

**Process:**
1. If dict has type marker → instantiate appropriate Python class, hydrate its fields
2. If value has `!include` tag → read file, insert contents
3. If value has `!_` tag → create Evaluable placeholder
4. If value has `!quote` tag → create Quoted placeholder
5. If value has `!ref` tag → create Reference placeholder
6. Otherwise → keep as constant, recursively hydrate children

**Example:**

```yaml
scenario.test:
  molecules:
    count: !_ normal(50, 10)
  reactions:
    rate: !quote Vmax * S / (Km + S)
  constants:
    timeout: 30
```

```python
# After hydrate
Scenario(
  name="test",
  molecules={
    "count": Evaluable(source="normal(50, 10)")
  },
  reactions={
    "rate": Quoted(source="Vmax * S / (Km + S)")
  },
  constants={
    "timeout": 30  # constant, unchanged
  }
)
```

---

## Dehydrate Phase

The `dehydrate` operation converts Python objects back to their serializable dict/YAML form:

```python
# Hydrated (in-memory)
Scenario(
  name="test",
  reactions={"rate": Quoted(source="Vmax * S / (Km + S)")}
)

# Dehydrated (serializable)
{
  "_type": "scenario",
  "name": "test",
  "reactions": {"rate": {"!quote": "Vmax * S / (Km + S)"}}
}
```

This enables round-trip serialization: `dehydrate(hydrate(data))` produces equivalent structure.

---

## Eval Phase

Evaluation handles each node type appropriately:

```python
def eval(node, ctx, strict=True):
    if is_constant(node):
        return node

    if isinstance(node, Evaluable):
        # Build namespace: lexical bindings + registered functions
        namespace = {**ctx.bindings, **ctx.functions}
        return python_eval(node.source, {"__builtins__": SAFE_BUILTINS}, namespace)

    if isinstance(node, Quoted):
        # Preserve the expression unchanged (for later compilation)
        return node.source

    if isinstance(node, Reference):
        if node.name not in ctx.bindings:
            if strict:
                raise EvalError(f"Unknown reference: {node.name}")
            return node
        return ctx.bindings[node.name]

    if isinstance(node, dict):
        return {k: eval(v, ctx, strict) for k, v in node.items()}

    if isinstance(node, list):
        return [eval(x, ctx, strict) for x in node]

    return node
```

**Key points:**
- `!_` expressions are evaluated with Python `eval()`
- `!quote` expressions are preserved unchanged (for later compilation, e.g., rate equations)
- Registered `@function` handlers are available in the eval namespace
- `SAFE_BUILTINS` includes math functions (`min`, `max`, `abs`, etc.)

---

## Macros vs Functions

### @function Decorator

Functions are registered and available in `!_` expressions:

```python
@function
def normal(mean: float, std: float, ctx: Context) -> float:
    """Sample from Gaussian distribution."""
    return ctx.rng.normal(mean, std)

@function
def discrete(weights: list, *choices, ctx: Context):
    """Weighted random choice."""
    return ctx.rng.choice(choices, p=weights)
```

Usage:
```yaml
count: !_ normal(50, 10)
type: !_ discrete([0.3, 0.7], "energy", "structural")
```

**Context injection**: The `@function` decorator wraps functions so that `ctx` is automatically injected. When the user writes `!_ normal(50, 10)`, the evaluator calls `normal(50, 10, ctx=ctx)` behind the scenes. Function authors declare `ctx: Context` as their last parameter.

### @macro Decorator

Macros control structure expansion. They receive unevaluated structure:

```python
@macro
def reaction(args, kwargs, ctx):
    """Create reaction object."""
    return Reaction(
        substrates=kwargs['substrates'],
        products=kwargs['products'],
        rate=kwargs['rate'],  # Already a string if !quote was used
    )
```

Note: With `!quote`, macros don't need special logic to preserve rate expressions. The author explicitly marks what should be preserved.

---

## Backquote Semantics

Spec evaluation is like operating inside a Lisp backquote: structure is implicitly "quoted" (returned as-is), and `!_` tags are like comma/unquote (evaluated).

```yaml
world:
  name: "test"
  population: !_ normal(100, 20)
  area: !_ pi * radius * radius
  rate_template: !quote k * S
  config:
    timeout: 30
```

During evaluation:
- `name: "test"` → returned as `"test"` (constant)
- `population: !_ normal(100, 20)` → calls `normal`, returns sampled number
- `area: !_ pi * radius * radius` → Python eval, returns computed value
- `rate_template: !quote k * S` → returns string `"k * S"` (preserved)
- `config: {timeout: 30}` → returned as dict (constant structure)

---

## Context Object

The context object (`ctx`) carries evaluation state:

| Property | Description |
|----------|-------------|
| `rng` | Random number generator (seeded for reproducibility) |
| `bindings` | Variable bindings (constants from spec + lexical scope) |
| `functions` | Registered `@function` handlers |
| `path` | Current path in tree (for error messages) |

**Lexical bindings** come from:
- Constants defined in the spec
- Values from parent scopes (lexical inheritance)

```yaml
# Constants available as bindings
pi: 3.14159
radius: 10

scenario:
  area: !_ pi * radius * radius  # evaluates to ~314.159
```

---

## Built-in Functions

### Distribution Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `normal` | `normal(mean, std)` | Gaussian distribution |
| `uniform` | `uniform(min, max)` | Uniform over range |
| `lognormal` | `lognormal(mu, sigma)` | Log-normal distribution |
| `poisson` | `poisson(lambda)` | Poisson (count data) |
| `exponential` | `exponential(lambda)` | Exponential distribution |
| `discrete` | `discrete(weights, *choices)` | Weighted discrete choice |
| `choice` | `choice(*choices)` | Uniform discrete choice |

For arithmetic and logic, use Python directly:
```yaml
total: !_ a + b + c
ratio: !_ x / y if y != 0 else 0
clamped: !_ max(0, min(value, 100))
```

See **Default Namespace** section below for full list of available builtins.

---

## Multiple Scenario Instantiations

A key use case is generating multiple random instantiations of the same scenario spec. The separation between `eval` and `Bio.sim` enables this:

```python
spec = Bio.load("ecosystem.yaml")  # Returns hydrated, unevaluated spec

for seed in range(10):
    ctx = Context(rng=np.random.default_rng(seed))
    scenario = Bio.eval(spec, ctx)   # Each eval samples different random values
    sim = Bio.sim(scenario)          # Compile to simulator
    result = sim.run(steps=1000)     # Run simulation
    save_result(seed, result)
```

**Key insight**: `Bio.eval` produces a **Scenario object** with all `!_` expressions evaluated (random samples taken). `Bio.sim` creates a **Simulator** (compiles rate expressions). `sim.run` actually executes the simulation. These are separate steps, allowing multiple instantiations from the same spec.

---

## Default Namespace

The evaluation namespace includes:

**Guaranteed builtins:**
```python
DEFAULT_BUILTINS = {
    'min', 'max', 'abs', 'round', 'sum', 'len',
    'int', 'float', 'str', 'bool',
    'list', 'dict', 'tuple', 'set',
    'range', 'zip', 'enumerate', 'sorted', 'reversed',
}
```

**Registered `@function` handlers** (distributions, etc.)

**User-defined bindings** from spec constants and `!include` of Python modules.

Users can extend the namespace by including Python modules that define additional functions:
```yaml
# In spec
utils: !include my_utils.py  # Adds functions to namespace
```

---

## Design Rationale

**Why `!_` and `!quote`?**
1. **Explicit intent**: Author marks what should be evaluated vs preserved
2. **No macro magic**: Macros don't need special knowledge about fields
3. **Lisp semantics**: Mirrors unquote (`!_`) and quote (`!quote`) from Lisp
4. **Flexible**: Can use `!quote` anywhere, not just rate fields

**Why Python strings instead of structured Expr trees?**
1. **JAX compilation**: At simulator creation, we generate a Python module that JAX traces
2. **Simpler**: Strings are readable, familiar. No parallel interpreters needed.
3. **Inspectable**: Generated Python modules are human-readable for debugging.

See [[Expr]] for the deferred structured format and [[Simulator]] for JAX compilation.

**Why lexical bindings?**
1. Variables resolve from spec scope naturally
2. Constants defined once, used throughout
3. Matches how Python programmers expect scoping to work

---

## See Also

- [[Spec Language]] - Syntax for writing specs
- [[Expr]] - Deferred structured expression format
- [[Simulator]] - Rate expression compilation with JAX
- [[Bio]] - High-level API exposing hydrate/dehydrate/eval
