#!/usr/bin/env python3
"""Demo 06: Life & Survival — Life has rules.

Story: "Operating envelopes, predation, and reproduction thresholds."
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from _shared import make_homeostatic_system
from alienbio.bio import WorldStateImpl, CompartmentTreeImpl
from alienbio.scenarios.organism_features import OperatingEnvelope
from alienbio.viz import population_dynamics, envelope_timeline

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "output", "06_features")


def main():
    print("=" * 60)
    print("Demo 06: Life & Survival")
    print("=" * 60)

    # --- Population dynamics using single-compartment as proxy ---
    print("\n--- Population Dynamics ---")
    system = make_homeostatic_system(seed=42)
    # Treat molecules A and B as "prey" and "predator" populations
    timeline = system.run(steps=500)

    print(f"  Tracking A (prey proxy) and B (predator proxy)")
    print(f"  Initial: A={timeline[0]['A']:.2f}, B={timeline[0]['B']:.2f}")
    print(f"  Final:   A={timeline[-1]['A']:.2f}, B={timeline[-1]['B']:.2f}")

    population_dynamics(
        timeline, species=["A", "B"],
        title="Population Dynamics (Prey vs Predator Proxy)",
        save_path=os.path.join(OUTPUT_DIR, "population.png"),
    )

    # --- Operating envelope ---
    print("\n--- Operating Envelope ---")
    tree = CompartmentTreeImpl()
    root = tree.add_root("body")

    envelope = OperatingEnvelope()
    envelope.add(molecule_id=0, compartment_id=0, low=5.0, high=15.0)

    # Build world state timeline from single-compartment data
    world_states = []
    for state in timeline:
        ws = WorldStateImpl(tree, 3)
        for i, (name, _) in enumerate(state.items()):
            ws.set(0, i, state[name])
        world_states.append(ws)

    # Check violations
    n_violations = 0
    for ws in world_states:
        status = envelope.check(ws)
        if not status.viable:
            n_violations += 1

    print(f"  Envelope: molecule 0 in [{5.0}, {15.0}]")
    print(f"  Violations: {n_violations}/{len(world_states)} steps")

    envelope_timeline(
        world_states, envelope, molecule_id=0, compartment_id=0,
        title="Operating Envelope: Viability Over Time",
        save_path=os.path.join(OUTPUT_DIR, "envelope.png"),
    )

    print(f"\nPlots saved to {OUTPUT_DIR}/")
    print("Takeaway: Organisms must maintain homeostasis within survival bounds.")
    return True


if __name__ == "__main__":
    main()
