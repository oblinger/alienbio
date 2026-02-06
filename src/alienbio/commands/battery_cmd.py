"""Battery command: Run an experiment battery from a YAML spec.

Usage:
    bio battery <spec.yaml>                 # Run battery, print summary
    bio battery <spec.yaml> --save results  # Run and save to results.yaml
    bio battery <spec.yaml> --csv           # Run and output CSV
    bio battery <spec.yaml> --json          # Run and output JSON

Battery spec format (YAML):
    scenarios:
      - catalog/test/scenarios/simple.yaml
      - catalog/test/scenarios/timing.yaml
    agents:
      - random
      - oracle
    seeds: [0, 1, 2, 3, 4]
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional

import yaml


def battery_command(args: list[str], verbose: bool = False) -> int:
    """Run an experiment battery from a spec file.

    Args:
        args: Command arguments [spec_path] [options]
        verbose: Enable verbose output

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    from alienbio import bio
    from alienbio.agent import ExperimentBattery, BatteryProgress
    from alienbio.agent.results_store import save_results, export_csv, export_json

    # Parse arguments
    spec_path = None
    save_path: Optional[str] = None
    output_format = "console"

    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--save" and i + 1 < len(args):
            save_path = args[i + 1]
            i += 2
        elif arg == "--csv":
            output_format = "csv"
            i += 1
        elif arg == "--json":
            output_format = "json"
            i += 1
        elif not arg.startswith("--"):
            if spec_path is None:
                spec_path = arg
            i += 1
        else:
            i += 1

    if not spec_path:
        print("Error: battery command requires a spec file", file=sys.stderr)
        print("Usage: bio battery <spec.yaml> [--save path] [--csv] [--json]", file=sys.stderr)
        return 1

    # Load battery spec
    path = Path(spec_path)
    if not path.exists():
        print(f"Error: Spec file not found: {spec_path}", file=sys.stderr)
        return 1

    try:
        with open(path) as f:
            spec = yaml.safe_load(f)
    except yaml.YAMLError as e:
        print(f"Error parsing spec: {e}", file=sys.stderr)
        return 1

    if not isinstance(spec, dict):
        print("Error: Battery spec must be a YAML mapping", file=sys.stderr)
        return 1

    # Load scenarios
    scenario_paths = spec.get("scenarios", [])
    if not scenario_paths:
        print("Error: No scenarios specified in battery spec", file=sys.stderr)
        return 1

    scenarios: list[dict[str, Any]] = []
    for sp in scenario_paths:
        try:
            scenario = bio.expand(str(sp))
            scenarios.append(scenario)
        except Exception as e:
            print(f"Error loading scenario {sp}: {e}", file=sys.stderr)
            return 1

    # Create agents
    agent_names = spec.get("agents", ["random"])
    agents = {}
    for name in agent_names:
        try:
            agents[name] = _create_agent(name)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    # Seeds
    seeds = spec.get("seeds", [0])

    if verbose:
        print(f"Battery: {len(scenarios)} scenarios × {len(agents)} agents × {len(seeds)} seeds")
        print(f"  = {len(scenarios) * len(agents) * len(seeds)} experiments")

    # Progress callback
    def on_progress(p: BatteryProgress) -> None:
        if verbose:
            print(f"  [{p.completed}/{p.total}] {p.scenario} / {p.agent} / seed={p.seed}")

    # Run battery
    battery = ExperimentBattery(
        scenarios=scenarios,
        agents=agents,
        seeds=seeds,
        on_progress=on_progress,
    )

    result = battery.run()

    # Output
    if output_format == "csv":
        print(export_csv(result), end="")
    elif output_format == "json":
        print(export_json(result))
    else:
        _print_battery_summary(result)

    # Save if requested
    if save_path:
        actual = save_results(result, Path(save_path), metadata={"spec": spec_path})
        if verbose:
            print(f"\nResults saved to: {actual}")

    return 0


