# Testing Summary
**Topic**: [[ABIO Topics]] > [[Testing]]

High-level overview of what each test file verifies. **534 tests total** across 10 test files.

**Related**: [[Testing]] covers test tiers and organization.

---

## test_spec_lang.py

Tests for the spec language: YAML tags, typed keys, decorators, and the Bio class.

- **YAML Tags** (`!ev`, `!ref`, `!include`)
  - Arithmetic and function evaluation in `!ev`
  - Reference resolution with dotted paths in `!ref`
  - File inclusion for markdown, YAML, and Python files
  - Security: dangerous builtins blocked (`open`, `__import__`)

- **Typed Keys** (`type.name:` syntax)
  - Transformation to `_type` field
  - Nested typed keys
  - Unknown types pass through unchanged

- **Decorators** (`@biotype`, `@scoring`, `@action`, `@measurement`, `@rate`)
  - Registration in global registries
  - Metadata storage and access
  - Hydrate/dehydrate round-trip

- **Defaults and Inheritance**
  - Deep merge of nested dicts
  - `null` removes inherited values
  - Suite defaults applied to child scenarios

- **Bio Class**
  - `Bio.fetch()` loads and hydrates specs
  - `Bio.store()` serializes to YAML
  - Round-trip preservation

- **Scope Class** (lexical scoping)
  - Parent-child inheritance chain
  - Shadowing of parent values
  - `resolve()` returns defining scope

---

## test_spec_eval.py

Tests for the spec evaluation system: hydrate, eval, dehydrate. **(~130 tests, pending implementation)**

- **Hydration**
  - Constants pass through unchanged
  - Recursive descent into dicts/lists
  - `!_` → Evaluable placeholder, `!quote` → Quoted placeholder, `!ref` → Reference
  - `!include` resolves files during hydration
  - Type instantiation from `_type` field

- **Dehydration**
  - Evaluable/Quoted/Reference → serializable dict form
  - Round-trip: `dehydrate(hydrate(x)) ≈ x`

- **Eval Expressions**
  - Arithmetic, builtins (`min`, `max`, `abs`, `sum`, `len`)
  - Conditionals, list comprehensions
  - Variables from `ctx.bindings`

- **Eval Quote**
  - `!quote` preserved as string, NOT evaluated
  - Variables inside quote not resolved

- **Eval Reference**
  - `!ref` resolves from `ctx.bindings`
  - Strict mode raises on missing; non-strict returns Reference

- **@function Decorator**
  - Auto-injection of `ctx` parameter
  - Distribution functions use `ctx.rng` for reproducibility

- **Context Object**
  - Seeded RNG produces reproducible results
  - Child context shadows parent bindings
  - Path tracking for error messages

- **Multiple Instantiations**
  - Same seed → same result
  - Different seeds → different random values
  - Original spec unchanged after eval

- **Error Handling**
  - Clear errors for undefined variables, syntax errors
  - Blocked builtins: `open`, `eval`, `exec`, `__import__`

---

## test_simulation.py

Tests for simulator creation and execution. **(~60 tests, pending implementation)**

- **Rate Compilation**
  - Constant rates, mass action (`k * S1 * S2`)
  - Michaelis-Menten (`Vmax * S / (Km + S)`)
  - Hill equation (`Vmax * S^n / (K^n + S^n)`)
  - Constants baked into rate functions at compile time

- **Simulator Creation**
  - `Bio.sim(scenario)` produces working simulator
  - Initial state from scenario
  - `step()` and `run()` execute correctly

- **Simulation Correctness**
  - Mass conservation in reactions
  - Substrates deplete, products accumulate
  - System responds to perturbations

- **Reproducibility**
  - Same seed → identical trajectory
  - Actions and measurements work correctly

---

## test_simulator_comprehensive.py

Thorough tests for ReferenceSimulatorImpl and DAT execution path.

