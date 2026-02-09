#!/usr/bin/env python3
"""Combo: Alien Exam — skinned difficulty curves and leaderboard."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib
matplotlib.use("Agg")

from _core import combo_alien_exam
from alienbio.viz import save_or_show

OUTPUT = Path(__file__).resolve().parent.parent / "output" / "combo_alien_exam"


def main() -> None:
    fig_diff, fig_lead = combo_alien_exam()
    save_or_show(fig_diff, OUTPUT / "difficulty_curves.png")
    save_or_show(fig_lead, OUTPUT / "leaderboard.png")
    print("combo_alien_exam: OK")


if __name__ == "__main__":
    main()
