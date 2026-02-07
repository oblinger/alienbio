#!/usr/bin/env python3
"""Run all demo scripts and report results."""

import importlib
import importlib.util
import os
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

DEMOS = [
    "01_quick_start",
    "02_equilibrium",
    "03_perturbation",
    "04_disease",
    "05_organism",
    "06_features",
    "07_skinning",
    "08_evaluation",
    "combo_disease_investigation",
    "combo_alien_exam",
    "combo_ecosystem",
]


def main():
    import matplotlib
    matplotlib.use("Agg")

    script_dir = os.path.dirname(os.path.abspath(__file__))
    results = []

    for name in DEMOS:
        print(f"\n{'#' * 70}")
        print(f"# Running: {name}")
        print(f"{'#' * 70}\n")
        try:
            spec = importlib.util.spec_from_file_location(
                name, os.path.join(script_dir, f"{name}.py"))
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            ok = module.main()
            results.append((name, "PASS" if ok else "FAIL"))
        except Exception:
            traceback.print_exc()
            results.append((name, "ERROR"))

    # Summary
    print(f"\n{'=' * 60}")
    print("DEMO SUITE SUMMARY")
    print(f"{'=' * 60}")
    for name, status in results:
        icon = "OK" if status == "PASS" else "FAIL"
        print(f"  [{icon:4s}] {name}")

    passed = sum(1 for _, s in results if s == "PASS")
    print(f"\n{passed}/{len(results)} demos passed.")
    return passed == len(results)


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
