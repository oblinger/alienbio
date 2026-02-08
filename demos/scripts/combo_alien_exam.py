#!/usr/bin/env python3
"""Combo: Alien Exam — skinned difficulty curves and leaderboard."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib
matplotlib.use("Agg")

from _shared import make_disease_system, oracle_agent, random_agent, zero_agent
from alienbio.bio import (
    AgentInterface,
    BioSystem,
    TestSuite,
    compare,
    generate_diagnosis_task,
    generate_name_map,
    run_suite,
    skin_task_description,
)
from alienbio.viz import difficulty_curve_plot, agent_comparison_chart, save_or_show

OUTPUT = Path(__file__).resolve().parent.parent / "output" / "combo_alien_exam"


def main() -> None:
    system, _, perturbations = make_disease_system(seed=42)
    name_map = generate_name_map(system, seed=42)

    agents = {"oracle": oracle_agent, "random": random_agent, "zero": zero_agent}
    difficulties = [1, 2, 3, 4]
    curves: dict[str, List[tuple[int, float]]] = {name: [] for name in agents}

    for diff in difficulties:
        for agent_name, agent_fn in agents.items():
            suite = TestSuite(name=f"{agent_name}_d{diff}")
            for trial in range(5):
                task = generate_diagnosis_task(
                    system, perturbations, difficulty=diff, seed=diff * 100 + trial,
                )
                # Skin the task description for demonstration
                skin_task_description(task, name_map)
                interface = AgentInterface(
                    BioSystem(system.chemistry, system.state.copy(), dt=0.1),
                )
                suite.add(interface, task)
            results = run_suite(suite, agent_fn)
            curves[agent_name].append((diff, results.mean_score))

    fig1 = difficulty_curve_plot(curves, title="Alien Exam: Difficulty Curves")
    save_or_show(fig1, OUTPUT / "difficulty_curves.png")

    # Leaderboard at difficulty 3
    all_results = {}
    for agent_name, agent_fn in agents.items():
        suite = TestSuite(name=agent_name)
        for trial in range(10):
            task = generate_diagnosis_task(
                system, perturbations, difficulty=3, seed=300 + trial,
            )
            interface = AgentInterface(
                BioSystem(system.chemistry, system.state.copy(), dt=0.1),
            )
            suite.add(interface, task)
        all_results[agent_name] = run_suite(suite, agent_fn)

    table = compare(all_results)
    fig2 = agent_comparison_chart(table, title="Alien Exam: Leaderboard")
    save_or_show(fig2, OUTPUT / "leaderboard.png")

    print("combo_alien_exam: OK")


if __name__ == "__main__":
    main()
