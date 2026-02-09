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
        ("md", """\
# Demo 01: Quick Start

Build a simple 3-molecule alien biological system from scratch and watch it
converge to equilibrium. This walkthrough shows every step — defining atoms,
molecules, reactions, and assembling them into a runnable simulation."""),

        ("code", SETUP),

        ("md", """\
## Step 1 — Define the Chemistry

An AlienBio system starts with **atoms**, **molecules**, and **reactions**.
Here we create a minimal zynol↔brevix↔corthan system where molecules convert
between each other at concentration-dependent rates.

> Every object needs a `dat` (data-access token). In a full scenario these
> come from the catalog; for quick experiments the `MockDat` helper is enough."""),

        ("code", """\
from alienbio.bio import (
    AtomImpl, MoleculeImpl, ReactionImpl,
    ChemistryImpl, StateImpl, BioSystem, MockDat,
)

# One atom type — Zyrium
zr = AtomImpl("Zr", name="Zyrium", atomic_weight=14.7)

# Three alien molecules, each containing one Zyrium atom
zynol = MoleculeImpl("zynol", atoms={zr: 1}, bdepth=0, dat=MockDat("mol/zynol"))
brevix = MoleculeImpl("brevix", atoms={zr: 1}, bdepth=0, dat=MockDat("mol/brevix"))
corthan = MoleculeImpl("corthan", atoms={zr: 1}, bdepth=0, dat=MockDat("mol/corthan"))
"""),

        ("md", """\
### Reactions

Each reaction has a **rate function** that depends on the current concentrations.
The forward/reverse pairs create a homeostatic loop that drives the system
toward a stable equilibrium.

```
zynol ──0.10·[zynol]──▸ brevix ──0.08·[brevix]──▸ corthan
zynol ◂──0.05·[brevix]── brevix ◂──0.04·[corthan]── corthan
```"""),

        ("code", """\
# zynol→brevix and brevix→zynol (forward/reverse)
r_zb = ReactionImpl("r_zb", reactants={zynol: 1.0}, products={brevix: 1.0},
                     rate=lambda s: 0.10 * s["zynol"], dat=MockDat("rxn/r_zb"))
r_bz = ReactionImpl("r_bz", reactants={brevix: 1.0}, products={zynol: 1.0},
                     rate=lambda s: 0.05 * s["brevix"], dat=MockDat("rxn/r_bz"))

# brevix→corthan and corthan→brevix (forward/reverse)
r_bc = ReactionImpl("r_bc", reactants={brevix: 1.0}, products={corthan: 1.0},
                     rate=lambda s: 0.08 * s["brevix"], dat=MockDat("rxn/r_bc"))
r_cb = ReactionImpl("r_cb", reactants={corthan: 1.0}, products={brevix: 1.0},
                     rate=lambda s: 0.04 * s["corthan"], dat=MockDat("rxn/r_cb"))
"""),

        ("md", """\
## Step 2 — Assemble and Run

A `ChemistryImpl` bundles atoms, molecules, and reactions. A `StateImpl` sets
the initial concentrations. A `BioSystem` ties it together and can be stepped
forward in time."""),

        ("code", """\
chem = ChemistryImpl(
    "zbc",
    atoms={"Zr": zr},
    molecules={"zynol": zynol, "brevix": brevix, "corthan": corthan},
    reactions={"r_zb": r_zb, "r_bz": r_bz, "r_bc": r_bc, "r_cb": r_cb},
    dat=MockDat("chem/zbc"),
)

# Start with all concentration in zynol
state = StateImpl(chem, initial={"zynol": 10.0, "brevix": 0.0, "corthan": 0.0})
system = BioSystem(chem, state, dt=0.1)

# Run 500 time steps — returns a timeline (list of concentration snapshots)
timeline = system.run(500)

print(f"Steps: {len(timeline)}")
print(f"Final: { {m: round(system.state[m], 3) for m in system.state} }")
"""),

        ("md", """\
## Step 3 — Visualize

`alienbio.viz` provides ready-made plots. `concentration_trajectory` shows how
each molecule's concentration changes over time. `equilibrium_convergence` shows
the rolling variance — when it drops below a threshold the system has stabilized."""),

        ("md", "### Concentration Trajectories"),

        ("code", """\
from alienbio.viz import concentration_trajectory, equilibrium_convergence

concentration_trajectory(timeline, title="Quick Start: Trajectories");
"""),

        ("md", """\
### Equilibrium Convergence

The variance of each molecule's concentration over a trailing window.
Once all variances drop below a threshold, the system is at equilibrium."""),

        ("code", 'equilibrium_convergence(timeline, title="Quick Start: Convergence");'),
    ]))


# ── 02 Equilibrium ──────────────────────────────────────────────────────

def build_02():
    write("02_equilibrium", nb([
        ("md", """\
# Demo 02: Equilibrium & Stability

How do you know a biological system has reached equilibrium? This demo builds
the same zynol↔brevix↔corthan chemistry from Demo 01 (using the shared helper
this time), runs it longer, and uses `check_stability` to programmatically
detect when concentrations stop changing."""),

        ("code", SETUP),

        ("md", """\
## Build the System

`_shared.make_homeostatic_system` creates the same 3-molecule zynol↔brevix↔corthan
chemistry from Demo 01 (see that notebook for the full construction code). Here
we use a different seed and run for 1000 steps — long enough to be confident
about convergence."""),

        ("code", """\
from _shared import make_homeostatic_system

system = make_homeostatic_system(seed=99)
timeline = system.run(1000)

print(f"Steps: {len(timeline)}")
print(f"Final: { {m: round(system.state[m], 3) for m in system.state} }")
"""),

        ("md", """\
## Stability Check

`check_stability` computes the variance of each molecule's concentration over
a trailing **window** (here, the last 100 steps). If the maximum variance
across all molecules is below the **threshold**, the system is considered
stable.

The returned `StabilityResult` has:
- `stable` — `True` if all variances are below threshold
- `max_variance` — the largest variance seen across molecules"""),

        ("code", """\
from alienbio.bio import check_stability

result = check_stability(timeline, window=100, threshold=1e-4)
print(f"Stable: {result.stable}")
print(f"Max variance: {result.max_variance:.6f}")
"""),

        ("md", """\
## Trajectories

With seed=99 the initial transient is slightly different from Demo 01, but
the system still converges to the same equilibrium point (determined by the
rate constants, not the seed)."""),

        ("code", """\
from alienbio.viz import concentration_trajectory, equilibrium_convergence

concentration_trajectory(timeline, title="Equilibrium: Trajectories");
"""),

        ("md", """\
## Convergence Analysis

The convergence plot shows per-molecule rolling variance over the timeline.
By step ~400 the variance has dropped well below the 1e-4 threshold, matching
the `check_stability` result above."""),

        ("code", 'equilibrium_convergence(timeline, window=100, title="Equilibrium: Convergence");'),
    ]))


# ── 03 Perturbation ─────────────────────────────────────────────────────

def build_03():
    write("03_perturbation", nb([
        ("md", "# Demo 03: Perturbation & Recovery\n\nTwo experiments: spike recovery and reaction-removal drift."),
        ("code", SETUP),
        ("md", "## Spike Recovery\nInject +20 into zynol after 200 equilibration steps."),
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
        ("md", "## Concentration Envelope\nViable range for zynol: 1.0–8.0"),
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
