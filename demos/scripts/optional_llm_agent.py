#!/usr/bin/env python3
"""Optional: LLM Agent demo — uses Anthropic API if ANTHROPIC_API_KEY is set."""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from _shared import make_disease_system
from alienbio.bio import (
    AgentInterface,
    BioSystem,
    generate_diagnosis_task,
    run_experiment,
)


def main() -> None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("optional_llm_agent: SKIPPED (no ANTHROPIC_API_KEY)")
        return

    try:
        import anthropic
    except ImportError:
        print("optional_llm_agent: SKIPPED (anthropic package not installed)")
        return

    system, _, perturbations = make_disease_system(seed=42)
    task = generate_diagnosis_task(system, perturbations, difficulty=1, seed=42)
    interface = AgentInterface(BioSystem(system.chemistry, system.state.copy(), dt=0.1))

    def llm_agent(iface: AgentInterface, tsk: object) -> int:
        """Simple LLM agent that asks Claude to diagnose."""
        from alienbio.bio import DiagnoseTask
        if not isinstance(tsk, DiagnoseTask):
            return 0

        measurements = iface.available_measurements()
        concs = iface.measure("all_concentrations")
        candidates = tsk.candidates

        prompt = (
            f"You are diagnosing an alien biological system.\n"
            f"Current concentrations: {concs}\n"
            f"Candidate perturbations:\n"
        )
        for i, c in enumerate(candidates):
            prompt += f"  {i}: {c.name} ({c.kind})\n"
        prompt += "Which candidate index (0-based) was applied? Reply with just the number."

        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=10,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()
        try:
            return int(text)
        except ValueError:
            return 0

    result = run_experiment(interface, task, llm_agent)
    print(f"  LLM agent score: {result.score}")
    print("optional_llm_agent: OK")


if __name__ == "__main__":
    main()
