#!/usr/bin/env python3
"""Build all demo notebooks from definitions.

Notebooks import from ``_core`` for all computation, keeping code cells
minimal and in sync with the standalone scripts.
"""

from __future__ import annotations

from pathlib import Path

import nbformat

HERE = Path(__file__).resolve().parent

# Common setup code injected into every notebook
SETUP = """\
import sys
from pathlib import Path

# Ensure alienbio is importable
_root = Path(".").resolve().parent.parent / "src"
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))
_demos = Path(".").resolve().parent
if str(_demos) not in sys.path:
    sys.path.insert(0, str(_demos))

%matplotlib inline
"""


def nb(cells: list[tuple[str, str]]) -> nbformat.NotebookNode:
    """Create a notebook from a list of (type, source) pairs."""
    notebook = nbformat.v4.new_notebook()
    for cell_type, source in cells:
        if cell_type == "md":
            notebook.cells.append(nbformat.v4.new_markdown_cell(source))
        else:
            notebook.cells.append(nbformat.v4.new_code_cell(source))
    return notebook


def write(name: str, notebook: nbformat.NotebookNode) -> None:
    path = HERE / f"{name}.ipynb"
    nbformat.write(notebook, str(path))
    print(f"  wrote {path.name}")


# ── 01 Quick Start ──────────────────────────────────────────────────────

def build_01():
    write("01_quick_start", nb([
        ("md", "# Demo 01: Quick Start\n\nA 3-molecule homeostatic system (A↔B↔C) converging to equilibrium."),
        ("code", SETUP),
        ("code", "from _core import demo_01_quick_start\nfig_traj, fig_conv = demo_01_quick_start()"),
        ("md", "## Concentration Trajectories"),
        ("code", "fig_traj"),
        ("md", "## Equilibrium Convergence\nVariance drops below threshold as the system stabilizes."),
        ("code", "fig_conv"),
    ]))


# ── 02 Equilibrium ──────────────────────────────────────────────────────

def build_02():
    write("02_equilibrium", nb([
        ("md", "# Demo 02: Equilibrium & Stability\n\nRun to equilibrium and analyze stability using variance over a trailing window."),
        ("code", SETUP),
        ("code", "from _core import demo_02_equilibrium\nresult, fig_traj, fig_conv = demo_02_equilibrium()\nprint(f'Stable: {result.stable}, max variance: {result.max_variance:.6f}')"),
        ("md", "## Trajectories"),
        ("code", "fig_traj"),
        ("md", "## Convergence Analysis"),
        ("code", "fig_conv"),
    ]))


# ── 03 Perturbation ─────────────────────────────────────────────────────

def build_03():
    write("03_perturbation", nb([
        ("md", "# Demo 03: Perturbation & Recovery\n\nTwo experiments: spike recovery and reaction-removal drift."),
        ("code", SETUP),
        ("md", "## Spike Recovery\nInject +20 into molecule A after 200 equilibration steps."),
        ("code", "from _core import demo_03_spike_recovery, demo_03_drift\nfig_spike = demo_03_spike_recovery()\nfig_spike"),
        ("md", "## Reaction Removal Drift\nRemove the B→C reaction and observe the system drifting."),
        ("code", "fig_drift = demo_03_drift()\nfig_drift"),
    ]))


# ── 04 Disease ──────────────────────────────────────────────────────────

def build_04():
    write("04_disease", nb([
        ("md", "# Demo 04: Disease Investigation\n\nApply a perturbation, observe the diseased system, and detect symptoms."),
        ("code", SETUP),
        ("code", "from _core import demo_04_disease\nsymptoms, fig_traj, fig_symp = demo_04_disease()\nprint(f'Detected {len(symptoms)} symptom(s)')"),
        ("md", "## Diseased Trajectories"),
        ("code", "fig_traj"),
        ("md", "## Symptom Detection"),
        ("code", "fig_symp"),
    ]))


# ── 05 Organism ─────────────────────────────────────────────────────────

