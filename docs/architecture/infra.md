# Infra - Infrastructure

Infrastructure layer providing foundational capabilities for the Alien Biology system.

**Parent**: [[alienbio|ALIEN BIO]]

## Entities

Core data classes and identity patterns that all biology objects inherit from.

### [[entity|Entity]]
Base protocol for all biology objects. Provides string/YAML serialization, name and description fields.

### [[persistent_entity|PersistentEntity]]
Entities saved to `data/` folder and loadable by name via dvc_dat. Used for reusable definitions like molecule types and reaction templates.

### [[scoped_entity|ScopedEntity]]
Entities named relative to their containing World or Harness. Used for runtime instances like "the glucose in compartment A".

## Data Management

Integration with dvc_dat for persistent storage and retrieval.

*(Protocols to be added: DataStore, EntityLoader, EntityRegistry)*

## Serialization

YAML and string representation utilities.

*(Protocols to be added: Serializer, Deserializer)*

## Configuration

System configuration and settings management.

*(Protocols to be added: Config, Settings)*
