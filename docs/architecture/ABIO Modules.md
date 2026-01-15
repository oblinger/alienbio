 [[Architecture Docs]]

# Modules

Code organization for the Alien Biology system.

---

## Source Tree

```
src/alienbio/
├── __init__.py              # Package exports
├── cli.py                   # CLI entry point
├── run.py                   # Execution helpers
│
├── spec_lang/               # Spec language processing
│   ├── bio.py               # Bio class — thin facade (400 lines)
│   ├── resolve.py           # Path resolution (source roots, DAT, dig)
│   ├── process.py           # Data transformation (includes, refs, hydrate)
│   ├── cache.py             # ORM caching layer
│   ├── tags.py              # YAML tag handlers (!include, !ref, !ev, !py)
│   ├── loader.py            # typed keys, expand_defaults
│   ├── eval.py              # Evaluable/Quoted/Reference evaluation
│   ├── scope.py             # Hierarchical scope chains
│   ├── decorators.py        # @biotype, @fn, @scoring, etc.
│   └── builtins.py          # Built-in functions
│
├── bio/                     # Biology domain classes
│   ├── molecule.py          # Molecule implementation
│   ├── reaction.py          # Reaction implementation
│   ├── chemistry.py         # Chemistry container
│   ├── state.py             # State (concentration dict)
│   ├── compartment.py       # Compartment implementation
│   ├── compartment_tree.py  # Compartment hierarchy
│   ├── simulator.py         # ReferenceSimulatorImpl
│   ├── world_simulator.py   # World-level simulation
│   ├── world_state.py       # World state management
│   ├── atom.py              # Atom building blocks
│   └── flow.py              # Flow between compartments
│
├── build/                   # Template instantiation
│   ├── pipeline.py          # Build pipeline orchestration
│   ├── template.py          # Template expansion
│   ├── expand.py            # Distribution/parameter expansion
│   ├── guards.py            # Constraint guards
│   ├── visibility.py        # Visible vs ground truth
│   └── exceptions.py        # Build-specific errors
│
├── commands/                # CLI commands
│   ├── run.py               # bio run command
│   ├── report.py            # bio report command
│   ├── expand.py            # bio expand command
│   └── cd.py                # bio cd command
│
├── infra/                   # Infrastructure
│   ├── entity.py            # Entity base class
│   ├── context.py           # Runtime context
│   ├── io.py                # File I/O utilities
│   └── imports.py           # Dynamic import helpers
│
└── protocols/               # Type protocols
    ├── bio.py               # Biology protocols (Molecule, Reaction, etc.)
    ├── execution.py         # Execution protocols (Simulator, etc.)
    └── infra.py             # Infrastructure protocols
```

---

## Key Modules

### spec_lang/

The spec language module handles YAML parsing, tag resolution, and data processing.

| Module | Lines | Purpose |
|--------|-------|---------|
| `bio.py` | 400 | Bio class facade — orchestrates fetch/store/build/run |
| `resolve.py` | 331 | Path resolution — source roots, DAT paths, dig operations |
| `process.py` | 118 | Data pipeline — includes, refs, py refs, defaults |
| `cache.py` | 56 | ORM caching — same path returns same object |
| `tags.py` | — | YAML tag handlers (!include, !ref, !ev, !py) |
| `loader.py` | — | typed key transformation, expand_defaults |
| `eval.py` | — | Evaluable/Quoted/Reference placeholder evaluation |

### bio/

Biology domain classes implementing the simulation model.

### build/

Template instantiation pipeline for expanding parameterized specs.

---

## Module Documentation

- **[Scope](modules/Scope.md)** — Hierarchical namespace resolution and inheritance

### Pending Documentation

- **Bio** — Core biology classes: molecules, reactions, compartments
- **CLI** — Command-line interface and command dispatch
- **Commands** — Individual CLI command implementations
- **Entity** — Base class infrastructure for all biology objects
- **Generator** — Template expansion and synthetic biology generation

---

## See Also

- [[ABIO Protocols]] — Alphabetical class index
- [[Spec Language Reference]] — YAML parsing, tags, evaluation pipeline
