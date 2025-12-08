# Files

Directory layout for the alienbio project.

**Parent**: [[alienbio]]

```
alienbio/
├─src/
│ ├─alienbio/                    # Python package
│ │ ├─__init__.py
│ │ ├─_smoke.py                  # Auto-run smoke tests
│ │ ├─protocols/                 # Protocol definitions (mirrors docs/architecture/)
│ │ │ ├─__init__.py
│ │ │ ├─infra.py                 # Entity, Context, Expr
│ │ │ ├─biology.py               # BioMolecule, BioReaction, BioContainer, Pathway
│ │ │ ├─generators.py            # Generators for synthetic biological systems
│ │ │ └─execution.py             # State, Step, Simulator, World, Timeline
│ │ ├─infra/                     # Infrastructure implementations
│ │ │ ├─context.py
│ │ │ ├─entity.py
│ │ │ └─expr.py
│ │ ├─biology/                   # Biology implementations
│ │ │ ├─molecule.py
│ │ │ ├─reaction.py
│ │ │ ├─pathway.py
│ │ │ └─container.py
│ │ ├─generators/                # Generator implementations
│ │ │ ├─molecule_gen.py
│ │ │ ├─reaction_gen.py
│ │ │ └─container_gen.py
│ │ └─execution/                 # Execution implementations
│ │   ├─state.py
│ │   ├─simulator.py
│ │   ├─world.py
│ │   └─harness.py
│ └─rust/                        # Rust crate (PyO3 bindings)
│   ├─Cargo.toml
│   ├─src/
│   │ ├─lib.rs
│   │ ├─molecule.rs
│   │ ├─reaction.rs
│   │ ├─pathway.rs
│   │ ├─container.rs
│   │ ├─state.rs
│   │ └─simulator.rs
│   └─benches/                   # Criterion benchmarks
├─tests/
│ ├─unit/                        # Fast isolated tests
│ │ ├─infra/
│ │ ├─biology/
│ │ ├─generators/
│ │ └─execution/
│ ├─integration/                 # Component interaction tests
│ ├─property/                    # Hypothesis/proptest
│ ├─parity/                      # Python == Rust verification
│ ├─benchmarks/                  # Performance tests
│ └─fixtures/                    # Shared test data
│   ├─molecules/
│   ├─reactions/
│   └─containers/
├─docs/
│ ├─architecture/                # Protocol documentation
│ └─topics/                      # Cross-cutting topics
├─data/                          # Persistent entities (dvc_dat)
├─justfile                       # Build/test commands
├─pyproject.toml
└─README.md
```

## Structure Notes

**protocols/** contains only Protocol definitions - the interfaces that implementations must satisfy. Each file mirrors a section in `docs/architecture/`:
- `infra.py` → [[infra]]
- `biology.py` → [[biology]]
- `generators.py` → [[biology]] > Generators
- `execution.py` → [[execution]]

**Implementation folders** (`infra/`, `biology/`, `generators/`, `execution/`) contain the actual implementations of those protocols.
