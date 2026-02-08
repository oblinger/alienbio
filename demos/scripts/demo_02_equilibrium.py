#!/usr/bin/env python3
"""Demo 02: Equilibrium — stability analysis and convergence."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib
matplotlib.use("Agg")

from _core import demo_02_equilibrium
from alienbio.viz import save_or_show

OUTPUT = Path(__file__).resolve().parent.parent / "output" / "02_equilibrium"


def main() -> None:
    result, fig_traj, fig_conv = demo_02_equilibrium()
    print(f"  Stable: {result.stable}, max variance: {result.max_variance:.6f}")
    save_or_show(fig_traj, OUTPUT / "trajectories.png")
    save_or_show(fig_conv, OUTPUT / "convergence.png")
    print("demo_02_equilibrium: OK")


if __name__ == "__main__":
    main()
