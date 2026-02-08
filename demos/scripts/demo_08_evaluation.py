#!/usr/bin/env python3
"""Demo 08: Evaluation — difficulty curves and agent comparison."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib
matplotlib.use("Agg")

from _core import demo_08_evaluation
from alienbio.viz import save_or_show

OUTPUT = Path(__file__).resolve().parent.parent / "output" / "08_evaluation"


def main() -> None:
    fig_diff, fig_comp = demo_08_evaluation()
    save_or_show(fig_diff, OUTPUT / "difficulty_curves.png")
    save_or_show(fig_comp, OUTPUT / "comparison.png")
    print("demo_08_evaluation: OK")


if __name__ == "__main__":
    main()
