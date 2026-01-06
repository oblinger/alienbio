# Scope
**Subsystem**: [[ABIO infra]] > Spec Language
A dict subclass with parent chain for lexical scoping. Lookups climb the chain until a value is found.

## Overview
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
| `local_keys()` | `Iterator[str]` | Keys defined in this scope only |
| `all_keys()` | `set[str]` | All keys including inherited |
| `child(data, name)` | `Scope` | Create child scope with this as parent |
| `resolve(key)` | `tuple[Any, Scope]` | Returns (value, defining_scope) |

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
    def local_keys(self) -> Iterator[str]: ...
    def all_keys(self) -> set[str]: ...
    def child(self, data: dict = None, name: str = None) -> Scope: ...
    def resolve(self, key: str) -> tuple[Any, Scope]: ...
```

## See Also
- [[Bio]] — Fetching with `as_scope=True`
- [[Spec Language]] — YAML syntax for `extends:` and `scope.X:`
