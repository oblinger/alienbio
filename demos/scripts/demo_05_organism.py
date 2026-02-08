#!/usr/bin/env python3
"""Demo 05: Organism — multi-compartment heatmap."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib
matplotlib.use("Agg")

from _shared import make_organism
from alienbio.viz import compartment_heatmap, save_or_show

OUTPUT = Path(__file__).resolve().parent.parent / "output" / "05_organism"


def main() -> None:
    organism = make_organism(seed=42)
    world_tl = organism.simulator.run(organism.state, steps=200, sample_every=5)

    fig = compartment_heatmap(world_tl, molecule_id=0, title="Organism: Molecule 0 Heatmap")
    save_or_show(fig, OUTPUT / "heatmap_mol0.png")

    print("demo_05_organism: OK")


if __name__ == "__main__":
    main()
