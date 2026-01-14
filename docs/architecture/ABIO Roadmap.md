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
- [Bio.md](classes/infra/Bio.md) — Bio class refactoring steps, hydration consolidation
- [[Spec Language Reference]] — Tag system consolidation, Context class cleanup

### Code Refactoring

1. **Bio class: instance pattern**
   - [ ] Refactor `_BioCompat` static wrappers to delegate to singleton
   - [ ] Ensure `Bio.__init__()` creates fresh DAT context and scope chain
   - [ ] Export `bio` singleton from `alienbio.__init__`
   - [ ] Update CLI commands to use singleton `bio` instance

2. **Consolidate hydration** (see TODO 2026-01-14 #7)
   - [ ] Move `hydrate`/`dehydrate` to module-level functions in `alienbio/__init__.py`
   - [ ] Update Bio.fetch() to call module-level hydrate()
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

7. **Factory pattern** (see TODO 2026-01-14 #7)
   - [ ] Implement `@factory` decorator in `alienbio/decorators.py`
   - [ ] Implement factory registry on Bio (`_factories`, `_factory_defaults`)
   - [ ] Update existing `*Impl` classes with `@factory` decorators
   - [ ] Add `impl` parameter to `build()`

8. **Module exports cleanup** (see TODO 2026-01-14 #9)
   - [ ] Refactor `alienbio/__init__.py` to use curated `__all__`
   - [ ] Export main API: `bio`, `Bio`, `hydrate`, `dehydrate`
   - [ ] Export core protocols: `Entity`, `Scenario`, `Chemistry`, `Simulator`, `State`
   - [ ] Keep `*Impl` classes importable but NOT in `__all__`

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

### Factory Pattern Documentation (see TODO 2026-01-14 #6)

- [ ] Create new doc: `docs/architecture/Factory Pattern.md`
- [ ] Document `@factory` decorator usage and registration
- [ ] Document implementation resolution order (build param → spec field → config default)
- [ ] Document config file format for defaults
- [ ] Add examples for creating custom implementations
- [ ] Update Bio.md to reference factory pattern doc

---

## M1.6 — Fetch Foundation (Current)

Front-loaded from M2 while design is fresh. Execute TODO 2026-01-14 items in order:

1. **#10 YAML/Python Fetch Implementation** — `!py` tag, source_roots config, Python globals as data
2. **#3 Fetch String Resolution** — Routing logic, dig operation, source root scanning
3. **#2 ORM Pattern** — DAT caching, `Bio(dat=...)` constructor
4. **#4 Fetch User Documentation** — Update docs to match implementation

---

## M2 — Bio Fetch & Lookup

Bio class methods for loading and navigating specs. Builds on M1.6.

**Key docs with implementation notes:**
- [Fetch](commands/ABIO Fetch.md) — Specifier routing logic, hydration order, data sources

### Code

1. **Bio.cd()**
   - [ ] Add `_current_dat: Path | None` instance variable
   - [ ] Add `cd(path=None)` method
   - [ ] Update `fetch()`, `store()` to resolve relative paths against current DAT
   - [ ] CLI: `bio cd` prints current, `bio cd path` changes it

2. **ORM Pattern** (see TODO 2026-01-14 #2)
   - [ ] Document DAT ORM pattern (single in-memory instance per DAT)
   - [ ] Implement DAT caching layer for fetch()
   - [ ] Implement `Bio(dat=...)` constructor parameter (accepts string or DAT object)
   - [ ] Document `bio.dat` accessor with lazy anonymous DAT creation
   - [ ] Define anonymous DAT spec constant location in config

3. **Fetch string resolution** (see TODO 2026-01-14 #3)
   - [ ] Implement routing logic (`/` → DAT, dots → module or source root)
   - [ ] Implement DAT name parsing (extract name + dig path)
   - [ ] Implement module access (import + attribute dig)
   - [ ] Implement source root scanning (YAML file discovery)
   - [ ] Implement shared dig operation (dict key / attribute access)
   - [ ] Implement ORM caching for DAT access
   - [ ] Enable and pass all tests in `test_fetch_resolution.py`
   - [ ] Handle edge cases (empty string, unicode, whitespace, etc.)

4. **YAML/Python coexistence** (see TODO 2026-01-14 #10)
   - [ ] Implement source_roots config with path + module pairs
   - [ ] Implement `!py` tag resolution (local to source file)
   - [ ] Implement Python module global loading (dict and "yaml: " string)
   - [ ] Update fetch() to check both YAML files and Python globals
   - [ ] Add tests for YAML/Python coexistence scenarios

5. **Bio.fetch() enhancements**
   - [ ] Detect dots-before-slash and route to lookup()
   - [ ] Implement "loads within DAT" pattern (load YAML → dereference → hydrate)
   - [ ] Support `hydrate=False` option

6. **Bio.store()**
   - [ ] Implement dehydration and storage
   - [ ] (Remote sync planned for Later)

### Documentation

- [ ] Verify [Fetch](commands/ABIO Fetch.md) examples match implementation
- [ ] Verify [Cd](commands/ABIO Cd.md) documentation
- [ ] Verify [Store](commands/ABIO Store.md) documentation

### DAT Name Convention Verification (see TODO 2026-01-14 #1)

- [ ] Review all documentation to ensure DAT names (full names) are used, not filesystem paths
- [ ] Review code to verify cross-component APIs use DAT names
- [ ] Verify persisted data stores DAT names, not paths
- [ ] Check that paths starting with `/` are handled as filesystem path escape hatch

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

- [ ] Verify [Build](commands/ABIO Build.md) template instantiation docs
- [ ] Document generator/template.py, expand.py, guards.py, visibility.py
- [ ] Document generator exceptions

---

## M4 — Execution System

Running scenarios and collecting results. Builds on M3.

### Code

1. **Entity.run() base** (see TODO 2026-01-14 #7)
   - [ ] Implement `Entity.run()` base method with NotImplementedError
   - [ ] Add `run()` methods to Scenario, Experiment, Report classes
   - [ ] Each returns domain-specific result (SimulationTrace, list[dict], Path)

2. **Bio.run()**
   - [ ] Update `run()` to call `build()` when given string, then execute
   - [ ] Wrap entity.run() result in dict with metadata (success, dat, elapsed)
   - [ ] Define `Runnable` protocol for objects that can be run

3. **Scenario execution**
   - [ ] `_run_scenario()`: build Chemistry, create State, run simulator, compute scores
   - [ ] `SimulationTrace` class with `final`, `timeline`, `steps`

4. **Scoring**
   - [ ] Scoring function evaluation with trace context
   - [ ] Verification checks

### Documentation

- [ ] Verify [Run](commands/ABIO Run.md) implicit chaining docs
- [ ] Add [Runnable](classes/execution/Runnable.md) class documentation
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

- [ ] Verify [Agent](commands/ABIO Agent.md) documentation
- [ ] Add [Agent](classes/execution/Agent.md) class documentation
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

- [ ] Verify [Report](commands/ABIO Report.md) DAT integration
- [ ] Verify [Experiment](classes/execution/experiment.md) documentation

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

## Cross-Cutting: Documentation Audit

Tasks that can be done alongside any milestone. See TODO 2026-01-14 for details.

### Documentation Integration Audit (see TODO 2026-01-14 #5)

- [ ] Scan all resolved questions (#1-13) in ABIO Todo.md
- [ ] For each resolution, verify details are integrated into relevant system docs
- [ ] Ensure no design decisions are lost in planning doc only
- [ ] Cross-reference: planning doc should point to where details live in real docs

### Pipeline Documentation Consistency (see TODO 2026-01-14 #8)

- [ ] Verify all docs use consistent pipeline: fetch → hydrate → build → eval
- [ ] Update Bio.md methods table to NOT include hydrate/dehydrate (module-level now)
- [ ] Update ABIO Hydrate.md to note it's module-level and called by fetch by default
- [ ] Ensure Spec Language Reference matches Core Spec on tag resolution timing

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