- **Rate Functions**
  - Constant rate values
  - Callable rate functions invoked with state
  - Rate sees state at start of step (not mid-step)

- **Reaction Types**
  - Simple A → B reactions
  - Stoichiometric coefficients (2A + B → C)
  - Reversible reactions
  - Catalytic (enzyme present but not consumed)

- **Simulation Mechanics**
  - `step()` applies all reactions once
  - `run()` returns timeline of states
  - Timestep affects rate of change

- **Edge Cases**
  - Empty chemistry (no reactions)
  - Zero concentrations
  - Large step counts

- **Scoring and Verification**
  - Scoring functions computed from timeline
  - Verify assertions checked against final state

---

## test_bio.py

Tests for core biology protocols: Atom, Molecule, Reaction, Chemistry, State, Simulator.

- **Atom**
  - Creation with symbol, name, atomic weight
  - Symbol must be 1-2 characters
  - Equality and hashing (can be dict keys)
  - Common atoms registry (`COMMON_ATOMS`)

- **Molecule**
  - Creation with formula, properties
  - Molecular weight calculation from atoms
  - String representation

- **Reaction**
  - Reactants and products with stoichiometry
  - Rate function (constant or callable)
  - Reversible reactions

- **Chemistry**
  - Collection of molecules and reactions
  - Lookup by name

- **State**
  - Concentration dict for molecules
  - Initial state from Chemistry

- **Simulator Protocol**
  - `step()` and `run()` methods
  - Returns State objects

---

## test_entity.py

Tests for Entity base class and naming system.

- **Entity Creation**
  - Requires parent or DAT anchor
  - Name cannot contain spaces
  - Optional description field

- **Parent-Child Relationships**
  - Bidirectional links (parent.children, child.parent)
  - Children inherit DAT from tree root
  - Sub-roots can have their own DAT

- **Full Names**
  - Computed from parent chain
  - Unique within DAT scope

- **Entity Types**
  - Registration via `register_entity_type()`
  - Lookup via `get_entity_type()`

---

## test_dat.py

Tests for dvc_dat integration via alienbio operators.

- **do() Resolution**
  - Dotted names resolve to fixture data
  - Missing names raise KeyError

- **create()**
  - From string spec (prototype name)
  - From dict spec (inline data)
  - Returns Dat object

- **save() / load() Round-trip**
  - `save()` creates Dat folder with `_spec_.yaml`
  - `load()` retrieves Dat object
  - Dict data preserved through round-trip

---

## test_alienbio.py

Tests for top-level alienbio operators.

- **ctx()**
  - Returns Context object
  - Uses ContextVar (not plain global)
  - Creates default if none exists

- **set_context()**
  - Changes active context
  - New context accessible via `ctx()`

- **do()**
  - Resolves dotted names
  - Returns fixture data

- **create()**
  - From string or dict spec
  - Returns Dat object

- **save() / load()**
  - Persistence to/from Dat folders

---

## test_io.py

Tests for IO class: prefix bindings, formatting, parsing.

- **Prefix Bindings**
  - `bind_prefix()` associates prefix with entity
  - `resolve_prefix()` returns bound entity
  - `unbind_prefix()` removes binding

- **Format/Parse**
  - Entity → string representation with prefix
  - String → Entity lookup

---

## test_cli.py

Tests for the `bio` command-line interface.

- **bio report** (default command)
  - Runs hardcoded_test job
  - Shows concentration changes
  - Displays score and PASSED/FAILED
  - Shows verification checkmarks

- **bio run**
  - Prints YAML-formatted result dict
  - Shows final_state, scores, success

- **bio --help**
  - Displays usage information

---

## See Also

- [[Testing]] — Test tiers and organization
- [[Spec Evaluation]] — What test_spec_eval.py tests
- [[Simulator]] — What test_simulation.py tests
- [[ABIO Roadmap]] — M1.8a-tests and M1.8b-tests sections
