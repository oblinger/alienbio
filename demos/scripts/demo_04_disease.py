#!/usr/bin/env python3
"""Demo 04: Disease — perturbation effects and symptom detection."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib
matplotlib.use("Agg")

from _core import demo_04_disease
from alienbio.viz import save_or_show

OUTPUT = Path(__file__).resolve().parent.parent / "output" / "04_disease"


def main() -> None:
    symptoms, fig_traj, fig_symp = demo_04_disease()
    print(f"  Detected {len(symptoms)} symptom(s)")
    save_or_show(fig_traj, OUTPUT / "diseased_trajectories.png")
    save_or_show(fig_symp, OUTPUT / "symptoms.png")
    print("demo_04_disease: OK")


if __name__ == "__main__":
    main()