def build_05():
    write("05_organism", nb([
        ("md", "# Demo 05: Multi-Compartment Organism\n\nGenerate a 3-organ organism and visualize molecule transport across compartments."),
        ("code", SETUP),
        ("code", "from _core import demo_05_organism\nfig = demo_05_organism()"),
        ("md", "## Compartment Heatmap\nMolecule 0 concentration across organs over time."),
        ("code", "fig"),
    ]))


# ── 06 Features ─────────────────────────────────────────────────────────

def build_06():
    write("06_features", nb([
        ("md", "# Demo 06: Life & Survival\n\nPopulation dynamics and concentration envelopes."),
        ("code", SETUP),
        ("code", "from _core import demo_06_features\nfig_pop, fig_env = demo_06_features()"),
        ("md", "## Population Dynamics"),
        ("code", "fig_pop"),
        ("md", "## Concentration Envelope\nViable range for molecule A: 1.0–8.0"),
        ("code", "fig_env"),
    ]))


# ── 07 Skinning ─────────────────────────────────────────────────────────

def build_07():
    write("07_skinning", nb([
        ("md", "# Demo 07: Generating & Skinning\n\nReplace real molecule/reaction names with opaque alien terminology at 3 detail levels."),
        ("code", SETUP),
        ("code", "from _core import demo_07_skinning\ndescriptions = demo_07_skinning()\nfor level, desc in descriptions.items():\n    print(f'--- Level {level} ---')\n    print(desc)\n    print()"),
    ]))


# ── 08 Evaluation ───────────────────────────────────────────────────────

def build_08():
    write("08_evaluation", nb([
        ("md", "# Demo 08: Agent Evaluation\n\nOracle, random, and zero agents evaluated across difficulty levels."),
        ("code", SETUP),
        ("code", "from _core import demo_08_evaluation\nfig_diff, fig_comp = demo_08_evaluation()"),
        ("md", "## Difficulty Curves"),
        ("code", "fig_diff"),
        ("md", "## Agent Comparison\nAll agents at difficulty 2."),
        ("code", "fig_comp"),
    ]))


# ── Combo: Disease Investigation ────────────────────────────────────────

def build_combo_disease():
    write("combo_disease_investigation", nb([
        ("md", "# Combo: Disease Investigation\n\n4-panel figure: healthy equilibrium → disease → symptoms → diagnosis."),
        ("code", SETUP),
        ("code", "from _core import combo_disease_investigation\nfig = combo_disease_investigation()\nfig"),
    ]))


# ── Combo: Alien Exam ───────────────────────────────────────────────────

def build_combo_exam():
    write("combo_alien_exam", nb([
        ("md", "# Combo: Alien Exam\n\nAgents evaluated on skinned (opaque) diagnosis tasks at multiple difficulty levels."),
        ("code", SETUP),
        ("code", "from _core import combo_alien_exam\nfig_diff, fig_lead = combo_alien_exam()"),
        ("md", "## Difficulty Curves (Skinned Tasks)"),
        ("code", "fig_diff"),
        ("md", "## Leaderboard (Difficulty 3)"),
        ("code", "fig_lead"),
    ]))


# ── Combo: Ecosystem ────────────────────────────────────────────────────

def build_combo_ecosystem():
    write("combo_ecosystem", nb([
        ("md", "# Combo: Ecosystem\n\nMulti-compartment organism heatmap and concentration envelope violations."),
        ("code", SETUP),
        ("code", "from _core import combo_ecosystem\nfig_heat, fig_env = combo_ecosystem()"),
        ("md", "## Organism Heatmap"),
        ("code", "fig_heat"),
        ("md", "## Envelope Violations"),
        ("code", "fig_env"),
    ]))


# ── Main ────────────────────────────────────────────────────────────────

def main():
    print("Building notebooks...")
    build_01()
    build_02()
    build_03()
    build_04()
    build_05()
    build_06()
    build_07()
    build_08()
    build_combo_disease()
    build_combo_exam()
    build_combo_ecosystem()
    print("Done — 11 notebooks created.")


if __name__ == "__main__":
    main()
