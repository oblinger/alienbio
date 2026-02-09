"""Core demo logic — pure functions that return figures/data, no I/O.

Each function corresponds to a demo script. Callers are responsible for
``matplotlib.use("Agg")`` and ``save_or_show()``.
"""

from __future__ import annotations

from typing import Any, List, TYPE_CHECKING

import matplotlib.pyplot as plt

from _shared import (
    _MockDat,
    make_disease_system,
    make_homeostatic_system,
    make_organism,
    oracle_agent,
    random_agent,
    zero_agent,
)
from alienbio.bio import (
    AgentInterface,
    BioSystem,
    ChemistryImpl,
    StateImpl,
    TestSuite,
    check_stability,
    compare,
    detect_symptoms,
    generate_description,
    generate_diagnosis_task,
    generate_name_map,
    run_experiment,
    run_suite,
    skin_task_description,
)
from alienbio.viz import (
    agent_comparison_chart,
    compartment_heatmap,
    concentration_trajectory,
    difficulty_curve_plot,
    envelope_timeline,
    equilibrium_convergence,
    perturbation_response,
    population_dynamics,
    symptom_chart,
)

if TYPE_CHECKING:
    from matplotlib.figure import Figure


# ── Demo 01: Quick Start ───────────────────────────────────────────────


def demo_01_quick_start(seed: int = 42) -> tuple[Figure, Figure]:
    """Run homeostatic system and return (trajectories, convergence) figures."""
    system = make_homeostatic_system(seed=seed)
    timeline = system.run(500)
    fig_traj = concentration_trajectory(timeline, title="Quick Start: Trajectories")
    fig_conv = equilibrium_convergence(timeline, title="Quick Start: Convergence")
    return fig_traj, fig_conv


# ── Demo 02: Equilibrium ──────────────────────────────────────────────


def demo_02_equilibrium(seed: int = 99) -> tuple[Any, Figure, Figure]:
    """Stability analysis. Returns (stability_result, trajectories, convergence)."""
    system = make_homeostatic_system(seed=seed)
    timeline = system.run(1000)
    result = check_stability(timeline, window=100, threshold=1e-4)
    fig_traj = concentration_trajectory(timeline, title="Equilibrium: Trajectories")
    fig_conv = equilibrium_convergence(timeline, window=100, title="Equilibrium: Convergence")
    return result, fig_traj, fig_conv


# ── Demo 03: Perturbation ─────────────────────────────────────────────


def demo_03_spike_recovery(seed: int = 42) -> Figure:
    """Spike +20 into molecule A and return perturbation response figure."""
    sys_base = make_homeostatic_system(seed=seed)
    sys_base.run(200)
    baseline_tl = sys_base.run(100)

    sys_spike = make_homeostatic_system(seed=seed)
    sys_spike.run(200)
    sys_spike.state["A"] = sys_spike.state["A"] + 20.0
    spike_tl = sys_spike.run(100)

    return perturbation_response(baseline_tl, spike_tl, title="Spike Recovery")


def demo_03_drift(seed: int = 42) -> Figure:
    """Remove B→C reaction and return drift response figure."""
    sys_drift_base = make_homeostatic_system(seed=seed)
    sys_drift_base.run(200)
    drift_baseline_tl = sys_drift_base.run(200)

    sys_orig = make_homeostatic_system(seed=seed)
    remaining = {n: r for n, r in sys_orig.chemistry.reactions.items() if n != "r_bc"}
    modified_chem = ChemistryImpl(
        "abc_no_rbc",
        atoms=sys_orig.chemistry.atoms,
        molecules=sys_orig.chemistry.molecules,
        reactions=remaining,
        dat=_MockDat("chem/abc_no_rbc"),
    )
    init_concs = {m: sys_drift_base.state[m] for m in sys_drift_base.state}
    modified_state = StateImpl(modified_chem, initial=init_concs)
    sys_drift = BioSystem(modified_chem, modified_state, dt=0.1)
    drift_tl = sys_drift.run(200)

    return perturbation_response(drift_baseline_tl, drift_tl, title="Reaction Removal Drift")


# ── Demo 04: Disease ──────────────────────────────────────────────────


def demo_04_disease(seed: int = 42) -> tuple[Any, Figure, Figure]:
    """Apply perturbation, detect symptoms. Returns (symptoms, trajectories, symptom_chart)."""
    system, baseline, perturbations = make_disease_system(seed=seed)
    pert = perturbations[0]

    diseased = BioSystem(system.chemistry, system.state.copy(), dt=0.1)
    pert.apply(diseased)
    diseased_tl = diseased.run(300)

    fig_traj = concentration_trajectory(diseased_tl, title=f"Diseased: {pert.name}")

    concs = {m: diseased.state[m] for m in diseased.state}
    symptoms = detect_symptoms(concs, baseline)

    fig_symp = symptom_chart(symptoms, baseline, title="Symptoms")
    return symptoms, fig_traj, fig_symp


