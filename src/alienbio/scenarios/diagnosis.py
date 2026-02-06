"""Diagnosis and cure tasks for agent evaluation."""

from __future__ import annotations

from typing import Any, Dict, List, TYPE_CHECKING

from ..bio.task import Task, TaskResult

if TYPE_CHECKING:
    from ..bio.agent_interface import AgentInterface
    from .disease import Baseline, Perturbation


class DiagnoseTask(Task):
    """Identify which perturbation was applied to a diseased system.

    The agent receives a diseased system and a list of candidate perturbations.
    It must identify which perturbation was actually applied.
    """

    def __init__(
        self,
        candidates: List["Perturbation"],
        applied_index: int,
    ) -> None:
        self._candidates = candidates
        self._applied_index = applied_index

    @property
    def name(self) -> str:
        return "diagnose"

    @property
    def description(self) -> str:
        n = len(self._candidates)
        return f"Identify which of {n} perturbations was applied to the system"

    @property
    def candidates(self) -> List["Perturbation"]:
        return list(self._candidates)

    @property
    def num_candidates(self) -> int:
        return len(self._candidates)

    @property
    def correct_index(self) -> int:
        return self._applied_index

    def score(self, interface: "AgentInterface", prediction: int) -> TaskResult:
        """Score a diagnosis prediction.

        Args:
            interface: Agent interface (not used for scoring, but part of protocol)
            prediction: Index into candidates list

        Returns:
            TaskResult with score 1.0 if correct, 0.0 if wrong
        """
        correct = prediction == self._applied_index
        return TaskResult(
            score=1.0 if correct else 0.0,
            details={
                "predicted_index": prediction,
                "correct_index": self._applied_index,
                "correct": correct,
                "num_candidates": len(self._candidates),
            },
        )


class CureTask(Task):
    """Restore a diseased system to healthy range.

    The agent receives a diseased system and must use actions to
    bring concentrations back within the healthy baseline ranges.
    """

    def __init__(
        self,
        baseline: "Baseline",
        *,
        recovery_steps: int = 200,
    ) -> None:
        self._baseline = baseline
        self._recovery_steps = recovery_steps

    @property
    def name(self) -> str:
        return "cure"

    @property
    def description(self) -> str:
        return "Restore the diseased system to healthy concentration ranges"

    @property
    def baseline(self) -> "Baseline":
        return self._baseline

    @property
    def recovery_steps(self) -> int:
        return self._recovery_steps

    def score(self, interface: "AgentInterface", prediction: Any = None) -> TaskResult:
        """Score cure attempt by checking if system is healthy after recovery.

        The agent should have already applied actions before score() is called.
        This method runs the system forward to allow actions to take effect,
        then checks whether concentrations are within healthy ranges.

        Args:
            interface: Agent interface wrapping the system
            prediction: Ignored (actions are applied directly)

        Returns:
            TaskResult with score based on fraction of molecules in range
        """
        # Run forward to let cure take effect
        interface.system.run(self._recovery_steps)

        concentrations = {
            name: interface.system.state[name]
            for name in interface.system.chemistry.molecules
        }

        # Score: fraction of molecules within healthy range
        in_range = 0
        total = len(self._baseline.ranges)
        details_per_mol: Dict[str, Any] = {}

        for r in self._baseline.ranges:
            val = concentrations.get(r.molecule, 0.0)
            healthy = r.contains(val)
            if healthy:
                in_range += 1
            details_per_mol[r.molecule] = {
                "value": val,
                "low": r.low,
                "high": r.high,
                "in_range": healthy,
            }

        cure_score = in_range / total if total > 0 else 1.0

        return TaskResult(
            score=cure_score,
            details={
                "molecules": details_per_mol,
                "in_range": in_range,
                "total": total,
            },
        )