def _create_agent(agent_type: str, model: Optional[str] = None, seed: Optional[int] = None):
    """Create an agent by type name."""
    from alienbio.agent import RandomAgent, OracleAgent, HumanAgent, ConversationalLLMAgent

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


def _print_battery_summary(result) -> None:
    """Print a formatted battery summary to stdout."""
    print(f"\n{'=' * 60}")
    print(f"  BATTERY RESULTS")
    print(f"{'=' * 60}")
    print(f"  Total: {result.total}  Passed: {result.passed}  "
          f"Failed: {result.failed}  Pass Rate: {result.pass_rate*100:.1f}%")

    summary = result.summary()
    if summary:
        print(f"\n  {'Agent':<15} {'Total':<8} {'Passed':<8} {'Rate':<10}", end="")
        # Get score keys from first agent
        score_keys = sorted(summary[0].get("mean_scores", {}).keys())
        for key in score_keys:
            print(f" {key:<12}", end="")
        print()
        print(f"  {'-' * (41 + 13 * len(score_keys))}")

        for row in summary:
            print(f"  {row['agent']:<15} {row['total']:<8} {row['passed']:<8} "
                  f"{row['pass_rate']*100:>5.1f}%   ", end="")
            for key in score_keys:
                val = row["mean_scores"].get(key, 0.0)
                print(f" {val:>11.3f}", end="")
            print()

    # Per-scenario breakdown
    by_scenario = result.by_scenario()
    if len(by_scenario) > 1:
        print(f"\n  Per Scenario:")
        print(f"  {'Scenario':<20} {'Total':<8} {'Passed':<8} {'Rate':<10}")
        print(f"  {'-' * 46}")
        for name, entries in by_scenario.items():
            total = len(entries)
            passed = sum(1 for e in entries if e.result.passed)
            rate = passed / total if total else 0.0
            print(f"  {name:<20} {total:<8} {passed:<8} {rate*100:>5.1f}%")

    print(f"{'=' * 60}\n")


def battery_report_command(args: list[str], verbose: bool = False) -> int:
    """Generate a summary report from saved battery results.

    Usage:
        bio battery-report <results.yaml>
        bio battery-report <results.yaml> --csv
        bio battery-report <results.yaml> --json

    Args:
        args: Command arguments [results_path] [options]
        verbose: Enable verbose output

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    from alienbio.agent.results_store import load_results, export_csv, export_json

    results_path = None
    output_format = "console"
    agent_filter: Optional[str] = None
    scenario_filter: Optional[str] = None

    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--csv":
            output_format = "csv"
            i += 1
        elif arg == "--json":
            output_format = "json"
            i += 1
        elif arg == "--agent" and i + 1 < len(args):
            agent_filter = args[i + 1]
            i += 2
        elif arg == "--scenario" and i + 1 < len(args):
            scenario_filter = args[i + 1]
            i += 2
        elif not arg.startswith("--"):
            if results_path is None:
                results_path = arg
            i += 1
        else:
            i += 1

    if not results_path:
        print("Error: battery-report requires a results file", file=sys.stderr)
        print("Usage: bio battery-report <results.yaml> [--csv] [--json] "
              "[--agent name] [--scenario name]", file=sys.stderr)
        return 1

    path = Path(results_path)
    if not path.exists():
        print(f"Error: Results file not found: {results_path}", file=sys.stderr)
        return 1

    try:
        result = load_results(path)
    except (ValueError, yaml.YAMLError) as e:
        print(f"Error loading results: {e}", file=sys.stderr)
        return 1

    # Apply filters
    if agent_filter or scenario_filter:
        result = result.filter(agent=agent_filter, scenario=scenario_filter)
        if result.total == 0:
            print("No results match the specified filters.", file=sys.stderr)
            return 1

    if output_format == "csv":
        print(export_csv(result), end="")
    elif output_format == "json":
        print(export_json(result))
    else:
        _print_battery_summary(result)

    return 0
