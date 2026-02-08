#!/usr/bin/env python3
"""Build all demo notebooks from definitions."""

from __future__ import annotations

import sys
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
        ("code", """\
from _shared import make_homeostatic_system
from alienbio.viz import concentration_trajectory, equilibrium_convergence

system = make_homeostatic_system(seed=42)
timeline = system.run(500)
print(f"Final: { {m: round(system.state[m], 3) for m in system.state} }")
"""),
        ("md", "## Concentration Trajectories"),
        ("code", "concentration_trajectory(timeline, title='Quick Start: Trajectories');"),
        ("md", "## Equilibrium Convergence\nVariance drops below threshold as the system stabilizes."),
        ("code", "equilibrium_convergence(timeline, title='Quick Start: Convergence');"),
    ]))


# ── 02 Equilibrium ──────────────────────────────────────────────────────

def build_02():
    write("02_equilibrium", nb([
        ("md", "# Demo 02: Equilibrium & Stability\n\nRun to equilibrium and analyze stability using variance over a trailing window."),
        ("code", SETUP),
        ("code", """\
from _shared import make_homeostatic_system
from alienbio.bio import check_stability
from alienbio.viz import concentration_trajectory, equilibrium_convergence

system = make_homeostatic_system(seed=99)
timeline = system.run(1000)
result = check_stability(timeline, window=100, threshold=1e-4)
print(f"Stable: {result.stable}, max variance: {result.max_variance:.6f}")
"""),
        ("md", "## Trajectories"),
        ("code", "concentration_trajectory(timeline, title='Equilibrium: Trajectories');"),
        ("md", "## Convergence Analysis"),
        ("code", "equilibrium_convergence(timeline, window=100, title='Equilibrium: Convergence');"),
    ]))


# ── 03 Perturbation ─────────────────────────────────────────────────────

def build_03():
    write("03_perturbation", nb([
        ("md", "# Demo 03: Perturbation & Recovery\n\nTwo experiments: spike recovery and reaction-removal drift."),
        ("code", SETUP),
        ("md", "## Spike Recovery\nInject +20 into molecule A after 200 equilibration steps."),
        ("code", """\
from _shared import make_homeostatic_system
from alienbio.viz import perturbation_response

sys_base = make_homeostatic_system(seed=42)
sys_base.run(200)
baseline_tl = sys_base.run(100)

sys_spike = make_homeostatic_system(seed=42)
sys_spike.run(200)
sys_spike.state["A"] = sys_spike.state["A"] + 20.0
spike_tl = sys_spike.run(100)

perturbation_response(baseline_tl, spike_tl, title="Spike Recovery");
"""),
        ("md", "## Reaction Removal Drift\nRemove the B→C reaction and observe the system drifting."),
        ("code", """\
from alienbio.bio import BioSystem, ChemistryImpl, StateImpl

class _MockDat:
    def __init__(self, p): self._path = p
    def get_path_name(self): return self._path
    def get_path(self): return f"/tmp/{self._path}"
    def save(self): pass

sys_drift_base = make_homeostatic_system(seed=42)
sys_drift_base.run(200)
drift_baseline_tl = sys_drift_base.run(200)

sys_orig = make_homeostatic_system(seed=42)
remaining = {n: r for n, r in sys_orig.chemistry.reactions.items() if n != "r_bc"}
modified_chem = ChemistryImpl(
    "abc_no_rbc", atoms=sys_orig.chemistry.atoms,
    molecules=sys_orig.chemistry.molecules, reactions=remaining,
    dat=_MockDat("chem/abc_no_rbc"),
)
init_concs = {m: sys_drift_base.state[m] for m in sys_drift_base.state}
modified_state = StateImpl(modified_chem, initial=init_concs)
sys_drift = BioSystem(modified_chem, modified_state, dt=0.1)
drift_tl = sys_drift.run(200)

perturbation_response(drift_baseline_tl, drift_tl, title="Reaction Removal Drift");
"""),
    ]))


# ── 04 Disease ──────────────────────────────────────────────────────────

