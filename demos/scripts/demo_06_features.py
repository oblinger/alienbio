#!/usr/bin/env python3
"""Demo 06: Features — population dynamics and concentration envelope."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib
matplotlib.use("Agg")

from _core import demo_06_features
from alienbio.viz import save_or_show

OUTPUT = Path(__file__).resolve().parent.parent / "output" / "06_features"


def main() -> None:
    fig_pop, fig_env = demo_06_features()
    save_or_show(fig_pop, OUTPUT / "population.png")
    save_or_show(fig_env, OUTPUT / "envelope.png")
    print("demo_06_features: OK")


if __name__ == "__main__":
    main()
