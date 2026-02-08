#!/usr/bin/env python3
"""Demo 07: Skinning — alien terminology generation at different detail levels."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from _shared import make_homeostatic_system
from alienbio.bio import generate_description, generate_name_map

OUTPUT = Path(__file__).resolve().parent.parent / "output" / "07_skinning"


def main() -> None:
    system = make_homeostatic_system(seed=42)
    name_map = generate_name_map(system, seed=42)

    OUTPUT.mkdir(parents=True, exist_ok=True)

    for level in (1, 2, 3):
        desc = generate_description(
            system, detail_level=level, name_map=name_map, seed=42,
        )
        out_path = OUTPUT / f"description_level{level}.txt"
        out_path.write_text(desc)
        print(f"  Level {level}: {len(desc)} chars")

    print("demo_07_skinning: OK")


if __name__ == "__main__":
    main()
