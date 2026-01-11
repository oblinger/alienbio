 [[Architecture Docs]]

# ABIO infra
Infrastructure: entity base classes, serialization, data management, and configuration.

## Entities
Core data classes and identity patterns that all biology objects inherit from.
- **[[Entity]]** - Base protocol for all biology objects.
- **[[Expr]]** - Functional expression trees for computations and rate equations.
- **[[Interpreter]]** - Evaluates Expr trees, handles language dispatch and template expansion.
- **[[IO]]** - Entity I/O: prefix bindings, formatting, parsing, persistence.
## Data Management
- **[[ABIO Data]]** - Organization of the `data/` folder and intent-based categories.
- **[[ABIO DAT]]** - dvc_dat integration, name resolution, and `_spec_.yaml` format.
- **[[Bio]]** - Higher-level fetch/store/run for biology objects.
- **[[Spec Language Reference]]** — YAML syntax extensions (`!ev`, `!_`, `!ref`, `!include`, typed keys).
- **[[Decorators]]** - `@biotype` for hydration, `@scoring`/`@action`/`@measurement`/`@rate` for functions.  

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
