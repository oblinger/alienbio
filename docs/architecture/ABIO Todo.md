 [[Architecture Docs]]

# ABIO Todo

Working notes and design decisions. Tasks are tracked in [[ABIO Roadmap]].

---

## Open Questions

Questions to resolve before/during implementation.

### M1.5 Questions

1. **Tag class inventory**: Docs say remove `EvTag`, `RefTag`, `IncludeTag` and keep `Evaluable`, `Quoted`, `Reference`. Need to verify which classes actually exist in `tags.py` before cleanup.

2. **generator → build rename timing**: Roadmap says rename `src/alienbio/generator/` → `src/alienbio/build/`. Should this be done early in M1.5 (before other changes) or late (after consolidation)?

3. **Scenario class location**: Currently `Scenario` dataclass lives in `generator/pipeline.py`. Should it move to `protocols/` or stay where it is?

4. **Backward compatibility duration**: `Bio.generate()` is kept as alias for `_instantiate()`. How long should we maintain backward-compat aliases before removing them?

### M2 Questions

5. **Bio.run() vs Bio.fetch() routing**: I implemented simple "dots before slash" detection in `Bio.run()`. The `ABIO Fetch.md` doc shows more complex routing (absolute path, relative path, Python modules, configured roots). Should `Bio.run()` use the same routing logic as `fetch()`?

6. **Bio.lookup() scope**: Docs mention `lookup()` handles "Python modules → cwd filesystem". What's the full enumeration of lookup cases? (Marked in roadmap as "Work with user to enumerate all lookup cases")

---

## 2026-01-10  Design Decisions (Resolved)

Historical record of design decisions made during documentation review.

### Bio Class Architecture (2026-01-10)

**Decision:** Bio is a traditional class with instance methods and a null constructor. Each `Bio()` creates a fresh environment (DAT context, scope chain). A module-level singleton `bio` is used for CLI commands.

This enables sandboxing for tests while keeping CLI simple.

### Execution Pipeline (2026-01-10)

**Decision:** Separate methods with implicit chaining:
- `fetch(string)` → load + hydrate → typed object
- `build(string_or_object)` → if string, fetch first, then template instantiate
- `run(string_or_object)` → if string, build first (which fetches), then execute

Chain: `run → build → fetch` (each implicitly calls the previous if given a string)

### Hydration Architecture (2026-01-10)

**Decision:** Two-level hydration:
- `Bio.hydrate(data)` — Orchestrator that handles all phases
- `Entity.hydrate(data, ...)` — Class-specific constructor called during phase 3

Phases: (1) Resolve `!include`, (2) Resolve `!ref`, (3) Bottom-up type construction

Note: `!ev` tags stay as `Evaluable` placeholders until evaluation time.

### Tag System (2026-01-10)

**Decision:** Keep new system (Evaluable, Quoted, Reference), remove old system (EvTag, RefTag, IncludeTag).

### Context Classes (2026-01-10)

**Decision:** Use Scope instead of eval.Context. Rename infra.Context to RuntimeEnv.

### Experiment Structure (2026-01-10)

**Decision:** Experiment references a single scenario (not scenarios as an axis). `name` is a top-level field for naming child DATs, not inside axes.

```yaml
experiment.sweep:
  scenario: !ref baseline
  name: "{agent}_s{seed}"
  axes:
    agents: [claude, gpt-4]
    seeds: 10
```

---

## B9 Design Decisions (Resolved)

Earlier decisions from B9 spec language design.

### ~~Loader vs current IO~~

**Resolved:** Keep both. Spec handles filesystem/storage (specifiers like `catalog/worlds/mutualism`). IO handles runtime references within loaded data (`W:Lora.cytoplasm.glucose`). Orthogonal concerns.

### ~~World definition~~

**Resolved:** Three distinct classes:
- `WorldSpec` — declarative description from YAML
- `WorldSimulator` — execution engine
- `WorldState` — runtime snapshot

Flow: `world.name:` → WorldSpec → WorldSimulator → WorldState

### ~~Simulator class~~

**Resolved:** Use WorldSimulator. B9's "Simulator" is the same as existing WorldSimulator.

### ~~Runtime expressions~~

**Resolved:** Build Python reference simulator first, then JAX-accelerated simulator as drop-in replacement. No Rust needed—JAX compiles Python to XLA/GPU code directly. Rate functions must be pure functional for JAX tracing.

### ~~YAML custom tags~~

**Resolved:** Use three YAML tags: `!ev` (evaluate expression), `!ref` (reference constant/object), `!include` (include file). No `$` or `=` prefix syntax.

### ~~Decorator module location~~

**Resolved:** Create `alienbio/spec_lang` module containing all decorators (`@biotype`, `@fn`, `@scoring`, `@action`, `@measurement`, `@rate`) and YAML tag implementations.

### ~~Action/Measurement registration~~

**Resolved:** Global singleton registries. `@action` and `@measurement` decorators register functions at decoration time (module load). Called via `sim.action(name, ...)` and `sim.measure(name, ...)`.

### ~~Terminology alignment~~

**Resolved:**

| B9 Term | Current Code | Notes |
|---------|--------------|-------|
| `world` | `WorldSpec` | Declarative description from YAML |
| — | `WorldSimulator` | Execution engine |
| — | `WorldState` | Runtime snapshot |
| `molecules` | Molecule class | Exists |
| `reactions` | Reaction class | Exists |
| `containers` | Compartment + CompartmentTree | Exists |
| `feedstock` | — | New concept |
| `actions` | — | New (decorator-defined via `@action`) |
| `measurements` | — | New (decorator-defined via `@measurement`) |

---

## Implementation Class Naming Pattern

Source code uses `*Impl` suffix for implementation classes:

| Protocol (type hints) | Implementation (runtime) |
|----------------------|--------------------------|
| `Atom` | `AtomImpl` |
| `Molecule` | `MoleculeImpl` |
| `Reaction` | `ReactionImpl` |
| `Chemistry` | `ChemistryImpl` |
| `State` | `StateImpl` |
| `Simulator` | `SimulatorBase`, `ReferenceSimulatorImpl` |

---

## B10 Naming Conventions

From the mutualism example specification:

| Prefix | Type | Examples |
|--------|------|----------|
| M | Molecules | ME (energy), MS (structural), MW (waste), MB (buffer), MC (catalyst) |
| K | Organisms | Krel, Kova, Kesh |
| L | Locations | Lora, Lesh, Lika |
| R | Reactions | R_energy_1, R_krel_1 |

---

## See Also

- [[ABIO Roadmap]] — Task tracking by milestone
- [[Architecture Docs]] — System documentation
