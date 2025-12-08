# Action
**Subsystem**: [[execution]] > Interface
Agent action to perturb system state.

## Description
Action represents a modification function that agents can use to perturb the biological system. Actions are the agent's means of affecting the world.

| Properties | Type | Description |
|----------|------|-------------|
| name | str | Action identifier |
| description | str | What this action does |

| Methods | Description |
|---------|-------------|
| apply | Apply action to world, return modified world |

## Protocol Definition
```python
from typing import Protocol

class Action(Protocol):
    """Agent modification function."""

    name: str
    description: str

    def apply(self, world: World, **params) -> World:
        """Apply action to world, return modified world."""
        ...
```

## Methods
### apply(world, **params) -> World
Applies the action and returns the modified world.

## Examples
- `add_molecule("inhibitor_X", 0.1)` - Add inhibitor to system
- `remove_enzyme("kinase_A")` - Remove an enzyme
- `adjust_temperature(+2.0)` - Change environmental condition

## See Also
- [[execution]]
- [[Measurement]] - Counterpart for observations
- [[Task]] - Constrains available actions
