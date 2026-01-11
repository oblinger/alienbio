 [[Architecture Docs]] → [[ABIO Commands|Commands]]

# Bio.hydrate()

Transform a raw dict into a structured tree with scopes and placeholders.

## Synopsis

```python
from alienbio import Bio

entity: Entity = Bio.hydrate(raw: dict)
raw: dict = Bio.dehydrate(entity: Entity)
```

## Description

Hydration converts a raw YAML dict into a typed Entity ready for building and evaluation. It's the second stage of the processing pipeline: <span style="white-space: nowrap">name → <b>.fetch()</b> → dict → <b>.hydrate()</b> → entity → <b>.build()</b> → expanded → <b>.eval()</b> → result</span>

Hydration proceeds in three phases:

1. **Reference Resolution** — Resolve `!ref` and `!include` placeholders
2. **Scope Processing** — Build scope tree, wire parent chains via `extends:`
3. **Type Hydration** — Instantiate registered Python types

## Phases

### Phase 1: Reference Resolution

YAML parsing already converted tags to placeholder objects. Hydration resolves the structural ones:

| Placeholder | Action |
|-------------|--------|
| `Reference` (`!ref`) | Copy referenced structure into place |
| `Include` (`!include`) | Load and embed file content |
| `Evaluable` (`!ev`) | *Unchanged* — resolved at eval time |
| `Quoted` (`!_`) | *Unchanged* — preserved for later |

After this phase, all `Reference` and `Include` placeholders are gone — the structure is complete.

### Phase 2: Scope Processing

Build the scope tree from the dict structure:

1. **Create root Scope** — The top-level dict becomes the module root scope
2. **Identify typed elements** — Keys matching `type.name:` pattern are recognized
3. **Build nested scopes** — `scope.X:` elements become child Scope objects
4. **Wire parent chains** — `extends:` declarations link to parent scopes
5. **Register names** — Named elements registered in their containing scope

After this phase, all Scope objects exist with proper parent links.

### Phase 3: Type Hydration

Instantiate registered Python types:

1. For each `type.name:` element, look up the type in the registry
2. Call the type's `from_spec()` classmethod with the element's dict
3. The type creates its Python representation

After this phase, the tree contains typed Python objects (World, Scenario, etc.).

## Dehydration

`Bio.dehydrate()` reverses hydration, converting an Entity back to a serializable dict:

```python
# Round-trip
raw = Bio.fetch("spec.yaml", raw=True)
entity = Bio.hydrate(raw)
restored = Bio.dehydrate(entity)
# raw == restored (structurally)
```

**Use cases:**
- Serialize modified specs
- Export generated scenarios
- Debug intermediate states

## Examples

**Inspect hydration result:**
```python
raw = Bio.fetch("mutualism.yaml", raw=True)
scenario = Bio.hydrate(raw)

print(type(scenario))  # → Scenario
print(scenario.interface.actions)  # → ['add_feedstock', ...]
```

**Manual processing:**
```python
# Low-level control over pipeline
raw = Bio.fetch("spec.yaml", raw=True)
entity = Bio.hydrate(raw)
expanded = Bio.build(entity)
result = expanded.eval()
```

## See Also

- [[ABIO Fetch|fetch]] — Previous stage: load from source
- [[ABIO Build|build]] — Next stage: template expansion
- [[modules/Scope|Scope]] — Scope tree structure
- [[Spec Language Reference]] — Complete language specification
