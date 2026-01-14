[[Architecture Docs]] → [[ABIO Modules|Modules]]

# Scope

A dict subclass with parent chain for lexical scoping. Lookups climb the chain until a value is found.

## Overview

**Top-level YAML is a scope.** Every spec file defines a scope — a hierarchical namespace where names are resolved. Scopes are the fundamental organizing structure for all spec content.

Scope enables lexical scoping in spec files. A YAML file is loaded as a tree of Scope objects, where each typed element (`world.X`, `scenario.X`, `scope.X`) becomes a Scope with a parent link established via `extends:`. Variable lookups climb the parent chain, enabling inheritance without copying values.

| Property | Type | Description |
|----------|------|-------------|
| `parent` | `Scope \| None` | Parent scope for inheritance chain |
| `name` | `str \| None` | Optional name for debugging |

| Method | Returns | Description |
|--------|---------|-------------|
| `scope[key]` | `Any` | Get value, climbing parent chain |
| `get(key, default)` | `Any` | Get with default, climbing chain |
| `key in scope` | `bool` | Check if key exists in chain |
| `lookup(dotted_name)` | `Any` | Resolve dotted name through scope tree → Bio fallback |
| `local_keys()` | `Iterator[str]` | Keys defined in this scope only |
| `all_keys()` | `set[str]` | All keys including inherited |
| `child(data, name)` | `Scope` | Create child scope with this as parent |
| `resolve(key)` | `tuple[Any, Scope]` | Returns (value, defining_scope) |
| `eval(expr)` | `Any` | Evaluate expression in this scope's context |

## Discussion

### Lexical Scoping
Scope implements lexical (static) scoping—the parent chain is established at load time based on `extends:` declarations, but variable lookups are dynamic. When you access `scope["key"]`, it checks the local dict first, then climbs to parent, grandparent, etc.

```python
root = Scope({"x": 1, "y": 2}, name="root")
child = Scope({"y": 3, "z": 4}, parent=root, name="child")

child["x"]  # → 1 (from root)
child["y"]  # → 3 (overridden in child)
child["z"]  # → 4 (defined in child)
```

### Dotted Name Lookup

The `lookup(dotted_name)` method resolves dotted names through a layered search:

1. **Walk scope tree** — Look for first segment in current scope → parent → ... → root
2. **If found in scope** — Dereference remaining segments from that object
3. **If not found** — Fall back to [Bio.lookup()](../commands/ABIO Lookup.md)

```python
# Local scope lookup
scope.lookup("chemistry.molecules.ME1")
# → Find "chemistry" in scope tree, dereference .molecules.ME1

# Falls back to Bio.lookup() when not in scope
scope.lookup("alienbio.bio.Chemistry")
# → Not in scope tree → Bio.lookup() → Python module
```

**Key points:**
- Local/inherited names shadow global names
- Scope tree is checked first, then Bio.lookup() as fallback
- `eval()` uses `lookup()` to resolve variable names in expressions

See [Bio.lookup()](../commands/ABIO Lookup.md) for the global resolution order (Python modules → cwd filesystem).

### In Spec Files
Every typed element becomes a Scope. The `extends:` keyword wires up the parent chain:

```yaml
world.mutualism:
  molecules: ...

scenario.base:
  extends: mutualism    # parent is world.mutualism
  interface: ...

scope.experiments:
  extends: base         # parent is scenario.base

  scenario.baseline:    # parent is scope.experiments
    briefing: "..."
```

**Scope chain:** `baseline` → `experiments` → `base` → `mutualism` → module root

### How Hydration Builds Scopes

During `.hydrate()`, scope processing occurs in Phase 2 (after reference resolution, before type hydration):

1. **Create root Scope** — The top-level dict becomes the module root scope
2. **Identify typed elements** — Keys matching `type.name:` pattern are recognized
3. **Build nested scopes** — `scope.X:` elements become child Scope objects
4. **Wire parent chains** — `extends:` declarations link to parent scopes
5. **Register names** — Named elements registered in their containing scope

```yaml
# During hydration:
world.ecosystem:        # → Scope(parent=module_root)
  molecules: ...

scenario.base:          # → Scope(parent=ecosystem, via extends)
  extends: ecosystem

scope.experiments:      # → Scope(parent=base, via extends)
  extends: base
  scenario.baseline:    # → Scope(parent=experiments, automatic)
```

After hydration, the scope tree exists with all parent links wired up. Type hydration (Phase 3) then instantiates the actual Python objects within these scopes.

