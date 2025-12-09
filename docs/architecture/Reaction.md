# Reaction
**Subsystem**: [[ABIO biology]] > Reactions
Transformation between molecules with stoichiometry and rate.

## Overview
Reaction represents a chemical transformation that converts reactants to products. Each reaction has reactants, products with stoichiometric coefficients, and a rate (constant or function). Reactions are Entity subclasses stored in Chemistry's `reactions` dict.

| Property | Type | Description |
|----------|------|-------------|
| `name` | str | Human-readable name (same as local_name) |
| `symbol` | str | Formula string: "reactant + reactant -> product" |
| `reactants` | Dict[Molecule, float] | Molecules consumed with coefficients |
| `products` | Dict[Molecule, float] | Molecules produced with coefficients |
| `rate` | float \| Callable | Constant rate or function of State |

| Method | Returns | Description |
|--------|---------|-------------|
| `get_rate(state)` | float | Get effective rate for given state |
| `add_reactant(mol, coef)` | None | Add a reactant after creation |
| `add_product(mol, coef)` | None | Add a product after creation |
| `set_rate(rate)` | None | Change the reaction rate |

## Discussion

### Stoichiometry
The stoichiometric coefficients determine how many molecules are consumed/produced:

```python
# 2A + B -> 3C (rate 0.5)
reaction = ReactionImpl(
    "synthesis",
    reactants={a: 2, b: 1},
    products={c: 3},
    rate=0.5,
    dat=dat,
)

# In simulation:
# - A decreases by 2 * rate * dt
# - B decreases by 1 * rate * dt
# - C increases by 3 * rate * dt
```

### Rate Functions
Reactions can have constant or dynamic rates:

```python
# Constant rate
r1 = ReactionImpl("r1", rate=0.1, dat=dat)

# Rate function (e.g., Michaelis-Menten)
def enzyme_rate(state):
    substrate = state["substrate"]
    km = 1.0
    vmax = 10.0
    return vmax * substrate / (km + substrate)

r2 = ReactionImpl("r2", rate=enzyme_rate, dat=dat)

# Get rate for current state
effective_rate = r2.get_rate(state)
```

### Serialization
Reactions serialize via `attributes()`:

```yaml
head: Reaction
name: glycolysis_step
reactants:
  glucose: 1
products:
  pyruvate: 2
  atp: 2
rate: 0.1
```

Note: Callable rate functions cannot be serialized and are omitted from output.

### Usage Example
```python
from alienbio import MoleculeImpl, ReactionImpl, ChemistryImpl

# Create molecules
glucose = MoleculeImpl("glucose", dat=dat)
pyruvate = MoleculeImpl("pyruvate", dat=dat)
atp = MoleculeImpl("atp", dat=dat)

# Create reaction: Glucose -> 2 Pyruvate + 2 ATP
reaction = ReactionImpl(
    "glycolysis_step",
    reactants={glucose: 1},
    products={pyruvate: 2, atp: 2},
    rate=0.1,
    dat=dat,
)

# Access properties
reaction.name    # "glycolysis_step"
reaction.symbol  # "glucose -> 2pyruvate + 2atp"
reaction.rate    # 0.1

# Add to chemistry
chem = ChemistryImpl(
    "glycolysis",
    molecules={"glucose": glucose, "pyruvate": pyruvate, "atp": atp},
    reactions={"glycolysis_step": reaction},
    dat=dat,
)
```

## Method Details

### `get_rate(state: State) -> float`
Get effective rate for given state.

**Args:**
- `state`: Current concentration state

**Returns:** Rate value (calls function if rate is callable, otherwise returns constant)

**Example:**
```python
rate = reaction.get_rate(state)
```

## Protocol
```python
from typing import Protocol, Callable, Dict, Union, runtime_checkable

@runtime_checkable
class Reaction(Protocol):
    """Protocol for reaction entities."""

    @property
    def name(self) -> str:
        """Human-readable name (same as local_name)."""
        ...

    @property
    def symbol(self) -> str:
        """Formula string: 'glucose + ATP -> G6P + ADP'."""
        ...

    @property
    def reactants(self) -> Dict[Molecule, float]:
        """Reactant molecules with stoichiometric coefficients."""
        ...

    @property
    def products(self) -> Dict[Molecule, float]:
        """Product molecules with stoichiometric coefficients."""
        ...

    @property
    def rate(self) -> Union[float, Callable]:
        """Reaction rate (constant or function of State)."""
        ...

    def get_rate(self, state: State) -> float:
        """Get effective rate for given state."""
        ...
```

## See Also
- [[Molecule]] - Reactants and products
- [[Chemistry]] - Container for reactions
- [[State]] - Molecule concentrations for rate functions
- [[Simulator]] - Applies reactions to advance state
- [[ReactionGenerator]] - Factory for reactions
- [[Pathway]] - Connected reaction sequences
