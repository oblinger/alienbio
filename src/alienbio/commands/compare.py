"""Compare command: Compare multiple agents on the same scenario.

Usage:
    bio compare <scenario> --agents random,oracle --runs 3
    bio compare <scenario> --agents anthropic,openai --runs 5 --model claude-3-5-sonnet
    bio compare <scenario> --csv         # Output as CSV
    bio compare <scenario> --json        # Output as JSON
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Optional


def compare_command(args: list[str], verbose: bool = False) -> int:
    """Compare multiple agents on the same scenario.

    Args:
        args: Command arguments [scenario] [--agents a,b,c] [--runs N] [--csv] [--json]
        verbose: Enable verbose output

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    from alienbio import bio
    from alienbio.agent import run_experiment

    # Parse arguments
    scenario_path = None
    agents: list[str] = ["random"]
    runs: int = 1
    model: Optional[str] = None
    output_format = "console"

    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--agents" and i + 1 < len(args):
            agents = args[i + 1].split(",")
            i += 2
        elif arg == "--runs" and i + 1 < len(args):
            runs = int(args[i + 1])
            i += 2
        elif arg == "--model" and i + 1 < len(args):
            model = args[i + 1]
            i += 2
        elif arg == "--csv":
            output_format = "csv"
            i += 1
        elif arg == "--json":
            output_format = "json"
            i += 1
        elif not arg.startswith("--"):
            if scenario_path is None:
                scenario_path = arg
            i += 1
        else:
            i += 1

    if not scenario_path:
        print("Error: compare command requires a scenario path", file=sys.stderr)
        print("Usage: bio compare <scenario> --agents a,b,c --runs N", file=sys.stderr)
        return 1

    path = Path(scenario_path)

    # Handle relative paths
    if not path.exists():
        for catalog_dir in ["catalog/scenarios", "catalog"]:
            catalog_path = Path(catalog_dir) / scenario_path
            if catalog_path.exists():
                path = catalog_path
                break
        else:
            print(f"Error: Scenario not found: {scenario_path}", file=sys.stderr)
            return 1

    if verbose:
        print(f"Comparing agents on: {path}")
        print(f"Agents: {', '.join(agents)}")
        print(f"Runs per agent: {runs}")

    # Load scenario
    try:
        scenario = bio.expand(str(path))
    except Exception as e:
        print(f"Error loading scenario: {e}", file=sys.stderr)
        return 1

    # Run experiments
    results: list[dict[str, Any]] = []

    for agent_type in agents:
        for run_idx in range(runs):
            seed = run_idx  # Use run index as seed for reproducibility

            if verbose:
                print(f"  Running: {agent_type} (seed={seed})...")

            try:
                agent = _create_agent(agent_type, model=model, seed=seed)
                experiment_results = run_experiment(scenario, agent, seed=seed)

                results.append({
                    "agent": agent_type,
                    "run": run_idx + 1,
                    "seed": seed,
                    "passed": experiment_results.passed,
                    "status": experiment_results.status,
                    "scores": experiment_results.scores,
                    "total_cost": experiment_results.trace.total_cost,
                })
            except Exception as e:
                results.append({
                    "agent": agent_type,
                    "run": run_idx + 1,
                    "seed": seed,
                    "passed": False,
                    "status": "error",
                    "error": str(e),
                    "scores": {},
                    "total_cost": 0.0,
                })

    # Output results
    if output_format == "json":
        _output_json(results)
    elif output_format == "csv":
        _output_csv(results)
    else:
        _output_console(results, scenario_path, agents)

    return 0


def _create_agent(agent_type: str, model: Optional[str] = None, seed: Optional[int] = None):
    """Create an agent of the specified type."""
    from alienbio.agent import (
        RandomAgent,
        OracleAgent,
        HumanAgent,
        ConversationalLLMAgent,
    )

    if agent_type == "random":
        return RandomAgent(seed=seed)
    elif agent_type == "oracle":
        return OracleAgent()
    elif agent_type == "human":
        return HumanAgent()
    elif agent_type == "anthropic":
        return ConversationalLLMAgent(model=model, api="anthropic")
    elif agent_type == "openai":
        return ConversationalLLMAgent(model=model, api="openai")
    else:
        raise ValueError(f"Unknown agent type: {agent_type}")


def _output_console(results: list[dict], scenario: str, agents: list[str]) -> None:
    """Output results as formatted console table."""
    print(f"\n{'=' * 70}")
    print(f"COMPARISON: {scenario}")
    print(f"{'=' * 70}")

    # Summary by agent
    print(f"\n{'Agent':<15} {'Runs':<8} {'Passed':<8} {'Pass Rate':<12} {'Avg Cost':<12}")
    print("-" * 55)

    for agent in agents:
        agent_results = [r for r in results if r["agent"] == agent]
        total = len(agent_results)
        passed = sum(1 for r in agent_results if r["passed"])
        pass_rate = passed / total if total > 0 else 0.0
        avg_cost = sum(r["total_cost"] for r in agent_results) / total if total > 0 else 0.0

        print(f"{agent:<15} {total:<8} {passed:<8} {pass_rate*100:>6.1f}%     {avg_cost:>10.2f}")

    # Detailed scores
    if results and results[0].get("scores"):
        score_names = list(results[0]["scores"].keys())
        if score_names:
            print(f"\n{'Agent':<15} " + " ".join(f"{name:<12}" for name in score_names))
            print("-" * (15 + 13 * len(score_names)))

            for agent in agents:
                agent_results = [r for r in results if r["agent"] == agent]
                avg_scores = {}
                for name in score_names:
                    values = [r["scores"].get(name, 0.0) for r in agent_results]
                    avg_scores[name] = sum(values) / len(values) if values else 0.0

                scores_str = " ".join(f"{avg_scores[name]:>12.3f}" for name in score_names)
                print(f"{agent:<15} {scores_str}")

    print(f"{'=' * 70}\n")


def _output_csv(results: list[dict]) -> None:
    """Output results as CSV."""
    if not results:
        return

    # Get all score names
    score_names = set()
    for r in results:
        score_names.update(r.get("scores", {}).keys())
    score_names = sorted(score_names)

    # Header
    headers = ["agent", "run", "seed", "passed", "status", "total_cost"] + list(score_names)
    print(",".join(headers))

    # Rows
    for r in results:
        row = [
            r["agent"],
            str(r["run"]),
            str(r["seed"]),
            str(r["passed"]),
            r["status"],
            f"{r['total_cost']:.4f}",
        ]
        for name in score_names:
            row.append(f"{r['scores'].get(name, 0.0):.4f}")
        print(",".join(row))


def _output_json(results: list[dict]) -> None:
    """Output results as JSON."""
    print(json.dumps(results, indent=2, default=str))
