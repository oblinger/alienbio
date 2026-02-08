#!/usr/bin/env python3
"""Combo: Disease Investigation — 4-panel: equilibrium, disease, diagnose, cure."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from _shared import make_disease_system, oracle_agent
from alienbio.bio import (
    AgentInterface,
    BioSystem,
    detect_symptoms,
    generate_diagnosis_task,
    run_experiment,
)
from alienbio.viz import save_or_show

OUTPUT = Path(__file__).resolve().parent.parent / "output" / "combo_disease_investigation"


def main() -> None:
    system, baseline, perturbations = make_disease_system(seed=42)

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("Disease Investigation", fontsize=14)

    # Panel 1: Healthy equilibrium
    healthy = BioSystem(system.chemistry, system.state.copy(), dt=0.1)
    healthy_tl = healthy.run(300)
    for mol in list(healthy_tl[0]):
        vals = [s[mol] for s in healthy_tl]
        axes[0, 0].plot(range(len(vals)), vals, label=mol)
    axes[0, 0].set_title("1. Healthy Equilibrium")
    axes[0, 0].set_xlabel("Time Step")
    axes[0, 0].set_ylabel("Concentration")
    axes[0, 0].legend(fontsize="small")

    # Panel 2: Diseased system
    pert = perturbations[0]
    diseased = BioSystem(system.chemistry, system.state.copy(), dt=0.1)
    pert.apply(diseased)
    diseased_tl = diseased.run(300)
    for mol in list(diseased_tl[0]):
        vals = [s[mol] for s in diseased_tl]
        axes[0, 1].plot(range(len(vals)), vals, label=mol)
    axes[0, 1].set_title(f"2. Diseased ({pert.name})")
    axes[0, 1].set_xlabel("Time Step")
    axes[0, 1].set_ylabel("Concentration")
    axes[0, 1].legend(fontsize="small")

    # Panel 3: Symptoms
    concs = {m: diseased.state[m] for m in diseased.state}
    symptoms = detect_symptoms(concs, baseline)
    if symptoms:
        names = [s.molecule for s in symptoms]
        values = [s.value for s in symptoms]
        range_map = {r.molecule: r for r in baseline.ranges}
        for i, s in enumerate(symptoms):
            r = range_map.get(s.molecule)
            if r is not None:
                axes[1, 0].barh(i, r.high - r.low, left=r.low, height=0.4,
                                color="green", alpha=0.2)
        axes[1, 0].barh(range(len(names)), values, height=0.4, color="red", alpha=0.7)
        axes[1, 0].set_yticks(range(len(names)))
        axes[1, 0].set_yticklabels(names)
    axes[1, 0].set_title("3. Symptoms Detected")
    axes[1, 0].set_xlabel("Concentration")

    # Panel 4: Diagnosis result
    task = generate_diagnosis_task(system, perturbations, difficulty=2, seed=42)
    interface = AgentInterface(BioSystem(system.chemistry, system.state.copy(), dt=0.1))
    result = run_experiment(interface, task, oracle_agent)
    candidate_names = [p.name for p in task.candidates]
    colors = ["green" if i == task.correct_index else "gray"
              for i in range(len(candidate_names))]
    axes[1, 1].barh(range(len(candidate_names)), [1] * len(candidate_names),
                     color=colors, alpha=0.7)
    axes[1, 1].set_yticks(range(len(candidate_names)))
    axes[1, 1].set_yticklabels(candidate_names, fontsize=8)
    axes[1, 1].set_title(f"4. Diagnosis (score={result.score:.1f})")

    fig.tight_layout()
    save_or_show(fig, OUTPUT / "four_panel.png")
    print("combo_disease_investigation: OK")


if __name__ == "__main__":
    main()
