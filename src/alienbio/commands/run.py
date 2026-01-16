"""Run command: Execute a scenario with an agent.

Usage:
    bio run <scenario_path>
    bio run <scenario_path> --seed 42
    bio run <scenario_path> --agent anthropic
    bio run <scenario_path> --agent anthropic --model claude-opus-4-20250514
    bio run <scenario_path> --agent random --seed 42

Agent types:
    anthropic - Anthropic Claude API (requires API key)
    openai    - OpenAI API (requires API key)
    random    - Random action selection
    oracle    - Agent with ground truth access
    human     - Interactive CLI agent

DAT Execution:
    When the target path is a DAT (a folder with _spec_.yaml),
    the run command creates a sandboxed Bio context for execution:

    1. A new Bio instance is created as an isolated sandbox
    2. The sandbox's current_dat is set to the executing DAT's path
    3. All execution occurs within this sandboxed context
    4. Results are saved via dvc_dat's _result_.yaml mechanism

    This ensures:
    - Each DAT execution is fully self-contained
    - No accidental mixing with the global bio singleton state
    - Results are stored with the DAT for reproducibility

DAT File Structure:
    A Bio DAT folder contains:
    - _spec_.yaml       Required: dvc_dat specification (kind, do function)
    - _result_.yaml     Generated: execution results from bio run
    - index.yaml        Bio content: default object for bio.fetch()

    Optional components may be added for specific DAT types.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional

import yaml


def _is_dat(path: Path) -> bool:
    """Check if path is a DAT (has _spec_.yaml).

    A DAT folder is identified by the presence of _spec_.yaml,
    which is the dvc_dat specification file.

    Args:
        path: Path to check

    Returns:
        True if path is a DAT folder
    """
    if not path.is_dir():
        return False
    spec_file = path / "_spec_.yaml"
    return spec_file.exists()


def _save_result(
    dat_path: Path,
    results: Any,
    agent_type: str,
    model: Optional[str],
    seed: Optional[int],
) -> None:
    """Save execution results to the DAT's _result_.yaml.

    This follows the dvc_dat convention where _result_.yaml contains
    the mutable execution results for a DAT.

    Args:
        dat_path: Path to the DAT folder
        results: ExperimentResults object
        agent_type: Type of agent used
        model: Model name if LLM agent
        seed: Random seed used
    """
    from datetime import datetime

    result_data = {
        "start_time": datetime.now().isoformat(),
        "success": results.passed,
        "execution_time": 0.0,  # TODO: track actual execution time
        "end_time": datetime.now().isoformat(),
        "run_metadata": {
            "scenario": results.scenario,
            "seed": seed,
            "agent_type": agent_type,
            "model": model,
            "status": results.status,
            "passed": results.passed,
            "incomplete_reason": results.incomplete_reason,
            "scores": results.scores,
            "trace_summary": {
                "total_cost": results.trace.total_cost,
                "action_count": len(results.trace),
            },
        },
    }

    result_file = dat_path / "_result_.yaml"
    with open(result_file, "w") as f:
        yaml.dump(result_data, f, default_flow_style=False, sort_keys=False)


def _parse_args(args: list[str]) -> tuple[Optional[str], dict[str, str]]:
    """Parse command arguments into path and options.

    Args:
        args: Command arguments

    Returns:
        Tuple of (path, options_dict)
    """
    path = None
    options: dict[str, str] = {}
    i = 0

    while i < len(args):
        arg = args[i]
        if arg.startswith("--"):
            key = arg[2:]
            if i + 1 < len(args) and not args[i + 1].startswith("--"):
                options[key] = args[i + 1]
                i += 2
            else:
                options[key] = "true"
                i += 1
        else:
            if path is None:
                path = arg
            i += 1

    return path, options


def _create_agent(
    agent_type: str,
    model: Optional[str] = None,
    seed: Optional[int] = None
):
    """Create an agent of the specified type.

    Args:
        agent_type: One of anthropic, openai, random, oracle, human
        model: Model name for LLM agents
        seed: Random seed (for random agent)

    Returns:
        Agent instance
    """
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


def run_command(args: list[str], verbose: bool = False) -> int:
    """Run a scenario with an agent.

    When target is a DAT, creates a sandboxed Bio for isolated execution.
    Results are saved to the DAT folder as _result_.yaml.

    Args:
        args: Command arguments [path] [--seed N] [--agent TYPE] [--model NAME]
        verbose: Enable verbose output

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    from alienbio import bio
    from alienbio.spec_lang.bio import Bio
    from alienbio.agent import run_experiment

    # Parse arguments
    scenario_path, options = _parse_args(args)

    if not scenario_path:
        print("Error: run command requires a scenario path", file=sys.stderr)
        print("Usage: bio run <scenario_path> [--seed N] [--agent TYPE] [--model NAME]", file=sys.stderr)
        print("\nAgent types: anthropic, openai, random, oracle, human", file=sys.stderr)
        return 1

    path = Path(scenario_path).resolve()

    # Handle relative paths - look in catalog/scenarios if not found directly
    if not path.exists():
        for catalog_dir in ["catalog/scenarios", "catalog/jobs", "catalog"]:
            catalog_path = Path(catalog_dir) / scenario_path
            if catalog_path.exists():
                path = catalog_path.resolve()
                break
        else:
            print(f"Error: Path not found: {scenario_path}", file=sys.stderr)
            return 1

    # Parse options
    seed_str = options.get("seed")
    seed = int(seed_str) if seed_str else None
    agent_type = options.get("agent", "random")
    model = options.get("model")

    # Detect if target is a DAT
    is_dat_execution = _is_dat(path)

    if verbose:
        print(f"Running: {path}")
        if is_dat_execution:
            print("  Mode: DAT (sandboxed execution)")
        print(f"  Agent: {agent_type}")
        if model:
            print(f"  Model: {model}")
        if seed is not None:
            print(f"  Seed: {seed}")

    # Create Bio context - sandboxed for DAT execution, global otherwise
    if is_dat_execution:
        # Create sandboxed Bio for isolated DAT execution
        sandbox = Bio()
        sandbox.cd(path)  # Set current_dat to the executing DAT
        active_bio = sandbox
        if verbose:
            print(f"  Sandbox current_dat: {path}")
    else:
        # Use global bio singleton for non-DAT execution
        active_bio = bio

    # Load and run scenario
    try:
        # Check for index.yaml or load directly
        if path.is_dir():
            index_file = path / "index.yaml"
            if index_file.exists():
                scenario = active_bio.expand(str(path))
            else:
                print(f"Error: No index.yaml found in: {path}", file=sys.stderr)
                return 1
        else:
            scenario = active_bio.expand(str(path))

        # Create agent
        agent = _create_agent(agent_type, model=model, seed=seed)

        # Run experiment
        results = run_experiment(scenario, agent, seed=seed)

        # Save results to DAT folder if this is DAT execution
        if is_dat_execution:
            _save_result(path, results, agent_type, model, seed)
            if verbose:
                print(f"  Results saved to: {path / '_result_.yaml'}")

        # Print results
        print("\n" + "=" * 60)
        print("EXPERIMENT RESULTS")
        print("=" * 60)
        print(f"Scenario: {results.scenario}")
        print(f"Status: {results.status}")
        print(f"Passed: {results.passed}")
        print(f"Seed: {results.seed}")
        if is_dat_execution:
            print(f"DAT: {path}")
        print("\nScores:")
        for name, value in results.scores.items():
            print(f"  {name}: {value:.3f}")
        print("=" * 60)

        return 0 if results.passed else 1

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if verbose:
            import traceback
            traceback.print_exc()
        return 1
