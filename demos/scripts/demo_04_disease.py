#!/usr/bin/env python3
"""Demo 04: Disease — perturbation effects and symptom detection."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib
matplotlib.use("Agg")

from _shared import make_disease_system
from alienbio.bio import BioSystem, detect_symptoms
from alienbio.viz import concentration_trajectory, symptom_chart, save_or_show

OUTPUT = Path(__file__).resolve().parent.parent / "output" / "04_disease"


def main() -> None:
    system, baseline, perturbations = make_disease_system(seed=42)

    # Apply first perturbation
    pert = perturbations[0]
    diseased = BioSystem(system.chemistry, system.state.copy(), dt=0.1)
    pert.apply(diseased)
    diseased_tl = diseased.run(300)

    fig1 = concentration_trajectory(diseased_tl, title=f"Diseased: {pert.name}")
    save_or_show(fig1, OUTPUT / "diseased_trajectories.png")

    # Detect symptoms
    concs = {m: diseased.state[m] for m in diseased.state}
    symptoms = detect_symptoms(concs, baseline)
    print(f"  Detected {len(symptoms)} symptom(s)")

    fig2 = symptom_chart(symptoms, baseline, title="Symptoms")
    save_or_show(fig2, OUTPUT / "symptoms.png")

    print("demo_04_disease: OK")


if __name__ == "__main__":
    main()
