"""Built-in biotype definitions for the spec language.

These are the core types used in YAML specs:
- Job: Executable DAT with scenario, run config, verification
- RunConfig: Execution parameters (steps, until_quiet)
- Verification: Assertions and expectations
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable

from .decorators import biotype


@dataclass
class RunConfig:
    """Execution parameters for a job.

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


@biotype("job")
@dataclass
class Job:
    """An executable DAT - a self-contained spec with scenario and execution.

    Jobs bundle:
    - chemistry: Molecules and reactions (or reference to chemistry DAT)
    - initial_state: Starting concentrations
    - run: Execution parameters (steps, until_quiet)
    - verify: Assertions and scoring expectations
    - scoring: Scoring function definitions

    Example usage:
        job = Bio.fetch("jobs/hardcoded_test")
        result = Bio.run(job)
        assert result.success
    """

    chemistry: dict[str, Any] = field(default_factory=dict)
    initial_state: dict[str, float] = field(default_factory=dict)
    run: dict[str, Any] = field(default_factory=dict)
    verify: list[dict[str, Any]] = field(default_factory=list)
    scoring: dict[str, Callable] = field(default_factory=dict)

    @property
    def steps(self) -> int:
        """Number of steps to run."""
        return self.run.get("steps", 100)

    @property
    def molecule_names(self) -> list[str]:
        """Names of all molecules in the chemistry."""
        mols = self.chemistry.get("molecules", {})
        return list(mols.keys())

    @property
    def reaction_names(self) -> list[str]:
        """Names of all reactions in the chemistry."""
        rxns = self.chemistry.get("reactions", {})
        return list(rxns.keys())


@dataclass
class JobResult:
    """Result of running a job.

    Attributes:
        success: Whether all verifications passed
        final_state: Concentrations at end of run
        timeline: List of states at each step (optional)
        scores: Computed scoring function values
        errors: List of verification failures
    """

    success: bool
    final_state: dict[str, float]
    timeline: list[dict[str, float]] | None = None
    scores: dict[str, float] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
