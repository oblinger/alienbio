# Print-format - Entity Display and Serialization

How entities are displayed to users and serialized for storage.

**Related**: [[ABIO infra]] > Entities, [[Expr]]

## Overview
Entities need to be visible to users in multiple contexts:
- Debug output in the console
- Log files
- Obsidian/markdown documentation
- Stored configuration files

This topic covers the formatting conventions and utilities that make entities easier to read.

## Display Format
Entity references use a prefix notation: `PREFIX:name`

The prefix is a namespace binding that maps to a source of entities. By convention, certain prefixes map to certain entity types, but the mechanism is general-purpose.

## Conventional Prefixes
Single-letter prefixes for frequently-used entity types:

| Prefix | Convention | Entity Type |
|--------|------------|-------------|
| M | molecules | [[BioMolecule]] |
| R | reactions | [[BioReaction]] |
| P | pathways | [[Pathway]] |
| S | systems | [[BioSystem]] |
| O | organisms | [[BioOrganism]] |
| C | compartments | Compartment |
| E | experiments | [[Experiment]] |
| T | tasks | [[Task]] |
| W | worlds | [[World]] |

Multi-letter prefixes for less frequent or special cases:

| Prefix | Convention | Description |
|--------|------------|-------------|
| dat | persistent data | Entities from `data/` folder |
| cfg | configuration | Config and settings |
| tmp | temporary | Transient/scratch entities |

## Examples
```
# Prefix definitions using Expr syntax
define_prefix(M, world1.molecules)
define_prefix(R, world1.reactions)
define_prefix(P, world1.pathways)

# Entity references
M:glucose           # molecule "glucose" from M namespace
R:glycolysis_1      # reaction "glycolysis_1" from R namespace
P:citric_acid       # pathway "citric_acid" from P namespace

# Multiple sources with numeric suffixes
define_prefix(M1, world1.molecules)
define_prefix(M2, world2.molecules)
define_prefix(MD, dat.molecules)

M1:glucose          # from world1
M2:glucose          # from world2
MD:glucose          # from persistent data/

# Expressions using Expr format
measure(M:glucose, compartment=cytoplasm)
add(M:inhibitor, concentration=0.1)
reaction(M:A, M:B, produces=M:C, rate=0.5)
```

## String Representation
Every entity implements `__str__` and `__repr__` for Python contexts:
- `__str__`: Short prefix notation - `M:glucose`
- `__repr__`: Full reconstructible form with class name and all fields

## YAML Format
Entities serialize to YAML for storage and configuration:

```yaml
name: glucose
atoms:
  C: 6
  H: 12
  O: 6
bdepth: 0
```

Used by:
- [[PersistentEntity]] for saving to `data/` folder
- Configuration files
- Test fixtures

## Serialization
The `serialize()` and `deserialize()` methods on [[Entity]] handle conversion. Uses [pyyaml](https://pyyaml.org/) under the hood.
