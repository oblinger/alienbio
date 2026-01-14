 [[Architecture Docs]]

# Spec Language Reference

Comprehensive specification of the YAML-based spec language used throughout alienbio.

---

## Implementation Notes

**READ THIS FIRST** if implementing or refactoring the spec language.

### Tag System Consolidation (M1.5)

The current code has two tag systems. Remove the old one:

**Remove (old system):**
- `EvTag`, `RefTag`, `IncludeTag` classes in `tags.py`

**Keep (new system):**
- `Evaluable` — placeholder for `!ev`, resolved at eval time
- `Quoted` — placeholder for `!_`, preserved as string for later
- `Reference` — placeholder for `!ref`, resolved during hydration

The YAML constructors in `tags.py` should create the new placeholder classes, not the old Tag classes.

### Context Class Consolidation (M1.5)

Two Context classes exist:
- `eval.Context` — dataclass with `rng`, `bindings`, `functions`, `path`
- `infra.Context` — runtime environment with `config`, `io`

**Target:**
- Remove `eval.Context`
- Use `Scope` for evaluation context (bindings/functions are scope entries)
- Rename `infra.Context` → `RuntimeEnv` to avoid confusion

### Hydration Phases

`Bio.hydrate()` should orchestrate three phases in order:

1. **Resolve `!include`** — Load external files, embed content
2. **Resolve `!ref`** — Substitute references with values (supports dotted paths)
3. **Type construction** — Bottom-up, call `Entity.hydrate()` on each `_type` node

Note: `!ev` stays as `Evaluable` placeholder until `eval()` is called separately.

