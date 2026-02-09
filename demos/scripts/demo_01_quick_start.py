#!/usr/bin/env python3
"""Demo 01: Quick Start — basic trajectory and convergence plots."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib
matplotlib.use("Agg")

from _core import demo_01_quick_start
from alienbio.viz import save_or_show

OUTPUT = Path(__file__).resolve().parent.parent / "output" / "01_quick_start"


def main() -> None:
    fig_traj, fig_conv = demo_01_quick_start()
    save_or_show(fig_traj, OUTPUT / "trajectories.png")
    save_or_show(fig_conv, OUTPUT / "convergence.png")
    print("demo_01_quick_start: OK")


if __name__ == "__main__":
    main()
