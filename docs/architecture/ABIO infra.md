# ABIO infra
**Parent**: [[ABIO Sys]]
Infrastructure: entity base classes, serialization, data management, and configuration.

## Entities
Core data classes and identity patterns that all biology objects inherit from.
- **[[Entity]]** - Base protocol for all biology objects.
- **[[PersistentEntity]]** - Entities saved to `data/` folder, loadable by name via dvc_dat.
- **[[ScopedEntity]]** - Entities named relative to their containing World or Harness.
- **[[Expr]]** - Simple functional expressions for operations and declarations.

- **[[Print-format]]** - How entities display and serialize (string, YAML, markdown).

## Data Management
- **[[ABIO Data]]** - Organization of the `data/` folder and intent-based categories.
- **[[ABIO DAT]]** - dvc_dat integration, name resolution, and `_spec_.yaml` format.

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

I would like to turn our attention to the relationship between DAT and entities:
One confusion for me is that some of these entities are gonna be associated with a DAT folder while others are not. Large data configurations and such will naturally be stored in the data folder as a DAT but like a single molecule or single pathway will be an entity, but probably we will not create a sub folder for the data for that single thing. The simplest picture would be one where certain protocols are associated. There are some class of DAT and in this way, they can be easily written to the file system, but just calling to save operator. But this means that we would have to decide once and for all which elements must be in the file system as a DAT and which can never be done in this way. This doesn't seem ideal. I'm worried that in some cases Bill really want to create it in that way, and in other cases we won't. Please consider different ways. We might approach this problem. And let me add one more way to your list of ideas. One idea is that we keep DAT separate and none of the entity classes are attached in that way. Instead every entity may have a pointer string into the DAT store. And the way this works is the first part of that pointer indicates the DAT so it's basically a DAT name and then maybe we use an arrow or something like that in the string and then the second part is a dotted name for where within the structure of that DAT it's stored. Then every DAT has a Yamo file called structure or data or content something like that, and this dotted string is referencing a sub portion of this content structure. That way some entities could actually be mapped to a single DAT while other entities are mapped to some portion of a DAT. As I think about it this location this location might actually be a temple a TUPLE with the first portion as a dat name as a DATA and the second portion is devoted location, the dotted location or maybe even is multiple entries that represents the path within the DAT. And since there's gonna be many of these entity objects, we might even want to have this field, potentially derivable from the structure of the entities themselves. Each entity probably has a pointer to its parent just to allow all different kinds of operations on that entity so we might even derive location dynamically in some cases. That's a lot to think about and there might be a better way to approach this problem, please consider.