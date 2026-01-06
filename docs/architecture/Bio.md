# Bio
**Subsystem**: Infrastructure

The Bio class provides fetching, hydration, and persistence for alien biology objects stored in DAT folders. For YAML syntax, see [[Spec Language]].

## Command Line Interface

The `bio` command provides direct access to Bio operations:

```bash
bio jobs/hardcoded_test              # Run a job (default action)
bio fetch catalog/scenarios/mutualism  # Fetch and display
bio expand catalog/scenarios/mutualism # Expand without hydrating
bio --help                           # Show available commands
```

**Command resolution:**
1. If first argument matches a registered command (`fetch`, `expand`, `run`, etc.), execute that command
2. Otherwise, treat argument as a job specifier and run it

This means `bio jobs/hardcoded_test` is equivalent to `bio run jobs/hardcoded_test`.

## Python API

| Method | Returns | Description |
|--------|---------|-------------|
| `fetch(specifier, raw=False)` | `Any` | Static. Fetch and hydrate object by specifier |
| `store(specifier, obj, raw=False)` | `None` | Static. Dehydrate and store object by specifier |
| `expand(specifier)` | `dict` | Static. Expand spec (includes, refs, defaults) without hydrating |
| `sim(scenario)` | `Simulator` | Static. Create Simulator from a Scenario |
| `run(job)` | `Result` | Static. Execute a job DAT |
| `hydrate(data)` | `Any` | Static. Convert dict with `_type` to typed object (advanced) |
| `dehydrate(obj)` | `dict` | Static. Convert typed object to dict with `_type` (advanced) |

Bio is a utility class with static methods—no instances. The `fetch()` method returns typed objects (Scenario, Chemistry, etc.) hydrated via the `@biotype` registry.

**Note:** `hydrate()` and `dehydrate()` are advanced methods. Most users should use `fetch()` and `store()` which handle the full pipeline.

---

## Specifier Syntax

A specifier identifies an object in the DAT hierarchy. It uses **slashes for DAT folders** and **dots for files within a folder**:

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

**Nested folder example:**
```
catalog/experiments.suite1.baseline
→ catalog/experiments/suite1/baseline.yaml
```

---

## Static Methods

### `Bio.fetch(specifier, raw=False)`

Fetch and hydrate an object by specifier.

```python
scenario = Bio.fetch("catalog/scenarios/mutualism")           # Scenario object
chemistry = Bio.fetch("catalog/chemistries/energy_ring")      # Chemistry object
data = Bio.fetch("catalog/scenarios/mutualism", raw=True)     # raw dict without processing
```

**Behavior:**
1. Parse specifier into DAT portion and dotted suffix
2. Locate the YAML file (default: `spec.yaml`)
3. Load YAML content
4. If `raw=True`, return dict as-is (no processing)
5. Otherwise: resolve includes, transform typed keys, resolve refs, expand defaults
6. Hydrate based on `_type` field via `@biotype` registry
7. Return hydrated object (Scenario, Chemistry, Job, etc.)

### `Bio.store(specifier, obj, raw=False)`

Dehydrate and store an object by specifier.

```python
Bio.store("catalog/scenarios/custom", my_scenario)            # store a Scenario
Bio.store("catalog/chemistries/custom", my_chemistry)         # store a Chemistry
Bio.store("data/results/run1", result_dict, raw=True)         # store raw dict
```

**Behavior:**
1. If `raw=True`, write obj directly to YAML
2. Otherwise, dehydrate object to dict (add `_type` field)
3. Write to `spec.yaml` in the specifier path

### `Bio.expand(specifier)`

Expand a spec without hydrating—useful for inspection and debugging.

```python
data = Bio.expand("catalog/scenarios/mutualism")
# Returns dict with all includes resolved, refs substituted, defaults merged
# but no hydration to typed objects
```

### `Bio.sim(scenario)`

Create a Simulator from a Scenario.

```python
scenario = Bio.fetch("catalog/scenarios/mutualism")
sim = Bio.sim(scenario)
```

### `Bio.run(job)`

Execute a job DAT and return results.

```python
job = Bio.fetch("jobs/hardcoded_test")
result = Bio.run(job)
```

---

## Hydration

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
  briefing: |
    You are managing an ecosystem...
```

```python
scenario = Bio.fetch("catalog/scenarios/mutualism")
print(type(scenario))  # <class 'Scenario'>
print(scenario.chemistry.molecules)  # typed access
```

The `include:` directive loads additional files during expansion:

```yaml
scenario.mutualism:
  include:
    - functions.py          # registers @action, @measurement, @rate decorators
    - base_chemistry.yaml   # merges chemistry definitions

  chemistry: !ref base_chemistry
  # ...
```

---

## Usage Examples

### Fetching and running a scenario

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

### Fetching individual components

```python
chemistry = Bio.fetch("catalog/chemistries/energy_ring")  # Chemistry object
scenario = Bio.fetch("catalog/scenarios/mutualism.hard")  # specific scenario variant
data = Bio.fetch("catalog/scenarios/mutualism", raw=True) # raw dict for inspection
```

### Running a job

```python
job = Bio.fetch("jobs/hardcoded_test")
result = Bio.run(job)
assert result.success
```

### Storing objects

```python
Bio.store("catalog/scenarios/custom", my_scenario)
Bio.store("catalog/chemistries/custom", my_chemistry)
```

---

## See Also

- [[Spec Language]] — YAML syntax (`!ev`, `!ref`, `!include`, typed elements, jobs)
- [[Decorators]] — `@biotype` for hydration registry
- [[Scenario]] — The main runnable unit
- [[ABIO DAT]] — DAT system integration
- [[IO]] — Runtime entity references (`W:`, `R:` prefixes)
- [[ABIO Data]] — DAT folder structure
