# ABIO infra - Infrastructure
**Parent**: [[alienbio]]
Infrastructure layer providing foundational capabilities for the Alien Biology system.

## Entities
Core data classes and identity patterns that all biology objects inherit from.
- **[[Entity]]** - Base protocol for all biology objects.
- **[[PersistentEntity]]** - Entities saved to `data/` folder, loadable by name via dvc_dat.
- **[[ScopedEntity]]** - Entities named relative to their containing World or Harness.
- **[[Expr]]** - Simple functional expressions for operations and declarations.

- **[[Print-format]]** - How entities display and serialize (string, YAML, markdown).

## Data Management
- **[dvc_dat](https://github.com/oblinger/dvc-dat/blob/main/docs/overview.md)** - Persistent storage and retrieval of entities by name.

## Installed Packages
- **[pydantic](https://docs.pydantic.dev/)** - Data validation and settings management.
- **[numpy](https://numpy.org/doc/)** - Numerical arrays for concentration vectors, rate calculations.
- **[matplotlib](https://matplotlib.org/stable/)** - Plotting concentration curves, debugging visualizations.
- **[pyyaml](https://pyyaml.org/)** - YAML serialization for entities.
- **[pytest](https://docs.pytest.org/)** - Unit and integration testing.
- **[hypothesis](https://hypothesis.readthedocs.io/)** - Property-based testing.
- **[pyo3](https://pyo3.rs/)** - Rust-Python bindings for high-performance simulator.
- **[ruff](https://docs.astral.sh/ruff/)** - Fast linting and formatting.
- **[pyright](https://microsoft.github.io/pyright/)** - Static type checking.

## Configuration
System configuration and settings management.

*(Protocols to be added)*

## Testing
- **[[Testing]]** - Testing paradigm for Python and Rust code.

- **[[ABIO Roadmap]]** - Implementation milestones.
