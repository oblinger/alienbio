#!/usr/bin/env python3
"""Demo 03: Perturbation & Recovery — What happens when you poke it?

Story: "Inject a spike. Remove a reaction. See what breaks."
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from _shared import make_homeostatic_system
from alienbio.bio import inject_spike
from alienbio.viz import perturbation_response, concentration_trajectory

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "output", "03_perturbation")


def main():
    print("=" * 60)
    print("Demo 03: Perturbation & Recovery")
    print("=" * 60)

    # --- Spike injection ---
    print("\n--- Spike Injection ---")
    system = make_homeostatic_system(seed=42)
    baseline_system = make_homeostatic_system(seed=42)

    # Run baseline
    baseline_tl = baseline_system.run(steps=300)

    # Run to steady state, then spike
    system.run(steps=200)
    result = inject_spike(system, molecule="A", amount=20.0,
                          recovery_steps=300, tolerance=0.15)

    # Run the spiked system forward
    perturbed_tl = system.run(steps=300)

    print(f"  Recovered: {result.recovered}")
    print(f"  Max deviation: {result.max_deviation:.4f}")
    print(f"  Recovery step: {result.recovery_step}")

    perturbation_response(
        baseline_tl, perturbed_tl, result,
        title="Perturbation: Spike Injection & Recovery",
        save_path=os.path.join(OUTPUT_DIR, "spike_recovery.png"),
    )

    # --- Reaction removal (drift) ---
    print("\n--- Reaction Removal ---")
    system2 = make_homeostatic_system(seed=42)
    system2.run(steps=200)  # reach steady state

    # Remove degradation of A — should cause A to drift up
    rxn = system2.chemistry.reactions["degrade_a"]
    rxn.set_rate(0.0)
    drift_tl = system2.run(steps=300)

    final = drift_tl[-1]
    print(f"  After removing degrade_a:")
    for name, _ in final.items():
        print(f"    {name}: {final[name]:.4f}")

    concentration_trajectory(
        drift_tl, title="Perturbation: Reaction Removal Drift",
        save_path=os.path.join(OUTPUT_DIR, "drift.png"),
    )

    print(f"\nPlots saved to {OUTPUT_DIR}/")
    print("Takeaway: Healthy systems recover from spikes but drift from structural damage.")
    return True


if __name__ == "__main__":
    main()
