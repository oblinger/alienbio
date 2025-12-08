# Roadmap

Implementation milestones for the alienbio project.

**Related**: [[alienbio]], [[Testing]]

## Milestone 1: Hollow World
Get the development infrastructure working with stub implementations.

### Goals
- Project structure in place
- Dev cycle working: edit → test → commit
- Basic types exist (stubbed)
- Print format working
- Smoke tests running on import

### Deliverables
- [ ] `pyproject.toml` with dependencies
- [ ] `justfile` with test/lint commands
- [ ] `src/alienbio/__init__.py` with smoke test runner
- [ ] `src/alienbio/context.py` - Context pegboard (stubbed)
- [ ] `src/alienbio/entity.py` - Entity base class
- [ ] `src/alienbio/expr.py` - Expr for print format
- [ ] `tests/unit/infra/test_entity.py` - basic entity tests
- [ ] `tests/unit/infra/test_context.py` - context smoke tests
- [ ] Verify: `just test` runs and passes
- [ ] Verify: `import alienbio` runs smoke tests

### Smoke Tests for M1
```python
# Architectural invariants to verify
- Context uses ContextVar (not plain global)
- Entity base class exists and is importable
- Expr can format simple expressions
- Print format produces PREFIX:name output
```

## Milestone 2: Biology Stubs
Stub out the biology layer with minimal implementations.

### Deliverables
- [ ] `src/alienbio/biology/molecule.py` - BioMolecule
- [ ] `src/alienbio/biology/reaction.py` - BioReaction
- [ ] `src/alienbio/biology/pathway.py` - Pathway
- [ ] `src/alienbio/biology/system.py` - BioSystem
- [ ] `tests/fixtures/molecules/glucose.yaml`
- [ ] `tests/unit/biology/test_molecule.py`
- [ ] Verify: can create molecule, print as `M:glucose`

## Milestone 3: Rust Foundation
Set up Rust crate with pyo3 bindings.

### Deliverables
- [ ] `src/rust/Cargo.toml`
- [ ] `src/rust/src/lib.rs` - pyo3 module
- [ ] `src/rust/src/molecule.rs` - Rust BioMolecule
- [ ] `just test-rust` works
- [ ] `just test-parity` - Python/Rust produce same output
- [ ] Benchmark: Rust molecule creation vs Python

## Milestone 4: Simulation Engine
Core simulation loop working.

### Deliverables
- [ ] `src/alienbio/execution/state.py` - State
- [ ] `src/alienbio/execution/simulator.py` - Simulator protocol
- [ ] `src/rust/src/simulator.rs` - Rust simulator
- [ ] Can step a simple system forward in time
- [ ] Property tests: mass conservation

## Milestone 5: Generators
Procedural generation of biology.

### Deliverables
- [ ] `src/alienbio/generators/molecule_gen.py`
- [ ] `src/alienbio/generators/reaction_gen.py`
- [ ] `src/alienbio/generators/system_gen.py`
- [ ] Property tests: generated objects satisfy invariants
- [ ] Statistical tests: distributions match KEGG

## Milestone 6: Agent Interface
API for LLM agents to interact with worlds.

### Deliverables
- [ ] Measurement protocol
- [ ] Action protocol
- [ ] Task definitions
- [ ] Example agent interaction

## Milestone 7: Experimentation Framework
Full test harness for agent evaluation.

### Deliverables
- [ ] Experiment runner
- [ ] TestHarness with logging
- [ ] Result aggregation
- [ ] Example experiment batch
