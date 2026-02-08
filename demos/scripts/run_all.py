#!/usr/bin/env python3
"""Run all demo scripts and print pass/fail summary."""

from __future__ import annotations

import importlib
import importlib.util
import sys
import traceback
from pathlib import Path

# Ensure package and demos are importable
_root = Path(__file__).resolve().parent.parent.parent / "src"
_demos = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))
if str(_demos) not in sys.path:
    sys.path.insert(0, str(_demos))

SCRIPTS = [
    "demo_01_quick_start",
    "demo_02_equilibrium",
    "demo_03_perturbation",
    "demo_04_disease",
    "demo_05_organism",
    "demo_06_features",
    "demo_07_skinning",
    "demo_08_evaluation",
    "combo_disease_investigation",
    "combo_alien_exam",
    "combo_ecosystem",
]


def main() -> None:
    scripts_dir = Path(__file__).resolve().parent

    # Set matplotlib backend before any scripts import it
    import matplotlib
    matplotlib.use("Agg")

    passed = 0
    failed = 0
    skipped = 0
    results: list[tuple[str, str]] = []

    for name in SCRIPTS:
        try:
            # Import and run each script's main()
            script_path = scripts_dir / f"{name}.py"
            if not script_path.exists():
                results.append((name, "MISSING"))
                failed += 1
                continue

            spec = importlib.util.spec_from_file_location(name, script_path)
            assert spec is not None and spec.loader is not None
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            module.main()
            results.append((name, "PASS"))
            passed += 1
        except Exception as e:
            results.append((name, f"FAIL: {e}"))
            traceback.print_exc()
            failed += 1

    # Optional LLM demo
    try:
        opt_path = scripts_dir / "optional_llm_agent.py"
        spec = importlib.util.spec_from_file_location("optional_llm_agent", opt_path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.main()
        results.append(("optional_llm_agent", "PASS"))
        passed += 1
    except Exception as e:
        if "SKIPPED" in str(e) or "ANTHROPIC_API_KEY" in str(e):
            results.append(("optional_llm_agent", "SKIPPED"))
            skipped += 1
        else:
            results.append(("optional_llm_agent", f"FAIL: {e}"))
            failed += 1

    # Summary
    print("\n" + "=" * 50)
    print("DEMO SUITE RESULTS")
    print("=" * 50)
    for name, status in results:
        marker = "+" if status == "PASS" else ("-" if "FAIL" in status else "~")
        print(f"  [{marker}] {name}: {status}")
    print(f"\nTotal: {passed} passed, {failed} failed, {skipped} skipped")
    print("=" * 50)

    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
