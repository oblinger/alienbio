:>> [[ABIO]] → [[ABIO Docs]] → [ABIO infra](ha://p/ABIO%20infra) 
 [[ABIO Architecture Docs]] 

# ABIO infra
Infrastructure: entity base classes, serialization, data management, and configuration.

## Entities
Core data classes and identity patterns that all biology objects inherit from.
- **[[ABIO entity|Entity]]** - Base class every biology object carries, with the tree and its dat anchor.
- **[[ABIO IO]]** - Entity I/O: prefix bindings, formatting, parsing, persistence.

The `Expr Class` and `Interpreter` pages that stood here were retired
2026-10-07 (T068): both described an M1 design in which expression trees
were evaluated by an `Interpreter` object with a do-manager and a `lua:`
escape hatch. The language that shipped is `alienbio.expr` — forms
(`Name` / `Call` / `Quoted` / `Include` / `PyRef`), an environment and
`evaluate(form, env)`, with three spellings — and it is documented as
built in [[ABIO Expr Spec]] and [[ABIO Expr Python API]].

## Data Management
- **[[ABIO Data]]** - Organization of the `data/` folder and intent-based categories.
- **[[ABIO DAT]]** - the dvc-dat 3.0 surface the package actually uses (`Dat` as a duck-typed anchor, `MockDat` everywhere synthetic).
- **the M1 `Bio` facade (deleted in M47.7)** - Higher-level fetch/store/run for biology objects.
- **[[ABIO Expr Spec]]** — the Expr language by example: the three spellings, the head catalog, the special forms.
- **[[ABIO Expr Python API]]** - `@biotype` for hydration, `@scoring`/`@action`/`@measurement`/`@rate` for functions.

## Installed Packages
- **[pydantic](https://docs.pydantic.dev/)** - Data validation and settings management.
- **[numpy](https://numpy.org/doc/)** - Numerical arrays for concentration vectors, rate calculations.
- **[matplotlib](https://matplotlib.org/stable/)** - Plotting concentration curves, debugging visualizations.
- **[pyyaml](https://pyyaml.org/)** - YAML serialization for entities.
- **[pytest](https://docs.pytest.org/)** - Unit and integration testing.
- **[hypothesis](https://hypothesis.readthedocs.io/)** - Property-based testing.
- **[ruff](https://docs.astral.sh/ruff/)** - Fast linting and formatting.
- **[pyright](https://microsoft.github.io/pyright/)** - Static type checking.

## Configuration
System configuration and settings management.

*(Protocols to be added)*

## Testing
- **[[ABIO Testing]]** - Testing paradigm for Python and Rust code.
