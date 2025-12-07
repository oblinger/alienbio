# Entity

The base class for all objects in the Alien Biology system.

## Properties

- **name** - unique identifier
- **description** - optional text description

## Serialization

- String format via `repr()`/`str()`
- YAML format for complex entities

## Subclasses

- [[test-molecule|BioMolecule]]
- [[test-reaction|BioReaction]]

## Source

See `src/architecture/entities.py`
