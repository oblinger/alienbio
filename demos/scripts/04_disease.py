#!/usr/bin/env python3
"""Demo 04: Disease Investigation — From symptoms to diagnosis to cure.

Story: "Alien diseases: detect, diagnose, and cure."
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from _shared import make_disease_system, oracle_agent, random_agent
from alienbio.bio import (
    AgentInterface,
    BioSystem,
    DiagnoseTask,
    CureTask,
    StateImpl,
    detect_symptoms,
    measure_baseline,
)
from alienbio.viz import symptom_chart, concentration_trajectory

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "output", "04_disease")


def main():
    print("=" * 60)
    print("Demo 04: Disease Investigation")
    print("=" * 60)

    # Build and measure healthy system
    system, baseline, perturbations = make_disease_system(seed=42)

    print(f"\nHealthy baseline:")
    for mol, conc in baseline.steady_state.items():
        print(f"  {mol}: {conc:.4f}")

    # Apply first perturbation as the "disease"
    disease = perturbations[0]
    print(f"\nApplying disease: {disease.name} ({disease.kind} on {disease.target_reaction})")

    # Record healthy trajectory first
    healthy_system, _, _ = make_disease_system(seed=42)
    healthy_tl = healthy_system.run(steps=300)

    # Apply disease and run
    disease.apply(system)
    diseased_tl = system.run(steps=300)

    # Detect symptoms
    concentrations = {name: system.state[name] for name in system.chemistry.molecules}
    symptoms = detect_symptoms(concentrations, baseline)
    print(f"\nSymptoms detected: {len(symptoms)}")
    for s in symptoms:
        direction = "HIGH" if s.value > s.healthy_range.high else "LOW"
        print(f"  {s.molecule}: {s.value:.4f} ({direction}, deviation={s.deviation:.4f})")

    # Diagnosis task
    print("\n--- Diagnosis ---")
    task = DiagnoseTask(perturbations, applied_index=0)
    iface = AgentInterface(system)

    oracle_pred = oracle_agent(iface, task)
    oracle_result = task.score(iface, oracle_pred)
    random_pred = random_agent(iface, task)
    random_result = task.score(iface, random_pred)

    print(f"  Oracle: predicted={oracle_pred}, score={oracle_result.score:.2f}")
    print(f"  Random: predicted={random_pred}, score={random_result.score:.2f}")

    # Plots
    symptom_chart(
        symptoms, baseline, title="Disease: Symptom Chart",
        save_path=os.path.join(OUTPUT_DIR, "symptoms.png"),
    )
    concentration_trajectory(
        diseased_tl, title="Disease: Diseased System Trajectories",
        save_path=os.path.join(OUTPUT_DIR, "diseased_trajectories.png"),
    )

    print(f"\nPlots saved to {OUTPUT_DIR}/")
    print("Takeaway: Disease = structural perturbation; symptoms = observable shifts.")
    return True


if __name__ == "__main__":
    main()
