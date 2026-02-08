#!/usr/bin/env python3
"""Demo 02: Equilibrium — stability analysis and convergence."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib
matplotlib.use("Agg")

from _shared import make_homeostatic_system
from alienbio.bio import check_stability
from alienbio.viz import concentration_trajectory, equilibrium_convergence, save_or_show

OUTPUT = Path(__file__).resolve().parent.parent / "output" / "02_equilibrium"


def main() -> None:
    system = make_homeostatic_system(seed=99)
    timeline = system.run(1000)

    result = check_stability(timeline, window=100, threshold=1e-4)
    print(f"  Stable: {result.stable}, max variance: {result.max_variance:.6f}")

    fig1 = concentration_trajectory(timeline, title="Equilibrium: Trajectories")
    save_or_show(fig1, OUTPUT / "trajectories.png")

    fig2 = equilibrium_convergence(timeline, window=100, title="Equilibrium: Convergence")
    save_or_show(fig2, OUTPUT / "convergence.png")

    print("demo_02_equilibrium: OK")


if __name__ == "__main__":
    main()
