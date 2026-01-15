"""Results storage for experiment results.

This module provides functions to save and load experiment results.
Results are stored as YAML files in a structured directory format:
    data/results/{scenario}/{timestamp}/index.yaml

Example:
    from alienbio.agent import save_results, load_results, list_results

    # Save results after running experiment
    path = save_results(results, agent_type="anthropic", model="claude-opus-4")

    # Load a specific result
    loaded = load_results(path)

    # List all results for a scenario
    all_results = list_results("mutualism/b10")
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import yaml

from .types import ExperimentResults


def _results_base_dir() -> Path:
    """Return the base directory for results storage."""
    return Path("data/results")


def _serialize_trace(trace: Any) -> dict[str, Any]:
    """Serialize a Trace object for storage.

    Args:
        trace: The Trace object to serialize

    Returns:
        Dictionary representation of the trace
    """
    return {
        "total_cost": trace.total_cost,
        "action_count": len(trace),
        "actions": [
            {
                "name": record.action.name,
                "params": record.action.params,
                "step": record.step,
                "cost": record.cumulative_cost - (trace[i-1].cumulative_cost if i > 0 else 0),
            }
            for i, record in enumerate(trace)
        ]
    }


def _generate_timestamp() -> str:
    """Generate a timestamp string for result naming."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def save_results(
    results: ExperimentResults,
    agent_type: Optional[str] = None,
    model: Optional[str] = None,
    base_dir: Optional[Path] = None,
) -> Path:
    """Save experiment results to disk.

    Args:
        results: The ExperimentResults to save
        agent_type: Type of agent used (e.g., "anthropic", "random")
        model: Model name if LLM agent was used
        base_dir: Override base directory (default: data/results)

    Returns:
        Path to the saved results directory
    """
    base = base_dir or _results_base_dir()
    timestamp = _generate_timestamp()

    # Create directory structure: results/scenario/timestamp/
    scenario_name = results.scenario.replace("/", "_").replace("\\", "_")
    result_dir = base / scenario_name / timestamp
    result_dir.mkdir(parents=True, exist_ok=True)

    # Build result data
    data = {
        "scenario": results.scenario,
        "seed": results.seed,
        "agent_type": agent_type,
        "model": model,
        "status": results.status,
        "passed": results.passed,
        "incomplete_reason": results.incomplete_reason,
        "scores": results.scores,
        "trace": _serialize_trace(results.trace),
        "timestamp": timestamp,
    }

    # Write index.yaml
    index_file = result_dir / "index.yaml"
    with open(index_file, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    return result_dir


def load_results(path: Path | str) -> dict[str, Any]:
    """Load experiment results from disk.

    Args:
        path: Path to results directory or index.yaml file

    Returns:
        Dictionary containing result data
    """
    path = Path(path)

    if path.is_dir():
        index_file = path / "index.yaml"
    else:
        index_file = path

    if not index_file.exists():
        raise FileNotFoundError(f"Results not found: {index_file}")

    with open(index_file) as f:
        return yaml.safe_load(f)


def list_results(
    scenario: Optional[str] = None,
    base_dir: Optional[Path] = None,
) -> list[dict[str, Any]]:
    """List all saved results, optionally filtered by scenario.

    Args:
        scenario: Filter to results for this scenario
        base_dir: Override base directory

    Returns:
        List of result data dictionaries, sorted by timestamp (newest first)
    """
    base = base_dir or _results_base_dir()

    if not base.exists():
        return []

    results = []

    if scenario:
        # Look in specific scenario directory
        scenario_name = scenario.replace("/", "_").replace("\\", "_")
        scenario_dir = base / scenario_name
        if scenario_dir.exists():
            for timestamp_dir in scenario_dir.iterdir():
                if timestamp_dir.is_dir():
                    try:
                        data = load_results(timestamp_dir)
                        data["_path"] = str(timestamp_dir)
                        results.append(data)
                    except Exception:
                        pass
    else:
        # List all scenarios
        for scenario_dir in base.iterdir():
            if scenario_dir.is_dir():
                for timestamp_dir in scenario_dir.iterdir():
                    if timestamp_dir.is_dir():
                        try:
                            data = load_results(timestamp_dir)
                            data["_path"] = str(timestamp_dir)
                            results.append(data)
                        except Exception:
                            pass

    # Sort by timestamp (newest first)
    results.sort(key=lambda r: r.get("timestamp", ""), reverse=True)
    return results


def aggregate_results(
    scenario: Optional[str] = None,
    base_dir: Optional[Path] = None,
) -> dict[str, Any]:
    """Aggregate results across multiple runs.

    Args:
        scenario: Filter to results for this scenario
        base_dir: Override base directory

    Returns:
        Dictionary with aggregated statistics
    """
    all_results = list_results(scenario=scenario, base_dir=base_dir)

    if not all_results:
        return {
            "count": 0,
            "scenarios": [],
            "pass_rate": 0.0,
            "score_stats": {},
        }

    # Group by scenario
    by_scenario: dict[str, list[dict[str, Any]]] = {}
    for r in all_results:
        s = r.get("scenario", "unknown")
        if s not in by_scenario:
            by_scenario[s] = []
        by_scenario[s].append(r)

    # Calculate stats
    total_passed = sum(1 for r in all_results if r.get("passed", False))

    # Aggregate scores
    score_totals: dict[str, list[float]] = {}
    for r in all_results:
        for name, value in r.get("scores", {}).items():
            if name not in score_totals:
                score_totals[name] = []
            score_totals[name].append(value)

    score_stats = {}
    for name, values in score_totals.items():
        score_stats[name] = {
            "mean": sum(values) / len(values),
            "min": min(values),
            "max": max(values),
            "count": len(values),
        }

    return {
        "count": len(all_results),
        "scenarios": list(by_scenario.keys()),
        "pass_rate": total_passed / len(all_results) if all_results else 0.0,
        "score_stats": score_stats,
        "by_scenario": {
            s: {
                "count": len(runs),
                "pass_rate": sum(1 for r in runs if r.get("passed", False)) / len(runs),
            }
            for s, runs in by_scenario.items()
        },
    }
