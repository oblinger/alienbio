# Files

Directory layout for the alienbio project.

**Parent**: [[alienbio]]

```
alienbio/
├─src/
│ ├─alienbio/                # Python package
│ │ ├─__init__.py
│ │ ├─_smoke.py              # Auto-run smoke tests
│ │ ├─context.py             # Runtime pegboard
│ │ ├─entity.py              # Base entity classes
│ │ ├─expr.py                # Functional expressions
│ │ ├─biology/               # Biology subsystem
│ │ │ ├─molecule.py
│ │ │ ├─reaction.py
│ │ │ ├─pathway.py
│ │ │ ├─system.py
│ │ │ └─organism.py
│ │ ├─generators/            # Synthetic biology factories
│ │ │ ├─molecule_gen.py
│ │ │ ├─reaction_gen.py
│ │ │ └─system_gen.py
│ │ └─execution/             # Simulation and testing
│ │   ├─state.py
│ │   ├─simulator.py
│ │   ├─world.py
│ │   └─harness.py
│ └─rust/                    # Rust crate
│   ├─Cargo.toml
│   ├─src/
│   │ ├─lib.rs
│   │ ├─molecule.rs
│   │ ├─reaction.rs
│   │ ├─pathway.rs
│   │ ├─system.rs
│   │ ├─state.rs
│   │ └─simulator.rs
│   └─benches/               # Criterion benchmarks
├─tests/
│ ├─unit/                    # Fast isolated tests
│ │ ├─infra/
│ │ ├─biology/
│ │ └─execution/
│ ├─integration/             # Component interaction tests
│ ├─property/                # Hypothesis/proptest
│ ├─parity/                  # Python == Rust verification
│ ├─benchmarks/              # Performance tests
│ └─fixtures/                # Shared test data
│   ├─molecules/
│   ├─reactions/
│   └─systems/
├─docs/
│ ├─architecture/            # Protocol definitions
│ └─topics/                  # Cross-cutting topics
├─data/                      # Persistent entities (dvc_dat)
├─justfile                   # Build/test commands
├─pyproject.toml
└─README.md
```
