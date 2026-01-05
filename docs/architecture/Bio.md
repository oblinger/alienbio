# Bio
**Subsystem**: Infrastructure

The Bio class provides loading, hydration, and persistence for alien biology objects stored in DAT folders. For YAML syntax, see [[Spec Language]].

## Overview

| Method | Returns | Description |
|--------|---------|-------------|
| `load(specifier, raw=False)` | `Any` | Static. Load and hydrate object by specifier |
| `save(specifier, obj)` | `None` | Static. Dehydrate and save object by specifier |
| `sim(scenario)` | `WorldSimulator` | Static. Create WorldSimulator from a Scenario |

Bio is a utility class with static methods—no instances. The `load()` method returns typed objects (Scenario, Chemistry, etc.) hydrated via the `@biotype` registry.

---

## Specifier Syntax

A specifier identifies an object in the DAT hierarchy. It uses **slashes for DAT folders** and **dots for files within a folder**:

```
catalog/scenarios/mutualism        → catalog/scenarios/mutualism/index.yaml
catalog/scenarios/mutualism.       → same (explicit index)
catalog/scenarios/mutualism.hard   → catalog/scenarios/mutualism/hard.yaml
catalog/chemistries.energy_ring    → catalog/chemistries/energy_ring.yaml (file, not folder)
```

**Rules:**
1. Slashes (`/`) navigate DAT folder hierarchy
2. Dots (`.`) after the DAT path navigate the filesystem within that DAT folder
3. If no dot suffix, load `index.yaml` by default
4. Each dotted segment becomes a folder, final segment is `{name}.yaml`

**Nested folder example:**
```
catalog/experiments.suite1.baseline
→ catalog/experiments/suite1/baseline.yaml
```

---

## Static Methods

### `Bio.load(specifier, raw=False)`

Load and hydrate an object by specifier.

```python
scenario = Bio.load("catalog/scenarios/mutualism")           # Scenario object
chemistry = Bio.load("catalog/chemistries/energy_ring")      # Chemistry object
data = Bio.load("catalog/scenarios/mutualism", raw=True)     # raw dict without hydration
```

**Behavior:**
1. Parse specifier into DAT portion and dotted suffix
2. Locate the YAML file (default: `index.yaml`)
3. Load YAML content
4. Process `include:` directives (load Python files, merge YAML)
5. If `raw=True`, return dict as-is
6. Otherwise, hydrate based on top-level `type.name:` declaration
7. Return hydrated object (Scenario, Chemistry, etc.)

### `Bio.save(specifier, obj)`

Dehydrate and save an object by specifier.

```python
Bio.save("catalog/scenarios/custom", my_scenario)            # save a Scenario
Bio.save("catalog/chemistries/custom", my_chemistry)         # save a Chemistry
Bio.save("catalog/experiments.suite1.baseline", scenario)    # specific file within folder
```

**Behavior:**
1. Dehydrate object to dict (recursively convert Python objects to YAML-serializable form)
2. Add type declaration at top (`type.name:` syntax)
3. Write to appropriate YAML file

### `Bio.sim(scenario)`

Create a WorldSimulator from a Scenario.

```python
scenario = Bio.load("catalog/scenarios/mutualism")
sim = Bio.sim(scenario)
```

---

## Hydration

When loading, Bio uses the `@biotype` registry to hydrate YAML into typed Python objects:

```yaml
# In file: mutualism.yaml
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
scenario = Bio.load("catalog/scenarios/mutualism")
print(type(scenario))  # <class 'Scenario'>
print(scenario.chemistry.molecules)  # typed access
```

The `include:` directive loads additional files during hydration:

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

### Loading and running a scenario

```python
scenario = Bio.load("catalog/scenarios/mutualism")
sim = Bio.sim(scenario)
while not sim.terminated:
    substrate = sim.measure("sample_substrate", "Lora")
    if substrate["ME1"] < 0.5:
        sim.action("add_feedstock", "Lora", "ME1", 2.0)
    sim.step()
result = sim.results()
```

### Loading individual components

```python
chemistry = Bio.load("catalog/chemistries/energy_ring")  # Chemistry object
scenario = Bio.load("catalog/scenarios/mutualism.hard")  # specific scenario variant
data = Bio.load("catalog/scenarios/mutualism", raw=True) # raw dict for inspection
```

### Saving objects

```python
Bio.save("catalog/scenarios/custom", my_scenario)
Bio.save("catalog/chemistries/custom", my_chemistry)
```

---

## See Also

- [[Spec Language]] — YAML syntax (`!ev`, `!ref`, `!include`, typed elements)
- [[Decorators]] — `@biotype` for hydration registry
- [[Scenario]] — The main runnable unit
- [[IO]] — Runtime entity references (`W:`, `R:` prefixes)
- [[ABIO Data]] — DAT folder structure
