"""Experiment battery - run scenarios × agents × seeds systematically.

An ExperimentBattery runs every combination of scenario, agent, and seed,
collecting results into a BatteryResult for aggregation and analysis.
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from .agents import Agent
from .experiment import run_experiment
from .types import ExperimentResults


@dataclass
class BatteryEntry:
    """One experiment run within a battery."""

    agent_name: str
    result: ExperimentResults


@dataclass
class BatteryResult:
    """Aggregated results from a battery run."""

    entries: list[BatteryEntry] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.entries)

    @property
    def passed(self) -> int:
        return sum(1 for e in self.entries if e.result.passed)

    @property
    def failed(self) -> int:
        return self.total - self.passed

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total if self.total else 0.0

    def by_scenario(self) -> dict[str, list[BatteryEntry]]:
        """Group entries by scenario name."""
        groups: dict[str, list[BatteryEntry]] = {}
        for entry in self.entries:
            key = entry.result.scenario
            groups.setdefault(key, []).append(entry)
        return groups

    def by_agent(self) -> dict[str, list[BatteryEntry]]:
        """Group entries by agent name."""
        groups: dict[str, list[BatteryEntry]] = {}
        for entry in self.entries:
            groups.setdefault(entry.agent_name, []).append(entry)
        return groups

    def filter(
        self,
        agent: Optional[str] = None,
        scenario: Optional[str] = None,
        seed: Optional[int] = None,
    ) -> "BatteryResult":
        """Return a new BatteryResult with only matching entries.

        Args:
            agent: Filter by agent name (exact match).
            scenario: Filter by scenario name (exact match).
            seed: Filter by seed value.
        """
        entries = self.entries
        if agent is not None:
            entries = [e for e in entries if e.agent_name == agent]
        if scenario is not None:
            entries = [e for e in entries if e.result.scenario == scenario]
        if seed is not None:
            entries = [e for e in entries if e.result.seed == seed]
        return BatteryResult(entries=entries)

    def merge(self, other: "BatteryResult") -> "BatteryResult":
        """Combine entries from two BatteryResults."""
        return BatteryResult(entries=self.entries + other.entries)

    def summary(self) -> list[dict[str, Any]]:
        """Per-agent summary with pass rate and mean scores."""
        rows = []
        for agent_name, entries in self.by_agent().items():
            total = len(entries)
            passed = sum(1 for e in entries if e.result.passed)
            # Collect all score keys
            all_keys: set[str] = set()
            for e in entries:
                all_keys.update(e.result.scores.keys())
            mean_scores = {}
            for key in sorted(all_keys):
                vals = [e.result.scores[key] for e in entries if key in e.result.scores]
                mean_scores[key] = sum(vals) / len(vals) if vals else 0.0
            rows.append({
                "agent": agent_name,
                "total": total,
                "passed": passed,
                "pass_rate": passed / total if total else 0.0,
                "mean_scores": mean_scores,
            })
        return rows


@dataclass
class BatteryProgress:
    """Progress report for a battery run."""

    completed: int
    total: int
    scenario: str
    agent: str
    seed: int


class ExperimentBattery:
    """Run multiple experiments systematically across scenarios × agents × seeds.

    Args:
        scenarios: List of scenario dicts to test.
        agents: Dict mapping agent name to Agent instance.
        seeds: List of random seeds for reproducibility.
        on_progress: Optional callback called after each experiment completes.
    """

    def __init__(
        self,
        scenarios: list[dict[str, Any]],
        agents: dict[str, Agent],
        seeds: list[int],
        on_progress: Optional[Callable[[BatteryProgress], None]] = None,
    ):
        self.scenarios = scenarios
        self.agents = agents
        self.seeds = seeds
        self.on_progress = on_progress

    @property
    def total_runs(self) -> int:
        return len(self.scenarios) * len(self.agents) * len(self.seeds)

    def run(self) -> BatteryResult:
        """Execute all scenario × agent × seed combinations.

        Returns:
            BatteryResult containing all experiment results.
        """
        result = BatteryResult()
        completed = 0

        for scenario in self.scenarios:
            scenario_name = scenario.get("name", "unnamed")
            for agent_name, agent in self.agents.items():
                for seed in self.seeds:
                    experiment_result = run_experiment(scenario, agent, seed=seed)
                    result.entries.append(BatteryEntry(
                        agent_name=agent_name,
                        result=experiment_result,
                    ))
                    completed += 1
                    if self.on_progress:
                        self.on_progress(BatteryProgress(
                            completed=completed,
                            total=self.total_runs,
                            scenario=scenario_name,
                            agent=agent_name,
                            seed=seed,
                        ))

        return result
