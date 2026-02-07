#!/usr/bin/env python3
"""Demo 02: Equilibrium & Stability — How alien biochemistry self-regulates.

Story: "Watch the system find balance."
Run the homeostatic system and analyze convergence in detail.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from _shared import make_homeostatic_system
from alienbio.bio import check_stability
from alienbio.viz import concentration_trajectory, equilibrium_convergence

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "output", "02_equilibrium")


def main():
    print("=" * 60)
    print("Demo 02: Equilibrium & Stability")
    print("=" * 60)

    system = make_homeostatic_system(seed=42)

    # Run with different time horizons
    for steps in [50, 200, 500]:
        tl = system.run(steps)
        system2 = make_homeostatic_system(seed=42)
        tl2 = system2.run(steps)
        stab = check_stability(tl2, window=min(50, steps // 2), threshold=1e-4)
        print(f"\n  Steps={steps}: stable={stab.stable}, max_var={stab.max_variance:.6f}")

    # Full run for plotting
    system = make_homeostatic_system(seed=42)
    timeline = system.run(steps=500)
    stability = check_stability(timeline, window=100, threshold=1e-4)

    final = timeline[-1]
    print(f"\nFinal concentrations:")
    for name, _ in final.items():
        print(f"  {name}: {final[name]:.4f}")
    print(f"\nUnstable molecules: {stability.unstable_molecules or 'None'}")
    print(f"Per-molecule variance:")
    for mol, var in stability.variance.items():
        print(f"  {mol}: {var:.8f}")

    concentration_trajectory(
        timeline, title="Equilibrium: Concentration Trajectories",
        save_path=os.path.join(OUTPUT_DIR, "trajectories.png"),
    )
    equilibrium_convergence(
        timeline, stability, title="Equilibrium: Convergence Analysis",
        save_path=os.path.join(OUTPUT_DIR, "convergence.png"),
    )

    print(f"\nPlots saved to {OUTPUT_DIR}/")
    print("Takeaway: Homeostatic systems converge to steady state.")
    return True


if __name__ == "__main__":
    main()
