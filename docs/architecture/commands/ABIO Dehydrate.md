 [[Architecture Docs]] → [[ABIO Commands|Commands]]

# Bio.dehydrate()

Convert an Entity back to a serializable dict.

## Synopsis

```python
from alienbio import Bio

raw: dict = Bio.dehydrate(entity: Entity)
```

## Description

Dehydration reverses hydration, converting a typed Entity back to a plain dict that can be serialized to YAML. This is the inverse of the hydration step in the processing pipeline: <span style="white-space: nowrap">name → <b>.fetch()</b> → dict → <b>.hydrate()</b> → entity → <b>.build()</b> → expanded → <b>.eval()</b> → result</span>

## Use Cases

**Export generated scenarios:**
```python
# Generate variants and save them
base = Bio.fetch("scenarios.baseline")
for rate in [0.1, 0.2, 0.5]:
    variant = base.child({"reaction_rate": rate})
    raw = Bio.dehydrate(variant)
    save_yaml(f"variant_{rate}.yaml", raw)
```

**Round-trip for testing:**
```python
raw = Bio.fetch("spec.yaml", raw=True)
entity = Bio.hydrate(raw)
restored = Bio.dehydrate(entity)
# raw == restored (structurally)
```

**Debug intermediate states:**
```python
scenario = Bio.fetch("complex.yaml")
# Inspect what hydration produced
print(Bio.dehydrate(scenario))
```

## What Gets Dehydrated

| Object | Becomes |
|--------|---------|
| `Scenario` | dict with scenario fields |
| `World` | dict with molecules, reactions, containers |
| `Scope` | dict with bindings |
| `Evaluable` | `!ev` tagged string |
| `Quoted` | `!_` tagged string |

Typed objects call their `to_spec()` method to produce the dict representation.

## See Also

- [[ABIO Hydrate|Bio.hydrate()]] — The inverse operation
- [[ABIO Fetch|Bio.fetch()]] — Load specs with `raw=True` option
- [[Spec Language Reference]] — Complete language specification
