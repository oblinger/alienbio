#!/usr/bin/env python3
"""Demo 01: Quick Start — basic trajectory and convergence plots."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib
matplotlib.use("Agg")

from _shared import make_homeostatic_system
from alienbio.viz import concentration_trajectory, equilibrium_convergence, save_or_show

OUTPUT = Path(__file__).resolve().parent.parent / "output" / "01_quick_start"


def main() -> None:
    system = make_homeostatic_system(seed=42)
    timeline = system.run(500)

    fig1 = concentration_trajectory(timeline, title="Quick Start: Trajectories")
    save_or_show(fig1, OUTPUT / "trajectories.png")

    fig2 = equilibrium_convergence(timeline, title="Quick Start: Convergence")
    save_or_show(fig2, OUTPUT / "convergence.png")

    print("demo_01_quick_start: OK")


if __name__ == "__main__":
    main()
