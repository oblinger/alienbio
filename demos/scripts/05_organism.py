#!/usr/bin/env python3
"""Demo 05: Multi-Compartment Organisms — Real organisms have structure.

Story: "Generate a multi-organ organism and watch transport dynamics."
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from _shared import make_organism
from alienbio.viz import compartment_heatmap

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "output", "05_organism")


def main():
    print("=" * 60)
    print("Demo 05: Multi-Compartment Organisms")
    print("=" * 60)

    organism, chem = make_organism(seed=42)

    print(f"\nOrganism structure:")
    print(f"  Compartments: {organism.num_compartments}")
    print(f"  Transport links: {organism.num_transport_links}")
    for link in organism.transport_links:
        print(f"    {link.source} -> {link.target} (mol={link.molecule_id}, rate={link.rate:.4f})")

    # Run simulation
    world_timeline = []
    for step in range(200):
        organism.simulator.step(organism.state)
        # Copy state for timeline
        from alienbio.bio import WorldStateImpl
        ws_copy = WorldStateImpl(
            organism.state.tree, organism.state.num_molecules,
            initial_concentrations=list(organism.state._concentrations),
            initial_multiplicities=list(organism.state._multiplicities),
        )
        world_timeline.append(ws_copy)

    # Print final state per compartment
    mol_names = list(chem.molecules.keys())
    print(f"\nFinal state (step 200):")
    for comp in range(organism.num_compartments):
        concs = organism.state.get_compartment(comp)
        parts = [f"{mol_names[i]}={concs[i]:.2f}" for i in range(len(mol_names))]
        print(f"  Compartment {comp}: {', '.join(parts)}")

    # Plot heatmap for first molecule
    compartment_heatmap(
        world_timeline, molecule_id=0,
        title=f"Organism: {mol_names[0]} Across Compartments",
        save_path=os.path.join(OUTPUT_DIR, "heatmap_mol0.png"),
    )

    print(f"\nPlots saved to {OUTPUT_DIR}/")
    print("Takeaway: Transport dynamics create spatial gradients across compartments.")
    return True


if __name__ == "__main__":
    main()
