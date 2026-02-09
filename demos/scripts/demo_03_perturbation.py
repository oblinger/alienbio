#!/usr/bin/env python3
"""Demo 03: Perturbation — spike recovery and reaction-removal drift."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib
matplotlib.use("Agg")

from _core import demo_03_spike_recovery, demo_03_drift
from alienbio.viz import save_or_show

OUTPUT = Path(__file__).resolve().parent.parent / "output" / "03_perturbation"


def main() -> None:
    fig_spike = demo_03_spike_recovery()
    save_or_show(fig_spike, OUTPUT / "spike_recovery.png")

    fig_drift = demo_03_drift()
    save_or_show(fig_drift, OUTPUT / "drift.png")

    print("demo_03_perturbation: OK")


if __name__ == "__main__":
    main()
