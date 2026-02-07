#!/usr/bin/env python3
"""Combo B: The Alien Biology Exam.

Skin a system with alien names → generate descriptions →
run difficulty-scaled diagnosis tasks → compare agents on opaque tasks.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from _shared import make_disease_system, oracle_agent, random_agent, zero_agent
from alienbio.bio import AgentInterface, DiagnoseTask
from alienbio.scenarios.skinning import generate_name_map, generate_description
from alienbio.scenarios.difficulty_curve import DifficultySpec, measure_difficulty_curve
from alienbio.bio.comparison import AgentStats, ComparisonTable
from alienbio.viz import difficulty_curve_plot, agent_comparison_chart

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "output", "combo_alien_exam")


def main():
    print("=" * 60)
    print("Combo B: The Alien Biology Exam")
    print("=" * 60)

    # Build and skin a system
    system, baseline, perturbs = make_disease_system(seed=42)
    name_map = generate_name_map(system, seed=42)

    print("\n--- Alien Biology ---")
    desc = generate_description(system, detail_level=2, name_map=name_map, seed=42)
    print(desc)

    # Build difficulty-scaled diagnosis tasks using skinned system
    spec = DifficultySpec(levels=[])
    for level, label, n_cand in [(1, "easy", 2), (2, "medium", 4), (3, "hard", 8)]:
        tasks = []
        for i in range(3):
            candidates = perturbs[:n_cand] if n_cand <= len(perturbs) else perturbs
            task = DiagnoseTask(candidates, applied_index=i % len(candidates))
            tasks.append(task)
        spec.add_level(level, label, tasks)

    # Run agents
    iface = AgentInterface(system)
    agents = [("oracle", oracle_agent), ("random", random_agent), ("zero", zero_agent)]
    curves = []

    for name, fn in agents:
        curve = measure_difficulty_curve(spec, iface, fn, agent_name=name)
        curves.append(curve)

    # Print results with alien context
    print("\n--- Exam Results ---")
    print(f"(Agent names are opaque; biology uses alien terminology)")
    for curve in curves:
        threshold = curve.capability_threshold(min_score=0.5)
        print(f"\n  {curve.agent_name}:")
        for pt in curve.points:
            print(f"    {pt.label}: score={pt.mean_score:.2f}")
        print(f"    Max difficulty passed: {threshold}")

    # Build leaderboard
    import math
    all_stats = []
    for curve in curves:
        scores = [s for pt in curve.points for s in pt.scores]
        n = len(scores) if scores else 1
        mean = sum(scores) / n if scores else 0.0
        var = sum((s - mean)**2 for s in scores) / n if scores else 0.0
        pass_rate = sum(1 for s in scores if s >= 0.5) / n if scores else 0.0
        all_stats.append(AgentStats(
            curve.agent_name, mean, math.sqrt(var),
            min(scores) if scores else 0.0, max(scores) if scores else 0.0,
            n, pass_rate,
        ))
    table = ComparisonTable(agents=all_stats)

    print(f"\n--- Leaderboard ---")
    for i, a in enumerate(table.ranking):
        print(f"  #{i+1} {a.agent_name}: {a.mean:.2f} ± {a.std:.2f}")

    difficulty_curve_plot(
        curves, title="Alien Exam: Difficulty Curves",
        save_path=os.path.join(OUTPUT_DIR, "difficulty_curves.png"),
    )
    agent_comparison_chart(
        table, title="Alien Exam: Agent Leaderboard",
        save_path=os.path.join(OUTPUT_DIR, "leaderboard.png"),
    )

    print(f"\nPlots saved to {OUTPUT_DIR}/")
    return True


if __name__ == "__main__":
    main()
