 [[Architecture Docs]] → [[ABIO execution]]

# Action

Agent action to perturb the system state.

## Overview
Action represents a modification function that agents can use to perturb the biological system. Actions are the agent's means of affecting the world.

| Property | Type | Description |
|----------|------|-------------|
| `name` | str | Action identifier |
| `description` | str | What this action does |

| Method | Returns | Description |
|--------|---------|-------------|
| `apply(world, **params)` | World | Apply action and return modified world |

## Discussion

### Examples
- `add_molecule("inhibitor_X", 0.1)` - Add inhibitor to system
- `remove_enzyme("kinase_A")` - Remove an enzyme
- `adjust_temperature(+2.0)` - Change environmental condition

### Usage
```python
action = Action(
    name="add_drug",
    description="Add therapeutic compound to system"
)

new_world = action.apply(world, molecule="drug_X", concentration=0.5)
```

## Protocol
```python
from typing import Protocol, Any

class Action(Protocol):
    """Agent modification function."""

    name: str
    description: str

    def apply(self, world: World, **params: Any) -> World:
        """Apply action to world, return modified world."""
        ...
```

## See Also
- [[Measurement]] - Counterpart for observations
- [[Task]] - Constrains available actions
- [[ABIO execution]] - Parent subsystem
