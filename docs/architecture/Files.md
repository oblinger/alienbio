# Files

Directory layout for the alienbio project.

**Parent**: [[alienbio]]

```
alienbio/
├─src/
│ ├─alienbio/                    # Python package
│ │ ├─__init__.py
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
│ │ ├─execution/                 # Execution implementations
│ │ │ ├─state.py
│ │ │ ├─simulator.py
│ │ │ ├─world.py
│ │ │ └─harness.py
│ │ └─catalog/                   # Named instances (see Catalog section below)
│ │   ├─kegg1/
│ │   │ ├─__catalog__.py
│ │   │ ├─molecule_gen.py
│ │   │ ├─reaction_gen.py
│ │   │ └─distributions.yaml
│ │   └─minimal1/
│ │     ├─__catalog__.py
│ │     └─cell.py
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
├─scripts/                       # Utility scripts (see Scripts section)
│ ├─smoke.py                     # Auto-run smoke tests
│ ├─build.py                     # Build helpers
│ └─download_upstream.py         # Fetch external datasets
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
├─data/                          # Persistent data (DAT system, see Data section)
│ ├─upstream/                    # External datasets (immutable)
│ │ └─kegg/
│ │   └─2024.1/
│ ├─derived/                     # Generated from upstream + catalog
│ │ ├─kegg1/
│ │ │ ├─molecules/
│ │ │ └─reactions/
│ │ └─minimal1/
│ │   └─cell/
│ └─runs/                        # Experiment executions
│   └─metabolism_bench/
│     ├─2024-01-15_001/
│     └─2024-01-15_002/
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

**Implementation folders** (`infra/`, `biology/`, `generators/`, `execution/`) contain base implementations of those protocols.

## Scripts

**scripts/** contains utility scripts that support development and operations. These are invoked by justfile commands or run directly.

```
scripts/
  smoke.py                  # Smoke tests run on package import
  build.py                  # Build automation helpers
  download_upstream.py      # Fetch and verify external datasets
  generate_derived.py       # Run catalog generators to populate derived/
```

Scripts are kept separate from the package to avoid polluting the importable namespace.

## Catalog

**catalog/** contains named instances of generators, containers, and other components. Unlike the implementation folders which provide base classes, the catalog provides ready-to-use, coherently grouped components.

### Organization

Catalog items are **grouped by coherence**, not by type. Related components that work together live in the same folder:

```
catalog/
  kegg1/                    # KEGG-based generators, version 1
    molecule_gen.py         # Molecules matching KEGG distributions
    reaction_gen.py         # Reactions matching KEGG patterns
    pathway_gen.py          # Pathways from KEGG templates
    distributions.yaml      # Shared statistical parameters
  kegg2/                    # Future: improved KEGG-based generators
  minimal1/                 # Minimal viable organism, version 1
    cell.py                 # Simplest possible cell
    metabolism.yaml         # Core metabolic config
```

### Versioned Naming

Catalog groups use versioned names (`kegg1`, `minimal1`) rather than bare names (`kegg`). This allows evolution:
- `kegg1` - Initial implementation based on KEGG data
- `kegg2` - Later revision with improved modeling
- Both can coexist, experiments can specify which version to use

### Dotted Names

Folder structure provides dotted names for DAT system integration:
- `catalog.kegg1.molecule_gen`
- `catalog.minimal1.cell`

Use `dat.do("catalog.kegg1.molecule_gen")` to resolve, `dat.create(...)` to instantiate.

### Self-Documenting Components

Components are self-documenting via decorators that indicate their type:

```python
# catalog/kegg1/molecule_gen.py
from alienbio.decorators import molecule_generator

@molecule_generator
class KEGGMoleculeGen:
    """Generates molecules matching KEGG statistical distributions."""
    ...
```

Decorators register the component type, enabling catalog scanning and discovery.

### __catalog__.py

Each catalog group has a `__catalog__.py` file describing its contents:

```python
# catalog/kegg1/__catalog__.py
"""KEGG-based generators for synthetic biology.

Generators in this group produce molecules, reactions, and pathways
matching statistical distributions extracted from the KEGG database.
Version 1 - initial implementation.
"""

__version__ = "1"
__components__ = {
    "molecule_gen": "MoleculeGenerator",
    "reaction_gen": "ReactionGenerator",
    "pathway_gen": "PathwayGenerator",
}
```

### Mixed Code and Config

Catalog groups can contain both:
- **Python files** (.py) - Complex logic, algorithms, classes
- **YAML files** (.yaml) - Parameters, distributions, configurations

YAML files can reference code via the DAT prototype system. Code files define the logic; YAML files parameterize it.

## Data

**data/** contains all persistent data managed by the [[DAT]] system. Every folder in `data/` is a DAT entry with a `_spec.yaml` file describing its contents and provenance.

Data flows from upstream through derived to runs:

```
upstream (external) → derived (generated) → runs (experiments)
```

See [[DAT]] for details on the DAT system and `_spec.yaml` format.

### upstream/

External datasets downloaded from other sources. **Immutable** - never modified after download.

```
data/upstream/
  kegg/
    2024.1/                     # Version from source
      _spec.yaml                # Metadata: source URL, download date, checksum
      compounds.json
      reactions.json
  uniprot/
    2024.2/
```

Each upstream dataset is a DAT with metadata recording:
- Source URL
- Download date
- Version from source
- Checksum for integrity verification

### derived/

Generated data built from upstream datasets + catalog code. These are materialized outputs from running catalog generators.

```
data/derived/
  kegg1/                        # Mirrors catalog/kegg1
    _spec.yaml                  # What catalog version, what upstream version
    molecules/                  # Generated molecule set
      _spec.yaml
      molecules.json
    reactions/
    pathways/
  minimal1/
    cell/
```

Organization **mirrors the source catalog** - if `catalog/kegg1/` defines generators, `data/derived/kegg1/` contains their outputs. This creates clear traceability.

Each derived DAT records:
- Which catalog version generated it
- Which upstream data it used
- Generation timestamp
- Any parameters used

### runs/

Experiment executions. Each run is a unique, timestamped folder.

```
data/runs/
  metabolism_bench/             # Experiment name
    2024-01-15_001/             # Timestamp + sequence number
      _spec.yaml                # Full config: derived data used, parameters
      results/
      logs/
    2024-01-15_002/
    latest -> 2024-01-15_002    # Optional: symlink to most recent
```

Run naming convention: `{YYYY-MM-DD}_{seq}` where seq is a sequence number for runs on the same day.

### Data Flow

The three-level structure tells a story:

1. **upstream/** - "Here's the external data we started with"
2. **derived/** - "Here's what we built from it using our catalog"
3. **runs/** - "Here's what happened when we ran experiments"

Future: DVC or Weights & Biases integration will version the data folder, enabling full reproducibility of any run by specifying exact versions of all components.