# ── Demo 05: Organism ─────────────────────────────────────────────────


def demo_05_organism(seed: int = 42) -> Figure:
    """Multi-compartment heatmap. Returns heatmap figure."""
    organism = make_organism(seed=seed)
    world_tl = organism.simulator.run(organism.state, steps=200, sample_every=5)
    return compartment_heatmap(world_tl, molecule_id=0, title="Organism: Molecule 0 Heatmap")


# ── Demo 06: Features ─────────────────────────────────────────────────


def demo_06_features(seed: int = 7) -> tuple[Figure, Figure]:
    """Population dynamics and envelope. Returns (population, envelope) figures."""
    system = make_homeostatic_system(seed=seed)
    timeline = system.run(500)

    fig_pop = population_dynamics(
        timeline, species=["A", "B", "C"], title="Population Dynamics",
    )
    envelope = {"A": (1.0, 8.0)}
    fig_env = envelope_timeline(
        timeline, envelope, "A", title="Concentration Envelope",
    )
    return fig_pop, fig_env


# ── Demo 07: Skinning ─────────────────────────────────────────────────


def demo_07_skinning(seed: int = 42) -> dict[int, str]:
    """Generate descriptions at 3 detail levels. Returns {level: description}."""
    system = make_homeostatic_system(seed=seed)
    name_map = generate_name_map(system, seed=seed)
    return {
        level: generate_description(
            system, detail_level=level, name_map=name_map, seed=seed,
        )
        for level in (1, 2, 3)
    }


# ── Demo 08: Evaluation ───────────────────────────────────────────────


def demo_08_evaluation(seed: int = 42) -> tuple[Figure, Figure]:
    """Difficulty curves and agent comparison. Returns (difficulty, comparison) figures."""
    system, _baseline, perturbations = make_disease_system(seed=seed)
    agents = {"oracle": oracle_agent, "random": random_agent, "zero": zero_agent}
    difficulties = [1, 2, 3]
    curves: dict[str, List[tuple[int, float]]] = {name: [] for name in agents}

    for diff in difficulties:
        for agent_name, agent_fn in agents.items():
            suite = TestSuite(name=f"{agent_name}_d{diff}")
            for trial in range(5):
                task = generate_diagnosis_task(
                    system, perturbations, difficulty=diff, seed=diff * 100 + trial,
                )
                interface = AgentInterface(
                    BioSystem(system.chemistry, system.state.copy(), dt=0.1),
                )
                suite.add(interface, task)
            results = run_suite(suite, agent_fn)
            curves[agent_name].append((diff, results.mean_score))

    fig_diff = difficulty_curve_plot(curves, title="Difficulty Curves")

    all_results = {}
    for agent_name, agent_fn in agents.items():
        suite = TestSuite(name=agent_name)
        for trial in range(10):
            task = generate_diagnosis_task(
                system, perturbations, difficulty=2, seed=200 + trial,
            )
            interface = AgentInterface(
                BioSystem(system.chemistry, system.state.copy(), dt=0.1),
            )
            suite.add(interface, task)
        all_results[agent_name] = run_suite(suite, agent_fn)

    table = compare(all_results)
    fig_comp = agent_comparison_chart(table, title="Agent Comparison")
    return fig_diff, fig_comp


# ── Combo: Disease Investigation ───────────────────────────────────────


