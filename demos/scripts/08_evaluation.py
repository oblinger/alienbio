#!/usr/bin/env python3
"""Demo 08: Agent Evaluation — How good is your agent?

Story: "Difficulty scaling, agent comparison, and leaderboards."
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from _shared import make_disease_system, oracle_agent, random_agent, zero_agent
from alienbio.bio import (
    AgentInterface,
    DiagnoseTask,
)
from alienbio.scenarios.difficulty_curve import DifficultySpec, measure_difficulty_curve
from alienbio.bio.comparison import AgentStats, ComparisonTable
from alienbio.viz import difficulty_curve_plot, agent_comparison_chart

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "output", "08_evaluation")


def main():
    print("=" * 60)
    print("Demo 08: Agent Evaluation")
    print("=" * 60)

    # Create tasks at different difficulty levels
    spec = DifficultySpec(levels=[])

    for level, label, n_candidates in [(1, "easy", 2), (2, "medium", 4), (3, "hard", 8)]:
        system, baseline, perturbs = make_disease_system(seed=level * 10)
        # Create diagnosis tasks with increasing candidates
        tasks = []
        for i in range(min(3, len(perturbs))):
            candidates = perturbs[:n_candidates] if n_candidates <= len(perturbs) else perturbs
            task = DiagnoseTask(candidates, applied_index=i % len(candidates))
            tasks.append(task)
        spec.add_level(level, label, tasks)

    # Measure difficulty curves for each agent
    system, _, _ = make_disease_system(seed=42)
    iface = AgentInterface(system)

    curves = []
    agents = [("oracle", oracle_agent), ("random", random_agent), ("zero", zero_agent)]

    for name, agent_fn in agents:
        curve = measure_difficulty_curve(spec, iface, agent_fn, agent_name=name)
        curves.append(curve)
        threshold = curve.capability_threshold(min_score=0.5)
        print(f"\n  {name}:")
        for pt in curve.points:
            print(f"    Level {pt.level} ({pt.label}): mean={pt.mean_score:.2f}, pass_rate={pt.pass_rate:.0%}")
        print(f"    Capability threshold: {threshold}")

    # Build comparison table
    all_stats = []
    for curve in curves:
        scores = []
        for pt in curve.points:
            scores.extend(pt.scores)
        n = len(scores) if scores else 1
        mean = sum(scores) / n if scores else 0.0
        import math
        var = sum((s - mean)**2 for s in scores) / n if scores else 0.0
        std = math.sqrt(var)
        pass_rate = sum(1 for s in scores if s >= 0.5) / n if scores else 0.0
        all_stats.append(AgentStats(
            agent_name=curve.agent_name,
            mean=mean, std=std,
            min=min(scores) if scores else 0.0,
            max=max(scores) if scores else 0.0,
            count=n, pass_rate=pass_rate,
        ))

    table = ComparisonTable(agents=all_stats)
    print(f"\n--- Rankings ---")
    for i, agent in enumerate(table.ranking):
        print(f"  #{i+1} {agent.agent_name}: mean={agent.mean:.2f} ± {agent.std:.2f}")

    # Plots
    difficulty_curve_plot(
        curves, threshold=0.5,
        title="Agent Evaluation: Difficulty Curves",
        save_path=os.path.join(OUTPUT_DIR, "difficulty_curves.png"),
    )
    agent_comparison_chart(
        table, title="Agent Evaluation: Comparison",
        save_path=os.path.join(OUTPUT_DIR, "comparison.png"),
    )

    print(f"\nPlots saved to {OUTPUT_DIR}/")
    print("Takeaway: The framework systematically evaluates agent capabilities.")
    return True


if __name__ == "__main__":
    main()
