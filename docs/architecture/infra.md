# Infra - Infrastructure

Infrastructure layer providing foundational capabilities for the Alien Biology system.

**Parent**: [[alienbio]]

## Entities
Core data classes and identity patterns that all biology objects inherit from.
- **[[Entity]]** - Base protocol for all biology objects. Provides utility functions.
- **[[PersistentEntity]]** - Entities saved to `data/` folder, loadable by name via dvc_dat.
- **[[ScopedEntity]]** - Entities named relative to their containing World or Harness.

## Data Management
Integration with [dvc_dat](https://github.com/oblinger/dvc-dat/blob/main/docs/overview.md) for persistent storage and retrieval.
*(Protocols to be added)*

## Serialization
YAML and string representation utilities.
*(Protocols to be added)*

## Configuration
System configuration and settings management.
*(Protocols to be added)*