See [[ABIO Roadmap#M1.5 — Refactoring & Cleanup]] for full task list.

---

## Execution Pipeline

<div style="text-align: center; font-size: 1.1em">name → <b>.fetch()</b> → dict → <b>.hydrate()</b> → tree → <b>.build()</b> → expanded → <b>.eval()</b> → result</div>

| Method | Input | Output | What Happens |
|--------|-------|--------|--------------|
| **.fetch()** | spec name | dict | Load data structure from source tree |
| **.hydrate()** | dict | tree | Resolve `!ref` and `!include`, convert tags to placeholders |
| **.build()** | tree | expanded | Template expansion |
| **.eval()** | expanded | result | Execute expressions with runtime context |

---

## YAML Tags

All tags use standard YAML syntax:

| Tag | Resolved At | Description |
|-----|-------------|-------------|
| `!ref` | Hydration | Copy referenced structure into place |
| `!include` | Hydration | Include external file content |
| `!ev` | Eval | Evaluate expression with context |
| `!_` | Later | Preserve as string for contextual evaluation |

### `!ref` — Structural Reference

Copy a chunk of YAML structure into place. Resolved at hydration time, before template expansion.

```yaml
standard_interface:
  actions: [add_feedstock, adjust_temp]
  measurements: [sample_substrate, population_count]

scenario.example:
  interface: !ref standard_interface    # copies the structure here
```

After hydration: the `interface` key contains a copy of the structure.

**Key points:**
- Fully resolved at hydration — no placeholder survives
- Copies the structure — result is still a tree, not a graph
- Two references to the same thing = two independent copies

### `!include` — Include File

Include external file content. Fully resolved at hydration — no placeholder survives.

```yaml
constitution: !include safety.md           # markdown file as string
defaults: !include shared/defaults.yaml    # YAML file merged in
```

### `!ev` — Evaluate Expression

Execute at eval time. Use for values that need runtime computation. Survives hydration as an `Evaluable` placeholder.

```yaml
count: !ev normal(50, 10)      # sampled at eval time
temp: !ev uniform(20, 30)      # random value in range
computed: !ev len(items) * 2   # expression using context
```

After eval: `47.3`

### `!_` — Quoted Expression

Preserve as string for later contextual evaluation. Use for "code" that runs later (rate equations, scoring functions). Survives hydration as a `Quoted` placeholder.

```yaml
rate: !_ k * S / (Km + S)           # Michaelis-Menten, compiled at simulation time
score: !_ trace.final['C'] / 10.0   # scoring, evaluated with trace in context
```

After eval: `"k * S / (Km + S)"` (string preserved for later contextual evaluation)

**Use `!_` when:**
- The expression depends on runtime context (simulation state, trace)
- You want to defer evaluation until the right context exists

---

## Hydration Phases

Hydration (`.hydrate()`) transforms a parsed YAML structure into a typed Entity. It proceeds in three phases:

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

1. Create root `Scope` from the top-level dict
2. Identify typed elements (`type.name:` keys) and nested scopes
3. Wire up parent chains via `extends:` declarations
4. Register named elements in their containing scope

After this phase, all Scope objects exist with proper parent links.

### Phase 3: Type Hydration

Instantiate registered Python types:

1. For each `type.name:` element, look up the type in the registry
2. Call the type's `from_spec()` classmethod with the element's dict
3. The type creates its Python representation

After this phase, the tree contains typed Python objects (World, Scenario, etc.) ready for `.build()` and `.eval()`.

---

## Scope

**Top-level YAML is a scope.** Every spec file defines a scope — a hierarchical namespace where names are resolved. Lookup climbs the parent chain until the name is found.

```yaml
high_permeability: 0.8              # plain value in scope

world.ecosystem:                     # typed object in scope
  molecules: ...

scenario.base:                       # another typed object
  extends: ecosystem
  interface: ...
```

See [Scope](modules/Scope.md) for full details on scope chains, typed elements, and inheritance.

---

## Evaluation

**Evaluation requires lookup in a scope.**

Expressions are never evaluated in a vacuum — there's always a scope providing the namespace for variable lookup:

| Expression Type | Scope | Variables Available |
|-----------------|-------|---------------------|
| Initial values (`!ev`) | Eval scope | `functions`, `rng` |
| Rate equations (`!_`) | Simulation state | `k`, `S`, `Km`, concentrations |
| Scoring functions (`!_`) | Simulation trace | `trace`, `final`, `timeline` |

### Function Injection

Functions in the scope's function registry can receive the scope automatically:

```python
def normal(mean, std, *, scope):
    return scope.rng.normal(mean, std)
```

When called from a `!ev` expression, `scope` is auto-injected — the expression author just writes `normal(50, 10)`.

---

## Built-in Functions

See [[Builtins]] for the complete list of distribution functions and safe Python builtins available in expressions.

---

## When Things Happen

| Content | Tag | When | Scope |
|---------|-----|------|-------|
| Structure references | `!ref` | Hydration | — (copies structure) |
| File includes | `!include` | Hydration | — (embeds content) |
| Initial values | `!ev` | Eval | Eval scope |
| Rate equations | `!_` | Simulation step | State |
| Scoring functions | `!_` | After simulation | Trace |

**Why this matters:**
- `!ref` must be resolved before template expansion (`.build()`) so the full structure is available
- `!ev` computes values when the spec is instantiated
- `!_` preserves expressions for later — when the right scope (state, trace) exists

---

## Typed Elements

Use `type.name:` syntax to declare typed objects:

```yaml
world.ecosystem:
  molecules: ...

scenario.mutualism:
  extends: ecosystem
  interface: ...
```

The first segment is looked up in the type registry. Built-in types include `world`, `scenario`, `scope`, and `experiment`. Custom types are registered via `@biotype`.

See [Scope](modules/Scope.md) for details on typed elements, subscopes, and the `@biotype` registry.

---

## Inheritance

The `extends:` keyword declares inheritance by wiring up the scope parent chain:

```yaml
scenario.base:
  interface: ...

scenario.variant:
  extends: base
  briefing: "Modified version"   # adds to base
```

Child values override parent values; lookup climbs the chain until found.

See [Scope](modules/Scope.md) for full details on scope chains and inheritance.

---

## See Also

- [[Core Spec]] — User guide introduction to spec syntax
- [Scope](modules/Scope.md) — Hierarchical namespace resolution
- [[Builtins]] — Distribution functions and safe Python builtins
- [Scenario](commands/ABIO Scenario.md) — Scenario spec format
