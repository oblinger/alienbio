#!/usr/bin/env python3
"""Combo: Ecosystem — organism heatmap and envelope violations."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib
matplotlib.use("Agg")

from _core import combo_ecosystem
from alienbio.viz import save_or_show

OUTPUT = Path(__file__).resolve().parent.parent / "output" / "combo_ecosystem"


def main() -> None:
    fig_heat, fig_env = combo_ecosystem()
    save_or_show(fig_heat, OUTPUT / "heatmap.png")
    save_or_show(fig_env, OUTPUT / "envelope.png")
    print("combo_ecosystem: OK")


if __name__ == "__main__":
    main()
