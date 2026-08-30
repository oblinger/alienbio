[[Architecture Docs]]

# Naming Conventions

Standard naming patterns used throughout the alienbio codebase.

## Protocol vs Implementation Pattern

The codebase uses a consistent pattern for defining interfaces (protocols) and their implementations:

| Component | Protocol | Implementation |
|-----------|----------|----------------|
| Molecule | `Molecule` | `MoleculeImpl` |
| Reaction | `Reaction` | `ReactionImpl` |
| Chemistry | `Chemistry` | `ChemistryImpl` |
| State | `State` | `StateImpl` |
| Simulator | `Simulator` | `ReferenceSimulatorImpl` |
| WorldState | `WorldState` | `WorldStateImpl` |
| WorldSimulator | (none) | `WorldSimulatorImpl` |
| Compartment | (none) | `CompartmentImpl` |
| CompartmentTree | `CompartmentTree` | `CompartmentTreeImpl` |
| Atom | `Atom` | `AtomImpl` |
| Flow | `Flow` | `MembraneFlow`, `GeneralFlow` |

### Protocol Classes

Protocols define the interface contract using Python's `typing.Protocol`:

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class Molecule(Protocol):
    """Protocol for molecule entities."""

    @property
    def name(self) -> str: ...

    @property
    def bdepth(self) -> int: ...
```

Protocols are:
- Used for type hints and duck typing
- Defined in `alienbio/protocols/bio.py`
- Exported from `alienbio` for type annotations
- Decorated with `@runtime_checkable` for isinstance() support

### Implementation Classes

Implementation classes provide concrete behavior:

```python
class MoleculeImpl(Entity, head="Molecule"):
    """Implementation: A molecule in the simulation."""

    def __init__(self, name: str, bdepth: int = 0, ...):
        ...
```

Implementation classes are:
- Named with `*Impl` suffix
- Inherit from `Entity` base class (for serialization, naming)
- Defined in `alienbio/bio/*.py`
- May have multiple implementations (e.g., `ReferenceSimulatorImpl`, `FastSimulatorImpl`)

### When to Use Each

**Use Protocol for:**
- Type hints in function signatures
- Dependency injection interfaces
- Testing with mocks

```python
def run_simulation(sim: Simulator, state: State) -> list[State]:
    ...
```

**Use Implementation for:**
- Creating actual instances
- Subclassing with custom behavior
- Factory registration

```python
mol = MoleculeImpl("glucose", bdepth=1)
```

## Entity Naming

Entities use the `PREFIX:name` format for string representation:

| Type | Prefix | Example |
|------|--------|---------|
| Molecule | `Mol` | `Mol:glucose` |
| Reaction | `Rxn` | `Rxn:glycolysis` |
| Chemistry | `Chem` | `Chem:basic` |
| Compartment | `Comp` | `Comp:cell` |

The prefix is defined by the `head` parameter in the Entity subclass.

## Flow Classes

Flows are an exception to the `*Impl` pattern. Instead of a single `FlowImpl`, there are specialized subclasses:

- `Flow` - Abstract base class
- `MembraneFlow` - Transport across parent-child membrane
- `GeneralFlow` - Arbitrary state modifications

This reflects the semantic differences between flow types.

## Factory Registration

Implementation classes can be registered with `@factory` decorator:

```python
from alienbio import factory
from alienbio.protocols.bio import Simulator

@factory(name="reference", protocol=Simulator, default=True)
class ReferenceSimulatorImpl(SimulatorBase):
    ...

@factory(name="fast", protocol=Simulator)
class FastSimulatorImpl(SimulatorBase):
    ...
```

Then create instances via Bio:

```python
bio.create(Simulator)                    # default: ReferenceSimulatorImpl
bio.create(Simulator, name="fast")       # FastSimulatorImpl
```

## See Also

- [[ABIO Protocols]] - Protocol definitions
- [[ABIO biology]] - Biology class implementations
- [[Factory Pegboard API]] - Factory pattern details
