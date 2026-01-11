 [[Architecture Docs]]

# ABIO Roadmap

Milestones organized for incremental, testable implementation.

---

## M1 — Core Biology (Complete)

Core biology classes implemented and working.

- [x] Molecule, Reaction, Chemistry classes
- [x] State and Simulator classes
- [x] Basic YAML loading
- [x] Spec language tags (`!ev`, `!ref`, `!include`)
- [x] Function decorators (`@biotype`, `@scoring`, `@action`, `@measurement`, `@rate`)

### Modules Reviewed and Consistent

These modules have been reviewed and match documentation:

- `spec_lang/scope.py` — Scope class
- `spec_lang/builtins.py` — Distribution functions
- `generator/template.py` — TemplateRegistry, parse_template, parse_port
- `generator/expand.py` — apply_template with namespace prefixing
- `generator/guards.py` — @guard decorator
- `generator/visibility.py` — generate_visibility_mapping, apply_visibility
- `generator/pipeline.py` — instantiate(), Scenario dataclass
- `commands/__init__.py` — COMMANDS registry
- `protocols/*.py` — Protocol definitions

---

## M1.5 — Refactoring & Cleanup

Clean up technical debt before building new features. All items reference existing code.

**Key docs with implementation notes:**
- [[classes/infra/Bio|Bio.md]] — Bio class refactoring steps, hydration consolidation
- [[Spec Language Reference]] — Tag system consolidation, Context class cleanup

### Code Refactoring

1. **Bio class: instance pattern**
   - [ ] Refactor `_BioCompat` static wrappers to delegate to singleton
   - [ ] Ensure `Bio.__init__()` creates fresh DAT context and scope chain
   - [ ] Export `bio` singleton from `alienbio.__init__`
   - [ ] Update CLI commands to use singleton `bio` instance

2. **Consolidate hydration**
   - [ ] Remove or deprecate `eval.hydrate()`
   - [ ] Consolidate `decorators.hydrate()` logic into `Bio.hydrate()`
   - [ ] Ensure each Entity subclass has `hydrate(data, ...)` classmethod

3. **Remove old tag system**
   - [ ] Remove `EvTag`, `RefTag`, `IncludeTag` classes from `tags.py`
   - [ ] Keep YAML constructors but have them create new placeholder classes (Evaluable, Quoted, Reference)
   - [ ] Add dotted path support to Reference resolution
   - [ ] Ensure circular include detection in `Bio.hydrate()`

4. **Context class disambiguation**
   - [ ] Remove `eval.Context` dataclass
   - [ ] Update `eval_node()` to take Scope instead of Context
   - [ ] Rename `infra.Context` → `RuntimeEnv`
   - [ ] Update all references

5. **Rename generator → build**
   - [ ] Rename `src/alienbio/generator/` → `src/alienbio/build/`
   - [ ] Update all imports

6. **Remove loader stub**
   - [ ] Remove `loader.py` stub `load_spec()`

### Documentation Updates (for existing code)

- [ ] Document `Entity.ancestors()`, `descendants()`, `local_name`, `parent`, `children`
- [ ] Document `IO.orphan_root`, `resolve_prefix()`, `unbind_prefix()`, `resolve_refs()`, `insert_refs()`, `load()`, `save()`
- [ ] Document `MoleculeImpl`, `ReactionImpl`, `ChemistryImpl` and hydrate methods
- [ ] Document `@fn`, `@scoring`, `@action`, `@measurement`, `@rate` decorator parameters
- [ ] Document `FnMeta` class and registry access functions
- [ ] Document `!quote` tag alias for `!_`
- [ ] Document `EvalError` exception
- [ ] Document `IncludeTag` .py file execution (security note)
- [ ] Clarify Protocol vs `*Impl` naming pattern

---

## M2 — Bio Fetch & Lookup

Bio class methods for loading and navigating specs. Testable independently.

**Key docs with implementation notes:**
- [[commands/ABIO Fetch|Fetch]] — Specifier routing logic, hydration order

### Code

1. **Bio.cd()**
   - [ ] Add `_current_dat: Path | None` instance variable
   - [ ] Add `cd(path=None)` method
   - [ ] Update `fetch()`, `store()` to resolve relative paths against current DAT
   - [ ] CLI: `bio cd` prints current, `bio cd path` changes it

2. **Bio.lookup()**
   - [ ] Create `lookup(dotted_name)` function
   - [ ] Handle: folder navigation, YAML loading, Python module loading
   - [ ] Work with user to enumerate all lookup cases

3. **Bio.fetch() enhancements**
   - [ ] Detect dots-before-slash and route to lookup()
   - [ ] Implement "loads within DAT" pattern (load YAML → dereference → hydrate)
   - [ ] Support `hydrate=False` option

4. **Bio.store()**
   - [ ] Implement dehydration and storage
   - [ ] (Remote sync planned for Later)

### Documentation

- [ ] Verify [[commands/ABIO Fetch|Fetch]] examples
- [ ] Verify [[commands/ABIO Cd|Cd]] documentation
- [ ] Verify [[commands/ABIO Store|Store]] documentation

