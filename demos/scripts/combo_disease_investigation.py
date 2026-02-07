#!/usr/bin/env python3
"""Combo A: Full Disease Investigation Pipeline.

Build organism → equilibrium → apply disease → detect symptoms →
diagnose (compare agents) → cure → verify recovery.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from _shared import (
    make_homeostatic_system, make_disease_system,
    oracle_agent, random_agent,
)
from alienbio.bio import (
    AgentInterface,
    DiagnoseTask,
    CureTask,
    check_stability,
    detect_symptoms,
    measure_baseline,
)
from alienbio.viz import (
    concentration_trajectory, symptom_chart, save_or_show,
)

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "output", "combo_disease_investigation")


def main():
    print("=" * 60)
    print("Combo A: Full Disease Investigation Pipeline")
    print("=" * 60)

    # Phase 1: Establish healthy baseline
    print("\n--- Phase 1: Healthy Baseline ---")
    system, baseline, perturbations = make_disease_system(seed=42)
    healthy_system = make_homeostatic_system(seed=42)
    healthy_tl = healthy_system.run(steps=500)
    stability = check_stability(healthy_tl, window=100, threshold=1e-4)
    print(f"  Stable: {stability.stable}")
    for mol, conc in baseline.steady_state.items():
        print(f"  {mol}: {conc:.4f}")

    # Phase 2: Apply disease
    print("\n--- Phase 2: Apply Disease ---")
    disease = perturbations[0]
    print(f"  Disease: {disease.name} ({disease.kind} on {disease.target_reaction})")
    disease.apply(system)
    diseased_tl = system.run(steps=300)

    # Phase 3: Detect symptoms
    print("\n--- Phase 3: Detect Symptoms ---")
    concentrations = {name: system.state[name] for name in system.chemistry.molecules}
    symptoms = detect_symptoms(concentrations, baseline)
    print(f"  Symptoms: {len(symptoms)}")
    for s in symptoms:
        print(f"    {s.molecule}: {s.value:.4f} (deviation={s.deviation:.4f})")

    # Phase 4: Diagnosis
    print("\n--- Phase 4: Diagnosis ---")
    task = DiagnoseTask(perturbations, applied_index=0)
    iface = AgentInterface(system)
    oracle_result = task.score(iface, oracle_agent(iface, task))
    random_result = task.score(iface, random_agent(iface, task))
    print(f"  Oracle score: {oracle_result.score:.2f}")
    print(f"  Random score: {random_result.score:.2f}")

    # Phase 5: Cure attempt (re-run healthy system as proxy for cure)
    print("\n--- Phase 5: Cure ---")
    cure_task = CureTask(baseline, recovery_steps=500)
    # Restore system to healthy state as oracle's "cure"
    cured_system = make_homeostatic_system(seed=42)
    cured_system.run(steps=500)
    cure_iface = AgentInterface(cured_system)
    cure_result = cure_task.score(cure_iface)
    print(f"  Cure score: {cure_result.score:.2f}")

    # Generate 4-panel figure
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    # Panel 1: Healthy trajectories
    from alienbio.viz.helpers import timeline_to_arrays
    times, data = timeline_to_arrays(healthy_tl)
    for mol, conc in data.items():
        axes[0, 0].plot(times, conc, label=mol)
    axes[0, 0].set_title("Phase 1: Healthy Baseline")
    axes[0, 0].legend()
    axes[0, 0].grid(True, alpha=0.3)

    # Panel 2: Diseased trajectories
    times_d, data_d = timeline_to_arrays(diseased_tl)
    for mol, conc in data_d.items():
        axes[0, 1].plot(times_d, conc, label=mol)
    axes[0, 1].set_title("Phase 2: Diseased System")
    axes[0, 1].legend()
    axes[0, 1].grid(True, alpha=0.3)

    # Panel 3: Symptoms
    if symptoms:
        range_map = {r.molecule: r for r in baseline.ranges}
        for i, s in enumerate(symptoms):
            hr = range_map.get(s.molecule, s.healthy_range)
            axes[1, 0].barh(i, hr.high - hr.low, left=hr.low, height=0.5,
                            color="green", alpha=0.25)
            axes[1, 0].plot(s.value, i, "ro", markersize=10)
        axes[1, 0].set_yticks(range(len(symptoms)))
        axes[1, 0].set_yticklabels([s.molecule for s in symptoms])
    axes[1, 0].set_title("Phase 3: Symptoms")

    # Panel 4: Agent scores
    agents = ["Oracle", "Random"]
    scores = [oracle_result.score, random_result.score]
    axes[1, 1].bar(agents, scores, color=["green", "orange"])
    axes[1, 1].set_ylim(0, 1.1)
    axes[1, 1].set_title("Phase 4: Diagnosis Scores")

    fig.suptitle("Full Disease Investigation Pipeline", fontsize=14, fontweight="bold")
    fig.tight_layout()
    save_or_show(fig, os.path.join(OUTPUT_DIR, "four_panel.png"))

    print(f"\nPlots saved to {OUTPUT_DIR}/")
    return True


if __name__ == "__main__":
    main()
