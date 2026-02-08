#!/usr/bin/env python3
"""Combo: Ecosystem — organism heatmap and envelope violations."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib
matplotlib.use("Agg")

from _shared import make_homeostatic_system, make_organism
from alienbio.viz import compartment_heatmap, envelope_timeline, save_or_show

OUTPUT = Path(__file__).resolve().parent.parent / "output" / "combo_ecosystem"


def main() -> None:
    # Organism heatmap
    organism = make_organism(seed=42)
    world_tl = organism.simulator.run(organism.state, steps=200, sample_every=5)

    fig1 = compartment_heatmap(world_tl, molecule_id=0,
                               title="Ecosystem: Compartment Heatmap")
    save_or_show(fig1, OUTPUT / "heatmap.png")

    # Envelope violations
    system = make_homeostatic_system(seed=42)
    timeline = system.run(500)
    envelope = {"A": (2.0, 6.0)}

    fig2 = envelope_timeline(timeline, envelope, "A",
                             title="Ecosystem: Envelope Violations")
    save_or_show(fig2, OUTPUT / "envelope.png")

    print("combo_ecosystem: OK")


if __name__ == "__main__":
    main()