See [[Spec Language Reference#Hydration Phases]] for the complete hydration pipeline.

### Bio.fetch() Integration
- `Bio.fetch(path)` — Expects one top-level typed object, returns it hydrated
- `Bio.fetch(path, "name")` — Fetches specific item by navigating scope tree
- `Bio.fetch(path, as_scope=True)` — Returns entire file as root Scope

```python
# Fetch specific scenario through scope path
scenario = Bio.fetch("mutualism.yaml", "experiments.baseline")

# Or navigate manually
module = Bio.fetch("mutualism.yaml", as_scope=True)
scenario = module["experiments"]["baseline"]
```

### Runtime Instantiation
When a Simulator is created, all values are resolved and copied—the Simulator doesn't do scope lookups. This means:
- Efficient simulation (no chain climbing)
- Scope objects can be reused for hyperparameter sweeps

```python
module = Bio.fetch("mutualism.yaml", as_scope=True)
base = module["base"]

for k in [0.1, 0.2, 0.5]:
    variant = base.child({"reaction_rate": k})
    sim = Bio.sim(module["experiments"]["baseline"])
    sim.run()
```

## Method Details

### `__getitem__(key: str) -> Any`
Get value by key, climbing parent chain if not found locally.

**Raises:**
- `KeyError`: If key not found in any scope in the chain

### `resolve(key: str) -> tuple[Any, Scope]`
Resolve a key and return both the value and the scope that defined it. Useful for debugging inheritance.

**Example:**
```python
value, defining_scope = child.resolve("x")
print(f"{value} defined in {defining_scope.name}")
```

### `child(data: dict = None, name: str = None) -> Scope`
Create a new Scope with this scope as parent.

**Example:**
```python
parent = Scope({"x": 1})
child = parent.child({"y": 2}, name="child")
```

### `lookup(dotted_name: str) -> Any`
Resolve a dotted name through the scope tree, falling back to [Bio.lookup()](../commands/ABIO Lookup.md).

**Resolution order:**
1. Walk scope tree for first segment (current → parent → ... → root)
2. If found, dereference remaining segments from that object
3. If not found, delegate to `Bio.lookup()` (Python modules → cwd filesystem)

**Examples:**
```python
# Local scope lookup
scope["chemistry"] = my_chemistry
scope.lookup("chemistry.molecules.ME1")  # → ME1 from local chemistry

# Falls back to Bio.lookup()
scope.lookup("alienbio.bio.Chemistry")   # → Chemistry class (via Bio.lookup)
```

See [Bio.lookup()](../commands/ABIO Lookup.md) for global resolution details.

### `eval(expr: str) -> Any`
Evaluate an expression in this scope's context. Uses `lookup()` to resolve variable names.

**The scope provides:**
- Variable bindings via `lookup()` (scope tree → Bio fallback)
- Function registry (built-in functions like `normal`, `uniform`)
- Random number generator (for stochastic functions)

**Example:**
```python
scope = Bio.fetch("spec.yaml", as_scope=True)

# Evaluate expression with scope's bindings
result = scope.eval("normal(50, 10)")

# Variables from scope are available
scope["rate"] = 0.5
result = scope.eval("rate * 2")  # → 1.0

# Can reference Python objects via lookup
result = scope.eval("alienbio.bio.Chemistry")  # → Chemistry class
```

**Use cases:**
- Evaluate `!ev` placeholders during spec processing
- Compute derived values from spec variables
- Reference Python classes/functions in expressions
- Interactive exploration of spec state

## Protocol
```python
class Scope(dict):
    """A dict with lexical scoping (parent chain lookup)."""

    parent: Scope | None
    name: str | None

    def __init__(
        self,
        data: dict[str, Any] | None = None,
        parent: Scope | None = None,
        name: str | None = None,
    ): ...

    def __getitem__(self, key: str) -> Any: ...
    def get(self, key: str, default: Any = None) -> Any: ...
    def __contains__(self, key: object) -> bool: ...
    def lookup(self, dotted_name: str) -> Any: ...
    def local_keys(self) -> Iterator[str]: ...
    def all_keys(self) -> set[str]: ...
    def child(self, data: dict = None, name: str = None) -> Scope: ...
    def resolve(self, key: str) -> tuple[Any, Scope]: ...
    def eval(self, expr: str) -> Any: ...
```

## See Also
- [[Bio (module)|Bio]] — Fetching with `as_scope=True`
- [[Spec Language Reference]] — YAML syntax, hydration phases, evaluation
- [[Core Spec]] — User guide introduction to scope and inheritance
