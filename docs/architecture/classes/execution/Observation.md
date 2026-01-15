 [[Architecture Docs]] → [[ABIO execution]]

# Observation

The agent's view of the environment at each decision point.

## Overview
Observation is the primary data structure through which an agent perceives the simulation environment. It provides everything the agent needs to decide on its next action: the scenario briefing, available actions/measurements, current observable state, and budget information.

| Property | Type | Description |
|----------|------|-------------|
| `briefing` | str | Scenario description/instructions for the agent |
| `constitution` | str | Rules/constraints the agent should follow |
| `available_actions` | dict[str, Any] | Actions the agent can take (name → info dict) |
| `available_measurements` | dict[str, Any] | Measurements available (name → info dict) |
| `current_state` | dict[str, Any] | Observable state of the environment |
| `step` | int | Current step number (0 at start) |
| `budget` | float | Total budget allocated |
| `spent` | float | Budget spent so far |
| `remaining` | float | Budget remaining (budget - spent) |

| Method | Returns | Description |
|--------|---------|-------------|
| `is_initial()` | bool | True if this is the first observation (before any actions) |

## Discussion

### Agent Interface Protocol
The Observation class is part of the agent interface protocol that defines how agents interact with the simulation environment:

```
┌─────────┐                    ┌─────────────┐
│  Agent  │◄── Observation ────│ Environment │
│         │─── Action ────────►│             │
│         │◄── ActionResult ───│             │
└─────────┘                    └─────────────┘
```

1. Agent receives an `Observation`
2. Agent returns an `Action` (or None to end)
3. Environment executes the action
4. Agent receives `ActionResult` (extends Observation with result data)
5. Repeat until agent returns None or budget exhausted

### Initial vs Subsequent Observations
The first observation has `step=0` and `is_initial()` returns True. The agent should use this to understand the scenario before taking action. After each action, the agent receives an `ActionResult` which contains updated observation data.

### Budget Management
The observation includes budget information to help agents make cost-aware decisions:
- `budget`: Total budget for the experiment
- `spent`: How much has been used
- `remaining`: How much is left (budget - spent)

Agents should check `remaining` before taking expensive actions.

### Available Actions/Measurements
The `available_actions` and `available_measurements` dicts map action names to info dicts containing:
- Description of what the action does
- Required parameters and their types
- Cost of the action

```python
# Example observation.available_actions
{
    "add_feedstock": {
        "description": "Add nutrients to the system",
        "params": {"amount": "float"},
        "cost": 10.0
    },
    "adjust_temp": {
        "description": "Change temperature",
        "params": {"delta": "float"},
        "cost": 5.0
    }
}
```

### Observable State
The `current_state` dict contains what the agent can observe without taking a measurement action. This typically includes directly observable quantities. Hidden state (requiring measurement to observe) is not included here.

## Protocol
```python
from dataclasses import dataclass, field
from typing import Any

@dataclass
class Observation:
    """What the agent observes about the environment."""

    briefing: str
    constitution: str
    available_actions: dict[str, Any]
    available_measurements: dict[str, Any]
    current_state: dict[str, Any]
    step: int
    budget: float
    spent: float
    remaining: float
    _is_initial: bool = field(default=True, repr=False)

    def is_initial(self) -> bool:
        """Return True if this is the first observation."""
        return self._is_initial
```

## See Also
- [[ActionResult]] - Extends Observation with action execution results
- [[Action (Agent Request)]] - What the agent returns to take an action
- [[ExperimentResults]] - Final results after experiment completion
- [[ABIO execution]] - Parent subsystem
