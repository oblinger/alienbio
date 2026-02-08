#!/usr/bin/env python3
"""Combo: Disease Investigation — 4-panel: equilibrium, disease, diagnose, cure."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib
matplotlib.use("Agg")

from _core import combo_disease_investigation
from alienbio.viz import save_or_show

OUTPUT = Path(__file__).resolve().parent.parent / "output" / "combo_disease_investigation"


def main() -> None:
    fig = combo_disease_investigation()
    save_or_show(fig, OUTPUT / "four_panel.png")
    print("combo_disease_investigation: OK")


if __name__ == "__main__":
    main()
