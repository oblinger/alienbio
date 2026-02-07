#!/usr/bin/env python3
"""Combo C: Ecosystem Under Stress.

Multi-compartment organism with operating envelope + perturbation.
Monitor viability through environmental stress and recovery.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from _shared import make_organism
from alienbio.bio import WorldStateImpl
from alienbio.scenarios.organism_features import OperatingEnvelope
from alienbio.viz import compartment_heatmap, envelope_timeline, save_or_show

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "output", "combo_ecosystem")


def _copy_world_state(ws):
    """Copy a WorldStateImpl for the timeline."""
    copy = WorldStateImpl(
        ws.tree, ws.num_molecules,
        initial_concentrations=list(ws._concentrations),
        initial_multiplicities=list(ws._multiplicities),
    )
    return copy


def main():
    print("=" * 60)
    print("Combo C: Ecosystem Under Stress")
    print("=" * 60)

    organism, chem = make_organism(seed=42)
    mol_names = list(chem.molecules.keys())

    # Set up operating envelope on key molecule in organ compartments
    envelope = OperatingEnvelope()
    for comp_id in range(1, organism.num_compartments):
        envelope.add(molecule_id=0, compartment_id=comp_id, low=0.5, high=8.0)

    print(f"\nOrganism: {organism.num_compartments} compartments, "
          f"{organism.num_transport_links} transport links")
    print(f"Envelope: {mol_names[0]} in [0.5, 8.0] for compartments 1-{organism.num_compartments - 1}")

    # Phase 1: Run to equilibrium
    print("\n--- Phase 1: Run to equilibrium (200 steps) ---")
    timeline = []
    for _ in range(200):
        organism.simulator.step(organism.state)
        timeline.append(_copy_world_state(organism.state))

    violations_before = sum(
        1 for ws in timeline[-50:] if not envelope.check(ws).viable
    )
    print(f"  Violations in last 50 steps: {violations_before}")

    # Phase 2: Apply stress — spike a molecule in compartment 1
    print("\n--- Phase 2: Apply toxin spike ---")
    spike_comp = 1
    spike_mol = 0
    spike_amount = 20.0
    current = organism.state.get(spike_comp, spike_mol)
    organism.state.set(spike_comp, spike_mol, current + spike_amount)
    print(f"  Spiked {mol_names[spike_mol]} in compartment {spike_comp} by +{spike_amount}")

    # Phase 3: Monitor recovery
    print("\n--- Phase 3: Recovery (300 steps) ---")
    for _ in range(300):
        organism.simulator.step(organism.state)
        timeline.append(_copy_world_state(organism.state))

    violations_after = sum(
        1 for ws in timeline[-50:] if not envelope.check(ws).viable
    )
    print(f"  Violations in last 50 steps: {violations_after}")

    # Summary
    total_violations = sum(1 for ws in timeline if not envelope.check(ws).viable)
    print(f"\n  Total violations across {len(timeline)} steps: {total_violations}")

    # Final state
    print(f"\nFinal state:")
    for comp in range(organism.num_compartments):
        concs = organism.state.get_compartment(comp)
        parts = [f"{mol_names[i]}={concs[i]:.2f}" for i in range(len(mol_names))]
        print(f"  Compartment {comp}: {', '.join(parts)}")

    # Plots
    compartment_heatmap(
        timeline, molecule_id=0,
        compartment_names={i: f"Comp {i}" for i in range(organism.num_compartments)},
        title=f"Ecosystem: {mol_names[0]} Distribution Under Stress",
        save_path=os.path.join(OUTPUT_DIR, "heatmap.png"),
    )
    envelope_timeline(
        timeline, envelope, molecule_id=0, compartment_id=spike_comp,
        title=f"Ecosystem: Envelope Viability (Comp {spike_comp})",
        save_path=os.path.join(OUTPUT_DIR, "envelope.png"),
    )

    print(f"\nPlots saved to {OUTPUT_DIR}/")
    return True


if __name__ == "__main__":
    main()
