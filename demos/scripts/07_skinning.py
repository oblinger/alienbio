#!/usr/bin/env python3
"""Demo 07: Generating & Skinning — Making biology alien.

Story: "Skin a system with alien names, generate opaque descriptions."
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from _shared import make_homeostatic_system
from alienbio.scenarios.skinning import (
    generate_name_map,
    generate_description,
)

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "output", "07_skinning")


def main():
    print("=" * 60)
    print("Demo 07: Generating & Skinning")
    print("=" * 60)

    system = make_homeostatic_system(seed=42)

    # Generate alien name mapping
    name_map = generate_name_map(system, seed=42)
    print(f"\nName mapping ({len(name_map)} entries):")
    for internal, alien in name_map.items():
        print(f"  {internal:20s} -> {alien}")

    # Generate descriptions at different detail levels
    for level in [1, 2, 3]:
        desc = generate_description(system, detail_level=level, name_map=name_map, seed=42)
        print(f"\n{'='*40}")
        print(f"Description (detail level {level}):")
        print(f"{'='*40}")
        print(desc[:500] + ("..." if len(desc) > 500 else ""))

    # Save descriptions to files
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    for level in [1, 2, 3]:
        desc = generate_description(system, detail_level=level, name_map=name_map, seed=42)
        path = os.path.join(OUTPUT_DIR, f"description_level{level}.txt")
        with open(path, "w") as f:
            f.write(desc)

    print(f"\nDescriptions saved to {OUTPUT_DIR}/")
    print("Takeaway: Skinning makes biology opaque for agent evaluation.")
    return True


if __name__ == "__main__":
    main()
