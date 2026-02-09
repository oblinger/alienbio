#!/usr/bin/env python3
"""Demo 07: Skinning — alien terminology generation at different detail levels."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from _core import demo_07_skinning

OUTPUT = Path(__file__).resolve().parent.parent / "output" / "07_skinning"


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    descriptions = demo_07_skinning()
    for level, desc in descriptions.items():
        out_path = OUTPUT / f"description_level{level}.txt"
        out_path.write_text(desc)
        print(f"  Level {level}: {len(desc)} chars")
    print("demo_07_skinning: OK")


if __name__ == "__main__":
    main()
