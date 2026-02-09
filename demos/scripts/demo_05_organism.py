#!/usr/bin/env python3
"""Demo 05: Organism — multi-compartment heatmap."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib
matplotlib.use("Agg")

from _core import demo_05_organism
from alienbio.viz import save_or_show

OUTPUT = Path(__file__).resolve().parent.parent / "output" / "05_organism"


def main() -> None:
    fig = demo_05_organism()
    save_or_show(fig, OUTPUT / "heatmap_mol0.png")
    print("demo_05_organism: OK")


if __name__ == "__main__":
    main()