def build_04():
    write("04_disease", nb([
        ("md", "# Demo 04: Disease Investigation\n\nApply a perturbation, observe the diseased system, and detect symptoms."),
        ("code", SETUP),
        ("code", """\
from _shared import make_disease_system
from alienbio.bio import BioSystem, detect_symptoms
from alienbio.viz import concentration_trajectory, symptom_chart

system, baseline, perturbations = make_disease_system(seed=42)
pert = perturbations[0]
print(f"Applying: {pert.name} ({pert.kind})")
"""),
        ("md", "## Diseased Trajectories"),
        ("code", """\
diseased = BioSystem(system.chemistry, system.state.copy(), dt=0.1)
pert.apply(diseased)
diseased_tl = diseased.run(300)
concentration_trajectory(diseased_tl, title=f"Diseased: {pert.name}");
"""),
        ("md", "## Symptom Detection"),
        ("code", """\
concs = {m: diseased.state[m] for m in diseased.state}
symptoms = detect_symptoms(concs, baseline)
print(f"Detected {len(symptoms)} symptom(s):")
for s in symptoms:
    print(f"  {s.molecule}: {s.value:.3f} (range: {s.healthy_range.low:.3f}–{s.healthy_range.high:.3f})")
symptom_chart(symptoms, baseline, title="Symptoms");
"""),
    ]))


# ── 05 Organism ─────────────────────────────────────────────────────────

def build_05():
    write("05_organism", nb([
        ("md", "# Demo 05: Multi-Compartment Organism\n\nGenerate a 3-organ organism and visualize molecule transport across compartments."),
        ("code", SETUP),
        ("code", """\
from _shared import make_organism
from alienbio.viz import compartment_heatmap

organism = make_organism(seed=42)
print(f"Compartments: {organism.num_compartments}, Transport links: {organism.num_transport_links}")
world_tl = organism.simulator.run(organism.state, steps=200, sample_every=5)
"""),
        ("md", "## Compartment Heatmap\nMolecule 0 concentration across organs over time."),
        ("code", "compartment_heatmap(world_tl, molecule_id=0, title='Organism: Molecule 0 Heatmap');"),
    ]))


# ── 06 Features ─────────────────────────────────────────────────────────

def build_06():
    write("06_features", nb([
        ("md", "# Demo 06: Life & Survival\n\nPopulation dynamics and concentration envelopes."),
        ("code", SETUP),
        ("code", """\
from _shared import make_homeostatic_system
from alienbio.viz import population_dynamics, envelope_timeline

system = make_homeostatic_system(seed=7)
timeline = system.run(500)
"""),
        ("md", "## Population Dynamics"),
        ("code", "population_dynamics(timeline, species=['A', 'B', 'C'], title='Population Dynamics');"),
        ("md", "## Concentration Envelope\nViable range for molecule A: 1.0–8.0"),
        ("code", """\
envelope = {"A": (1.0, 8.0)}
envelope_timeline(timeline, envelope, "A", title="Concentration Envelope");
"""),
    ]))


# ── 07 Skinning ─────────────────────────────────────────────────────────

def build_07():
    write("07_skinning", nb([
        ("md", "# Demo 07: Generating & Skinning\n\nReplace real molecule/reaction names with opaque alien terminology at 3 detail levels."),
        ("code", SETUP),
        ("code", """\
from _shared import make_homeostatic_system
from alienbio.bio import generate_description, generate_name_map

system = make_homeostatic_system(seed=42)
name_map = generate_name_map(system, seed=42)
print("Name mapping:")
for real, alien in name_map.items():
    print(f"  {real} → {alien}")
"""),
        ("md", "## Level 1 — Minimal"),
        ("code", "print(generate_description(system, detail_level=1, name_map=name_map, seed=42))"),
        ("md", "## Level 2 — Moderate"),
        ("code", "print(generate_description(system, detail_level=2, name_map=name_map, seed=42))"),
        ("md", "## Level 3 — Full"),
        ("code", "print(generate_description(system, detail_level=3, name_map=name_map, seed=42))"),
    ]))


# ── 08 Evaluation ───────────────────────────────────────────────────────

