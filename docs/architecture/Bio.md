# Bio
**Subsystem**: [[ABIO infra]]
Utility class for fetching, hydration, and persistence of alien biology objects stored in DAT folders. For YAML syntax, see [[Spec Language]]. For the command-line interface, see [[Bio CLI]].

## Overview
Bio is a utility class with static methods—no instances. The `fetch()` method returns typed objects (Scenario, Chemistry, etc.) hydrated via the `@biotype` registry. The `store()` method dehydrates objects back to YAML.

| Method | Returns | Description |
|--------|---------|-------------|
| `fetch(bioref)` | `Any` | Fetch and hydrate object by bioref |
| `store(bioref, obj, raw=False)` | `None` | Dehydrate and store object by bioref |
| `expand(bioref)` | `dict` | Expand spec (includes, refs, defaults) without hydrating |
| `sim(scenario)` | `Simulator` | Create Simulator from a Scenario |
| `run(job)` | `Result` | Execute a job DAT |
| `hydrate(data)` | `Any` | Convert dict with `_type` to typed object (advanced) |
| `dehydrate(obj)` | `dict` | Convert typed object to dict with `_type` (advanced) |

**Note:** `hydrate()` and `dehydrate()` are advanced methods. Most users should use `fetch()` and `store()` which handle the full pipeline.

## Discussion

### Bioref Syntax
A **bioref** identifies a fetchable biological object. It uses **slashes for DAT folders** and **dots for names within a module**:

```
catalog/scenarios/mutualism        → catalog/scenarios/mutualism/spec.yaml
catalog/scenarios/mutualism.       → same (explicit index)
catalog/scenarios/mutualism.hard   → catalog/scenarios/mutualism/hard.yaml
catalog/chemistries.energy_ring    → catalog/chemistries/energy_ring.yaml (file, not folder)
```

**Rules:**
1. Slashes (`/`) navigate DAT folder hierarchy
2. Dots (`.`) after the DAT path navigate the filesystem within that DAT folder
3. If no dot suffix, load `spec.yaml` by default
4. Each dotted segment becomes a folder, final segment is `{name}.yaml`

### Scope-Aware Fetching
See [[Scope]] for details on lexical scoping and the module pattern.

```python
# Fetch specific scenario through bioref
scenario = Bio.fetch("catalog/scenarios/mutualism/experiments.baseline")

# Or load module and navigate manually
module = Bio.fetch("catalog/scenarios/mutualism", as_scope=True)
scenario = module["experiments"]["baseline"]
```

### Hydration
When fetching, Bio uses the `@biotype` registry to hydrate YAML into typed Python objects:

```yaml
# In file: spec.yaml
scenario.mutualism:
  chemistry:
    molecules: {...}
    reactions: {...}
  containers: {...}
  interface:
    actions: [add_feedstock, adjust_temp]
    measurements: [sample_substrate, population_count]
```

```python
scenario = Bio.fetch("catalog/scenarios/mutualism")
print(type(scenario))  # <class 'Scenario'>
print(scenario.chemistry.molecules)  # typed access
```

### Usage Examples

**Fetching and running a scenario:**
```python
scenario = Bio.fetch("catalog/scenarios/mutualism")
sim = Bio.sim(scenario)
while not sim.terminated:
    substrate = sim.measure("sample_substrate", "Lora")
    if substrate["ME1"] < 0.5:
        sim.action("add_feedstock", "Lora", "ME1", 2.0)
    sim.step()
result = sim.results()
```

**Storing objects:**
```python
Bio.store("catalog/scenarios/custom", my_scenario)
Bio.store("catalog/chemistries/custom", my_chemistry)
```

## Method Details

### `Bio.fetch(bioref, as_scope=False)`
Fetch and hydrate an object by bioref.

**Args:**
- `bioref`: A bioref string identifying the object (see Bioref Syntax above)
- `as_scope`: Return root Scope instead of hydrated object

**Returns:** Hydrated object, or Scope if `as_scope=True`

**Behavior:**
1. Parse bioref into DAT path and name within module
2. Load the DAT's `index.yaml`
3. Resolve includes, transform typed keys, resolve refs, expand defaults
4. Wire up scope parent chains (from `extends:` declarations)
5. If `as_scope=True`: return the root Scope
6. If name provided in bioref: navigate to that item in the scope tree
7. Otherwise: expect exactly one top-level typed object, return it hydrated
8. Hydrate based on `_type` field via `@biotype` registry

**Raises:**
- `ValueError`: If bioref has no name and module has 0 or 2+ top-level objects
- `KeyError`: If name in bioref doesn't exist in module

### `Bio.store(bioref, obj, raw=False)`
Dehydrate and store an object by bioref.

**Args:**
- `bioref`: A bioref string for storage location
- `obj`: Object to store
- `raw`: If True, write obj directly without dehydration

**Behavior:**
1. If `raw=True`, write obj directly to YAML
2. Otherwise, dehydrate object to dict (add `_type` field)
3. Write to `index.yaml` in the DAT path

### `Bio.expand(bioref)`
Expand a spec without hydrating—useful for inspection and debugging.

**Args:**
- `bioref`: A bioref string identifying the object

**Returns:** Dict with all includes resolved, refs substituted, defaults merged, but no hydration to typed objects.

### `Bio.sim(scenario)`
Create a Simulator from a Scenario.

**Args:**
- `scenario`: Scenario object to simulate

**Returns:** Configured Simulator instance

### `Bio.run(job)`
Execute a job DAT and return results.

**Args:**
- `job`: Job object to execute

**Returns:** Result object with success status and data

## Protocol
```python
class Bio:
    """Utility class for fetching, hydrating, and storing bio objects."""

    @staticmethod
    def fetch(bioref: str, as_scope: bool = False) -> Any:
        """Fetch and hydrate object by bioref."""
        ...

    @staticmethod
    def store(bioref: str, obj: Any, raw: bool = False) -> None:
        """Dehydrate and store object by bioref."""
        ...

    @staticmethod
    def expand(bioref: str) -> dict:
        """Expand spec without hydrating."""
        ...

    @staticmethod
    def sim(scenario: Scenario) -> Simulator:
        """Create Simulator from Scenario."""
        ...

    @staticmethod
    def run(job: Job) -> Result:
        """Execute a job DAT."""
        ...

    @staticmethod
    def hydrate(data: dict) -> Any:
        """Convert dict with _type to typed object."""
        ...

    @staticmethod
    def dehydrate(obj: Any) -> dict:
        """Convert typed object to dict with _type."""
        ...
```

## See Also
- [[Bio CLI]] — Command-line interface
- [[Spec Language]] — YAML syntax (`!ev`, `!ref`, `!include`, typed elements)
- [[Scope]] — Scope class for lexical scoping
- [[Decorators]] — `@biotype` for hydration registry
- [[Scenario]] — The main runnable unit
- [[ABIO DAT]] — DAT system integration