def combo_disease_investigation(seed: int = 42) -> Figure:
    """4-panel figure: healthy → disease → symptoms → diagnosis."""
    system, baseline, perturbations = make_disease_system(seed=seed)

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("Disease Investigation", fontsize=14)

    # Panel 1: Healthy equilibrium
    healthy = BioSystem(system.chemistry, system.state.copy(), dt=0.1)
    healthy_tl = healthy.run(300)
    for mol in list(healthy_tl[0]):
        vals = [s[mol] for s in healthy_tl]
        axes[0, 0].plot(range(len(vals)), vals, label=mol)
    axes[0, 0].set_title("1. Healthy Equilibrium")
    axes[0, 0].set_xlabel("Time Step")
    axes[0, 0].set_ylabel("Concentration")
    axes[0, 0].legend(fontsize="small")

    # Panel 2: Diseased system
    pert = perturbations[0]
    diseased = BioSystem(system.chemistry, system.state.copy(), dt=0.1)
    pert.apply(diseased)
    diseased_tl = diseased.run(300)
    for mol in list(diseased_tl[0]):
        vals = [s[mol] for s in diseased_tl]
        axes[0, 1].plot(range(len(vals)), vals, label=mol)
    axes[0, 1].set_title(f"2. Diseased ({pert.name})")
    axes[0, 1].set_xlabel("Time Step")
    axes[0, 1].set_ylabel("Concentration")
    axes[0, 1].legend(fontsize="small")

    # Panel 3: Symptoms
    concs = {m: diseased.state[m] for m in diseased.state}
    symptoms = detect_symptoms(concs, baseline)
    if symptoms:
        names = [s.molecule for s in symptoms]
        values = [s.value for s in symptoms]
        range_map = {r.molecule: r for r in baseline.ranges}
        for i, s in enumerate(symptoms):
            r = range_map.get(s.molecule)
            if r is not None:
                axes[1, 0].barh(
                    i, r.high - r.low, left=r.low, height=0.4,
                    color="green", alpha=0.2,
                )
        axes[1, 0].barh(
            range(len(names)), values, height=0.4, color="red", alpha=0.7,
        )
        axes[1, 0].set_yticks(range(len(names)))
        axes[1, 0].set_yticklabels(names)
    axes[1, 0].set_title("3. Symptoms Detected")
    axes[1, 0].set_xlabel("Concentration")

    # Panel 4: Diagnosis result
    task = generate_diagnosis_task(system, perturbations, difficulty=2, seed=seed)
    interface = AgentInterface(
        BioSystem(system.chemistry, system.state.copy(), dt=0.1),
    )
    result = run_experiment(interface, task, oracle_agent)
    candidate_names = [p.name for p in task.candidates]
    colors = [
        "green" if i == task.correct_index else "gray"
        for i in range(len(candidate_names))
    ]
    axes[1, 1].barh(
        range(len(candidate_names)), [1] * len(candidate_names),
        color=colors, alpha=0.7,
    )
    axes[1, 1].set_yticks(range(len(candidate_names)))
    axes[1, 1].set_yticklabels(candidate_names, fontsize=8)
    axes[1, 1].set_title(f"4. Diagnosis (score={result.score:.1f})")

    fig.tight_layout()
    return fig


# ── Combo: Alien Exam ──────────────────────────────────────────────────


def combo_alien_exam(seed: int = 42) -> tuple[Figure, Figure]:
    """Skinned difficulty curves and leaderboard. Returns (curves, leaderboard)."""
    system, _, perturbations = make_disease_system(seed=seed)
    name_map = generate_name_map(system, seed=seed)

    agents = {"oracle": oracle_agent, "random": random_agent, "zero": zero_agent}
    difficulties = [1, 2, 3, 4]
    curves: dict[str, List[tuple[int, float]]] = {name: [] for name in agents}

    for diff in difficulties:
        for agent_name, agent_fn in agents.items():
            suite = TestSuite(name=f"{agent_name}_d{diff}")
            for trial in range(5):
                task = generate_diagnosis_task(
                    system, perturbations, difficulty=diff, seed=diff * 100 + trial,
                )
                skin_task_description(task, name_map)
                interface = AgentInterface(
                    BioSystem(system.chemistry, system.state.copy(), dt=0.1),
                )
                suite.add(interface, task)
            results = run_suite(suite, agent_fn)
            curves[agent_name].append((diff, results.mean_score))

    fig_diff = difficulty_curve_plot(curves, title="Alien Exam: Difficulty Curves")

    all_results = {}
    for agent_name, agent_fn in agents.items():
        suite = TestSuite(name=agent_name)
        for trial in range(10):
            task = generate_diagnosis_task(
                system, perturbations, difficulty=3, seed=300 + trial,
            )
            interface = AgentInterface(
                BioSystem(system.chemistry, system.state.copy(), dt=0.1),
            )
            suite.add(interface, task)
        all_results[agent_name] = run_suite(suite, agent_fn)

    table = compare(all_results)
    fig_lead = agent_comparison_chart(table, title="Alien Exam: Leaderboard")
    return fig_diff, fig_lead


# ── Combo: Ecosystem ──────────────────────────────────────────────────


def combo_ecosystem(seed: int = 42) -> tuple[Figure, Figure]:
    """Organism heatmap and envelope violations. Returns (heatmap, envelope)."""
    organism = make_organism(seed=seed)
    world_tl = organism.simulator.run(organism.state, steps=200, sample_every=5)
    fig_heat = compartment_heatmap(
        world_tl, molecule_id=0, title="Ecosystem: Compartment Heatmap",
    )

    system = make_homeostatic_system(seed=seed)
    timeline = system.run(500)
    envelope = {"A": (2.0, 6.0)}
    fig_env = envelope_timeline(
        timeline, envelope, "A", title="Ecosystem: Envelope Violations",
    )
    return fig_heat, fig_env