def build_08():
    write("08_evaluation", nb([
        ("md", "# Demo 08: Agent Evaluation\n\nOracle, random, and zero agents evaluated across difficulty levels."),
        ("code", SETUP),
        ("code", """\
from _shared import make_disease_system, oracle_agent, random_agent, zero_agent
from alienbio.bio import (
    AgentInterface, BioSystem, TestSuite,
    compare, generate_diagnosis_task, run_suite,
)
from alienbio.viz import difficulty_curve_plot, agent_comparison_chart

system, _, perturbations = make_disease_system(seed=42)
agents = {"oracle": oracle_agent, "random": random_agent, "zero": zero_agent}
"""),
        ("md", "## Difficulty Curves"),
        ("code", """\
curves = {name: [] for name in agents}
for diff in [1, 2, 3]:
    for agent_name, agent_fn in agents.items():
        suite = TestSuite(name=f"{agent_name}_d{diff}")
        for trial in range(5):
            task = generate_diagnosis_task(system, perturbations, difficulty=diff, seed=diff*100+trial)
            interface = AgentInterface(BioSystem(system.chemistry, system.state.copy(), dt=0.1))
            suite.add(interface, task)
        results = run_suite(suite, agent_fn)
        curves[agent_name].append((diff, results.mean_score))

difficulty_curve_plot(curves, title="Difficulty Curves");
"""),
        ("md", "## Agent Comparison\nAll agents at difficulty 2."),
        ("code", """\
all_results = {}
for agent_name, agent_fn in agents.items():
    suite = TestSuite(name=agent_name)
    for trial in range(10):
        task = generate_diagnosis_task(system, perturbations, difficulty=2, seed=200+trial)
        interface = AgentInterface(BioSystem(system.chemistry, system.state.copy(), dt=0.1))
        suite.add(interface, task)
    all_results[agent_name] = run_suite(suite, agent_fn)

table = compare(all_results)
for a in table.ranking:
    print(f"  {a.agent_name}: mean={a.mean:.2f}, pass_rate={a.pass_rate:.0%}")

agent_comparison_chart(table, title="Agent Comparison");
"""),
    ]))


# ── Combo: Disease Investigation ────────────────────────────────────────

def build_combo_disease():
    write("combo_disease_investigation", nb([
        ("md", "# Combo: Disease Investigation\n\n4-panel figure: healthy equilibrium → disease → symptoms → diagnosis."),
        ("code", SETUP),
        ("code", """\
import matplotlib.pyplot as plt
from _shared import make_disease_system, oracle_agent
from alienbio.bio import (
    AgentInterface, BioSystem, detect_symptoms,
    generate_diagnosis_task, run_experiment,
)
from alienbio.viz import save_or_show

system, baseline, perturbations = make_disease_system(seed=42)
fig, axes = plt.subplots(2, 2, figsize=(14, 10))
fig.suptitle("Disease Investigation", fontsize=14)

# Panel 1: Healthy
healthy = BioSystem(system.chemistry, system.state.copy(), dt=0.1)
healthy_tl = healthy.run(300)
for mol in list(healthy_tl[0]):
    axes[0, 0].plot(range(len(healthy_tl)), [s[mol] for s in healthy_tl], label=mol)
axes[0, 0].set_title("1. Healthy Equilibrium")
axes[0, 0].set_xlabel("Time Step"); axes[0, 0].set_ylabel("Concentration"); axes[0, 0].legend(fontsize="small")

# Panel 2: Diseased
pert = perturbations[0]
diseased = BioSystem(system.chemistry, system.state.copy(), dt=0.1)
pert.apply(diseased)
diseased_tl = diseased.run(300)
for mol in list(diseased_tl[0]):
    axes[0, 1].plot(range(len(diseased_tl)), [s[mol] for s in diseased_tl], label=mol)
axes[0, 1].set_title(f"2. Diseased ({pert.name})")
axes[0, 1].set_xlabel("Time Step"); axes[0, 1].set_ylabel("Concentration"); axes[0, 1].legend(fontsize="small")

# Panel 3: Symptoms
concs = {m: diseased.state[m] for m in diseased.state}
symptoms = detect_symptoms(concs, baseline)
if symptoms:
    names = [s.molecule for s in symptoms]
    range_map = {r.molecule: r for r in baseline.ranges}
    for i, s in enumerate(symptoms):
        r = range_map.get(s.molecule)
        if r: axes[1, 0].barh(i, r.high - r.low, left=r.low, height=0.4, color="green", alpha=0.2)
    axes[1, 0].barh(range(len(names)), [s.value for s in symptoms], height=0.4, color="red", alpha=0.7)
    axes[1, 0].set_yticks(range(len(names))); axes[1, 0].set_yticklabels(names)
axes[1, 0].set_title("3. Symptoms"); axes[1, 0].set_xlabel("Concentration")

# Panel 4: Diagnosis
task = generate_diagnosis_task(system, perturbations, difficulty=2, seed=42)
interface = AgentInterface(BioSystem(system.chemistry, system.state.copy(), dt=0.1))
result = run_experiment(interface, task, oracle_agent)
cnames = [p.name for p in task.candidates]
colors = ["green" if i == task.correct_index else "gray" for i in range(len(cnames))]
axes[1, 1].barh(range(len(cnames)), [1]*len(cnames), color=colors, alpha=0.7)
axes[1, 1].set_yticks(range(len(cnames))); axes[1, 1].set_yticklabels(cnames, fontsize=8)
axes[1, 1].set_title(f"4. Diagnosis (score={result.score:.1f})")

fig.tight_layout()
plt.show()
"""),
    ]))


