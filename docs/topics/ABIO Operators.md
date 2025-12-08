# ABIO Operators

Top-level operations for working with alienbio entities and data.

**Parent**: [[ABIO Topics]]

## Overview

These operators provide the foundational interface for loading, creating, resolving, and displaying alienbio objects. They wrap the underlying dvc_dat functionality with ABIO-specific conventions.

## Data Operations

### do(name) → object
Resolve a dotted name to an object. Traverses the namespace from data/, catalog/, or module paths.

```python
from alienbio import do

molecule = do("catalog.kegg1.molecule_gen")
dataset = do("data.upstream.kegg.2024.1")
```

### create(spec) → object
Instantiate an object from a prototype specification. The spec can be a dotted name string or a dict with prototype references.

```python
from alienbio import create

gen = create("catalog.kegg1.molecule_gen")
mol = create({"_proto": "catalog.kegg1.molecule_gen", "params": {...}})
```

### load(path) → object
Load an entity from a data path. Reads `_spec.yaml` and reconstructs the object.

```python
from alienbio import load

dataset = load("data/upstream/kegg/2024.1")
```

### save(obj, path)
Save an entity to a data path. Writes `_spec.yaml` and associated files.

```python
from alienbio import save

save(molecules, "data/derived/kegg1/molecules")
```

## Print Operations

### print format
Entities display in PREFIX:name format for quick identification.

```python
mol = BioMolecule(name="glucose")
print(mol)  # M:glucose

rxn = BioReaction(name="glycolysis_1")
print(rxn)  # R:glycolysis_1
```

See [[Print-format]] for full specification.

### parse(string) → object
Parse a string representation back into an object.

```python
from alienbio import parse

mol = parse("M:glucose")
```

## Context Access

### ctx() → Context
Access the runtime context containing configuration and subsystem references.

```python
from alienbio import ctx

config = ctx().config
simulator = ctx().simulator
```

See [[Context]] for full specification.

## Implementation Notes

These operators are defined in `alienbio/__init__.py` and wrap the dvc_dat `do()` function with ABIO namespace conventions. The exact API may evolve; this topic will be updated as the implementation solidifies.

## See Also

- [[DAT]] - Underlying data management system
- [[Context]] - Runtime pegboard
- [[Print-format]] - Entity display format
- [[Entity]] - Base class for all objects
