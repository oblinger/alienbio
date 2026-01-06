"""Built-in dataclass definitions for the spec language.

These are helper types used in YAML specs:
- RunConfig: Execution parameters (steps, until_quiet)
- Verification: Assertions and expectations

Note: Jobs are simply DATs with a `do:` function - no separate Job class needed.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class RunConfig:
    """Execution parameters for a scenario.

    Attributes:
        steps: Number of simulation steps to run
        until_quiet: Optional quiescence parameters {delta, span}
    """

    steps: int = 100
    until_quiet: dict[str, Any] | None = None


@dataclass
class Verification:
    """A single verification criterion.

    Can be an assertion (expression that must be true)
    or a scoring expectation (function result compared to threshold).
    """

    assert_: str | None = None  # Use assert_ to avoid keyword conflict
    message: str | None = None
    scoring: Callable | None = None
    expect: str | None = None

    def __post_init__(self):
        # Handle YAML loading where 'assert' comes through as dict key
        if hasattr(self, "assert") and self.assert_ is None:
            self.assert_ = getattr(self, "assert")