# ── Combo: Alien Exam ───────────────────────────────────────────────────

def build_combo_exam():
    write("combo_alien_exam", nb([
        ("md", "# Combo: Alien Exam\n\nAgents evaluated on skinned (opaque) diagnosis tasks at multiple difficulty levels."),
        ("code", SETUP),
        ("code", """\
from _shared import make_disease_system, oracle_agent, random_agent, zero_agent
from alienbio.bio import (
    AgentInterface, BioSystem, TestSuite,
    compare, generate_diagnosis_task, generate_name_map, run_suite, skin_task_description,
)
from alienbio.viz import difficulty_curve_plot, agent_comparison_chart

system, _, perturbations = make_disease_system(seed=42)
name_map = generate_name_map(system, seed=42)
agents = {"oracle": oracle_agent, "random": random_agent, "zero": zero_agent}
"""),
        ("md", "## Difficulty Curves (Skinned Tasks)"),
        ("code", """\
curves = {name: [] for name in agents}
for diff in [1, 2, 3, 4]:
    for agent_name, agent_fn in agents.items():
        suite = TestSuite(name=f"{agent_name}_d{diff}")
        for trial in range(5):
            task = generate_diagnosis_task(system, perturbations, difficulty=diff, seed=diff*100+trial)
            skin_task_description(task, name_map)
            interface = AgentInterface(BioSystem(system.chemistry, system.state.copy(), dt=0.1))
            suite.add(interface, task)
        results = run_suite(suite, agent_fn)
        curves[agent_name].append((diff, results.mean_score))

difficulty_curve_plot(curves, title="Alien Exam: Difficulty Curves");
"""),
        ("md", "## Leaderboard (Difficulty 3)"),
        ("code", """\
all_results = {}
for agent_name, agent_fn in agents.items():
    suite = TestSuite(name=agent_name)
    for trial in range(10):
        task = generate_diagnosis_task(system, perturbations, difficulty=3, seed=300+trial)
        interface = AgentInterface(BioSystem(system.chemistry, system.state.copy(), dt=0.1))
        suite.add(interface, task)
    all_results[agent_name] = run_suite(suite, agent_fn)

table = compare(all_results)
for a in table.ranking:
    print(f"  {a.agent_name}: mean={a.mean:.2f}")
agent_comparison_chart(table, title="Alien Exam: Leaderboard");
"""),
    ]))


# ── Combo: Ecosystem ────────────────────────────────────────────────────

def build_combo_ecosystem():
    write("combo_ecosystem", nb([
        ("md", "# Combo: Ecosystem\n\nMulti-compartment organism heatmap and concentration envelope violations."),
        ("code", SETUP),
        ("code", """\
from _shared import make_homeostatic_system, make_organism
from alienbio.viz import compartment_heatmap, envelope_timeline
"""),
        ("md", "## Organism Heatmap"),
        ("code", """\
organism = make_organism(seed=42)
world_tl = organism.simulator.run(organism.state, steps=200, sample_every=5)
compartment_heatmap(world_tl, molecule_id=0, title="Ecosystem: Compartment Heatmap");
"""),
        ("md", "## Envelope Violations"),
        ("code", """\
system = make_homeostatic_system(seed=42)
timeline = system.run(500)
envelope_timeline(timeline, {"A": (2.0, 6.0)}, "A", title="Ecosystem: Envelope Violations");
"""),
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
