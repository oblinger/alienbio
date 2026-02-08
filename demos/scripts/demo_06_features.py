#!/usr/bin/env python3
"""Demo 06: Features — population dynamics and concentration envelope."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib
matplotlib.use("Agg")

from _shared import make_homeostatic_system
from alienbio.viz import population_dynamics, envelope_timeline, save_or_show

OUTPUT = Path(__file__).resolve().parent.parent / "output" / "06_features"


def main() -> None:
    # Population dynamics (use molecules as "species")
    system = make_homeostatic_system(seed=7)
    timeline = system.run(500)

    fig1 = population_dynamics(timeline, species=["A", "B", "C"],
                               title="Population Dynamics")
    save_or_show(fig1, OUTPUT / "population.png")

    # Envelope: viable range for molecule A
    envelope = {"A": (1.0, 8.0)}
    fig2 = envelope_timeline(timeline, envelope, "A",
                             title="Concentration Envelope")
    save_or_show(fig2, OUTPUT / "envelope.png")

    print("demo_06_features: OK")


if __name__ == "__main__":
    main()
