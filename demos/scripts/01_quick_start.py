#!/usr/bin/env python3
"""Demo 01: Quick Start — From chemistry to simulation in a few lines.

Story: "Meet your first alien biology system."
Build a 3-molecule homeostatic system, run to equilibrium, and visualize.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from _shared import make_homeostatic_system
from alienbio.bio import check_stability
from alienbio.viz import concentration_trajectory, equilibrium_convergence

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "output", "01_quick_start")


def main():
    print("=" * 60)
    print("Demo 01: Quick Start")
    print("=" * 60)

    # Build system and run to equilibrium
    system = make_homeostatic_system(seed=42)
    timeline = system.run(steps=500)

    # Check stability
    stability = check_stability(timeline, window=100, threshold=1e-4)

    # Print numeric summary
    final = timeline[-1]
    print(f"\nFinal concentrations after 500 steps:")
    for mol_name, _ in final.items():
        print(f"  {mol_name}: {final[mol_name]:.4f}")
    print(f"\nStable: {stability.stable}")
    print(f"Max variance: {stability.max_variance:.6f}")
    print(f"Steps run: {stability.steps_run}")

    # Generate plots
    concentration_trajectory(
        timeline, title="Quick Start: Concentration Trajectories",
        save_path=os.path.join(OUTPUT_DIR, "trajectories.png"),
    )
    equilibrium_convergence(
        timeline, stability, title="Quick Start: Equilibrium Convergence",
        save_path=os.path.join(OUTPUT_DIR, "convergence.png"),
    )

    print(f"\nPlots saved to {OUTPUT_DIR}/")
    print("Takeaway: Systems self-regulate through reaction kinetics.")
    return True


if __name__ == "__main__":
    main()