---

## M3 — Build System

Template instantiation and scenario building. Builds on M2.

### Code

1. **Bio.build()**
   - [ ] Rename `_instantiate()` to public `build()` method
   - [ ] Ensure `build()` calls `fetch()` when given string
   - [ ] Template expansion with namespace prefixing

2. **Template system**
   - [ ] `TemplateRegistry.from_directory()`
   - [ ] `parse_template()`, `parse_port()`, `ports_compatible()`
   - [ ] `apply_template()` with `_as_` syntax
   - [ ] Guards: `@guard` decorator, `apply_template_with_guards()`

3. **Visibility system**
   - [ ] `generate_visibility_mapping()`
   - [ ] `apply_visibility()`, `apply_fraction_known()`

### Documentation

- [ ] Verify [[commands/ABIO Build|Build]] template instantiation docs
- [ ] Document generator/template.py, expand.py, guards.py, visibility.py
- [ ] Document generator exceptions

---

## M4 — Execution System

Running scenarios and collecting results. Builds on M3.

### Code

1. **Bio.run()**
   - [ ] Update `run()` to call `build()` when given string, then execute
   - [ ] Define `Runnable` protocol for objects that can be run

2. **Scenario execution**
   - [ ] `_run_scenario()`: build Chemistry, create State, run simulator, compute scores
   - [ ] `SimulationTrace` class with `final`, `timeline`, `steps`

3. **Scoring**
   - [ ] Scoring function evaluation with trace context
   - [ ] Verification checks

### Documentation

- [ ] Verify [[commands/ABIO Run|Run]] implicit chaining docs
- [ ] Add [[classes/execution/Runnable|Runnable]] class documentation
- [ ] Document `run.py` module

---

## M5 — Agent System

Agent registration and interaction. Builds on M4.

### Code

1. **Agent registry**
   - [ ] Add `_agents: dict[str, type]` registry to Bio
   - [ ] Add `register_agent(name, agent_class)` method
   - [ ] Add `create_agent(name, scenario, **kwargs)` factory method
   - [ ] Add `agents` property returning list of registered names

2. **Agent protocol**
   - [ ] Define `Agent` protocol with `step()`, `reset()`, `observe()`, `act()` methods

3. **Simulator integration**
   - [ ] `sim.action(name, ...)` and `sim.measure(name, ...)` methods
   - [ ] Action/measurement registry lookup

### Documentation

- [ ] Verify [[commands/ABIO Agent|Agent]] documentation
- [ ] Add [[classes/execution/Agent|Agent]] class documentation
- [ ] Update [[Agent Interface]] with registration pattern

---

## M6 — Experiment System

Multi-run experiments with result aggregation. Builds on M5.

### Code

1. **Experiment class**
   - [ ] `scenario`, `name`, `axes`, `exploration`, `samples`, `seed` fields
   - [ ] Exploration patterns: iterate, sample, grid
   - [ ] Result collection as list of dicts

2. **Bio.report()**
   - [ ] `report(results, format, output)` method
   - [ ] Formats: table, csv, excel, json
   - [ ] DAT integration via `dat_report`

3. **Post-actions**
   - [ ] Execute post_actions after experiment completes

### Documentation

- [ ] Verify [[commands/ABIO Report|Report]] DAT integration
- [ ] Verify [[classes/execution/Experiment|Experiment]] documentation

---

## M7 — Advanced Biology

Extended biology features for complex ecosystems.

### Code

1. **Container hierarchy**
   - [ ] ecosystems > regions > organisms > compartments > organelles
   - [ ] Outflow/inflow system with `^` parent reference
   - [ ] Target resolution: children first, then siblings, then up

2. **Organism features**
   - [ ] Maintained molecules (enzymes at constant concentration)
   - [ ] Operating envelope (survival ranges)
   - [ ] Reproduction threshold
   - [ ] Predation mechanics

3. **Reaction extensions**
   - [ ] Catalyst coefficient (0 = required but not consumed)

### Documentation

- [ ] Document `CompartmentImpl`, `CompartmentTreeImpl`
- [ ] Document `Flow`, `MembraneFlow`, `GeneralFlow`
- [ ] Document `WorldStateImpl`, `WorldSimulatorImpl`

---

## Later

Features planned but not yet scheduled.

### Remote Sync
- [ ] `bio fetch` from remote storage
- [ ] `bio store` to remote cloud storage

### Performance
- [ ] JAX-accelerated simulator (drop-in replacement for reference simulator)
- [ ] Rate functions must be pure functional for JAX tracing

### Advanced Simulation
- [ ] Multi-compartment simulation (`WorldSimulator`)
- [ ] Quiescence detection: `run(quiet=..., delta=..., span=...)`

### Advanced Reporting
- [ ] `detailed` report type with timelines, action traces, state snapshots

### Runtime Context
- [ ] Document runtime `Context` class (`config`, `io`, `do()`, `create()`, etc.)
- [ ] Document `ctx()` function and `o` proxy object

---

## See Also

- [[ABIO Todo]] — Detailed task tracking
- [[Architecture Docs]] — System documentation
