 [[Architecture Docs]] → [[ABIO execution]]

# ExperimentResults

Final results of a completed experiment run.

## Overview
ExperimentResults captures the outcome of running an experiment with an agent. It includes the scores achieved, whether the experiment passed, the complete trace of actions taken, and metadata about the run.

| Property | Type | Description |
|----------|------|-------------|
| `scenario` | str | Name of the scenario that was run |
| `seed` | Optional[int] | Random seed used (for reproducibility) |
| `scores` | dict[str, float] | Dictionary of score name → value |
| `trace` | Trace | Recording of all actions taken |
| `passed` | bool | Whether the experiment passed (score >= passing_score) |
| `status` | str | "completed" or "incomplete" |
| `incomplete_reason` | Optional[str] | Reason if status is "incomplete" |

## Discussion

### Pass/Fail Determination
An experiment passes when its primary score meets or exceeds the scenario's `passing_score` threshold:

```python
# Scenario defines: passing_score: 0.8
# Experiment achieves: scores["primary"] = 0.85
# Result: passed = True
```

### Scores Dictionary
The `scores` dict contains all evaluated scoring functions:

```python
scores = {
    "budget_compliance": 0.9,    # How well budget was used
    "goal_achievement": 0.85,    # Primary objective completion
    "efficiency": 0.72           # Resource efficiency
}
```

Scoring functions are registered with `@scoring` decorator and specified in the scenario.

### Trace Object
The `trace` field contains a Trace object recording the complete history:
- All actions taken by the agent
- Observations received
- Timing information
- System events

Traces are useful for debugging, analysis, and reproducibility.

### Incomplete Experiments
An experiment can be incomplete for several reasons:
- Agent exhausted budget
- Agent returned None (gave up)
- Time limit exceeded
- Error during execution

```python
ExperimentResults(
    scenario="complex_task",
    seed=42,
    scores={},
    trace=trace,
    passed=False,
    status="incomplete",
    incomplete_reason="Agent exhausted budget before achieving goal"
)
```

### Reproducibility
The `seed` field ensures experiments can be reproduced:

```python
# Run with specific seed
results = harness.run(agent, seed=12345)

# Later, reproduce exact same run
results2 = harness.run(agent, seed=12345)
assert results.scores == results2.scores
```

## Protocol
```python
from dataclasses import dataclass
from typing import Any, Optional

@dataclass
class ExperimentResults:
    """Results of a completed experiment run."""

    scenario: str
    seed: Optional[int]
    scores: dict[str, float]
    trace: Any  # Trace object
    passed: bool
    status: str = "completed"
    incomplete_reason: Optional[str] = None
```

## See Also
- [[Observation]] - What agent sees during experiment
- [[ActionResult]] - Results of individual actions
- [[Trace]] - Detailed record of experiment execution
- [[ABIO execution]] - Parent subsystem
