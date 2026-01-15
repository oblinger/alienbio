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
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import yaml


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

    Args:
        args: Command arguments [path] [--seed N] [--agent TYPE] [--model NAME]
        verbose: Enable verbose output

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    from alienbio import bio
    from alienbio.agent import run_experiment

    # Parse arguments
    scenario_path, options = _parse_args(args)

    if not scenario_path:
        print("Error: run command requires a scenario path", file=sys.stderr)
        print("Usage: bio run <scenario_path> [--seed N] [--agent TYPE] [--model NAME]", file=sys.stderr)
        print("\nAgent types: anthropic, openai, random, oracle, human", file=sys.stderr)
        return 1

    path = Path(scenario_path)

    # Handle relative paths - look in catalog/scenarios if not found directly
    if not path.exists():
        for catalog_dir in ["catalog/scenarios", "catalog/jobs", "catalog"]:
            catalog_path = Path(catalog_dir) / path
            if catalog_path.exists():
                path = catalog_path
                break
        else:
            print(f"Error: Path not found: {scenario_path}", file=sys.stderr)
            return 1

    # Parse options
    seed_str = options.get("seed")
    seed = int(seed_str) if seed_str else None
    agent_type = options.get("agent", "random")
    model = options.get("model")

    if verbose:
        print(f"Running: {path}")
        print(f"  Agent: {agent_type}")
        if model:
            print(f"  Model: {model}")
        if seed is not None:
            print(f"  Seed: {seed}")

    # Load scenario
    try:
        # Check for index.yaml or load directly
        if path.is_dir():
            index_file = path / "index.yaml"
            if index_file.exists():
                scenario = bio.expand(str(path))
            else:
                print(f"Error: No index.yaml found in: {path}", file=sys.stderr)
                return 1
        else:
            scenario = bio.expand(str(path))

        # Create agent
        agent = _create_agent(agent_type, model=model, seed=seed)

        # Run experiment
        results = run_experiment(scenario, agent, seed=seed)

        # Print results
        print("\n" + "=" * 60)
        print("EXPERIMENT RESULTS")
        print("=" * 60)
        print(f"Scenario: {results.scenario}")
        print(f"Status: {results.status}")
        print(f"Passed: {results.passed}")
        print(f"Seed: {results.seed}")
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
