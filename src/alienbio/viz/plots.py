"""Core plotting functions for alienbio visualization."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.figure
from .helpers import timeline_to_arrays, world_timeline_to_arrays, save_or_show


def concentration_trajectory(
    timeline: List[Any],
    molecules: Optional[List[str]] = None,
    title: Optional[str] = None,
    save_path: Optional[str] = None,
) -> matplotlib.figure.Figure:
    """Line chart of molecule concentrations over time.

    Args:
        timeline: List of StateImpl from BioSystem.run()
        molecules: Which molecules to plot. None = all.
        title: Plot title
        save_path: If given, save figure to this path instead of showing.

    Returns:
        The matplotlib Figure.
    """
    times, data = timeline_to_arrays(timeline, molecules)

    fig, ax = plt.subplots(figsize=(10, 6))
    for mol_name, conc in data.items():
        ax.plot(times, conc, label=mol_name)

    ax.set_xlabel("Time Step")
    ax.set_ylabel("Concentration")
    ax.set_title(title or "Concentration Trajectories")
    ax.legend()
    ax.grid(True, alpha=0.3)

    fig.tight_layout()
    save_or_show(fig, save_path)
    return fig


def equilibrium_convergence(
    timeline: List[Any],
    stability: Any,
    title: Optional[str] = None,
    save_path: Optional[str] = None,
) -> matplotlib.figure.Figure:
    """Trajectories with variance subplot showing convergence.

    Args:
        timeline: List of StateImpl
        stability: StabilityResult with variance and window info
        title: Plot title
        save_path: Save path

    Returns:
        The matplotlib Figure.
    """
    times, data = timeline_to_arrays(timeline)

    fig, (ax_traj, ax_var) = plt.subplots(2, 1, figsize=(10, 8), height_ratios=[2, 1])

    for mol_name, conc in data.items():
        ax_traj.plot(times, conc, label=mol_name)
    ax_traj.set_ylabel("Concentration")
    ax_traj.set_title(title or "Equilibrium Convergence")
    ax_traj.legend()
    ax_traj.grid(True, alpha=0.3)

    # Variance subplot
    mol_names = list(data.keys())
    window = stability.window
    if len(times) > window:
        var_times = times[window:]
        for mol_name in mol_names:
            conc = data[mol_name]
            rolling_var = np.array([
                np.var(conc[max(0, i - window):i])
                for i in range(window, len(conc))
            ])
            ax_var.plot(var_times, rolling_var, label=mol_name)

    # Threshold line from max_variance
    if stability.max_variance > 0:
        ax_var.axhline(y=stability.max_variance, color="red", linestyle="--",
                       alpha=0.7, label=f"max variance = {stability.max_variance:.2e}")

    ax_var.set_xlabel("Time Step")
    ax_var.set_ylabel("Variance")
    ax_var.set_title("Rolling Variance")
    ax_var.legend(fontsize=8)
    ax_var.grid(True, alpha=0.3)

    fig.tight_layout()
    save_or_show(fig, save_path)
    return fig


def perturbation_response(
    baseline_tl: List[Any],
    perturbed_tl: List[Any],
    result: Any,
    molecules: Optional[List[str]] = None,
    title: Optional[str] = None,
    save_path: Optional[str] = None,
) -> matplotlib.figure.Figure:
    """Overlaid baseline vs perturbed trajectories with recovery point.

    Args:
        baseline_tl: Baseline timeline (List of StateImpl)
        perturbed_tl: Perturbed timeline
        result: PerturbationResult with recovery_step
        molecules: Which molecules to plot
        title: Plot title
        save_path: Save path

    Returns:
        The matplotlib Figure.
    """
    b_times, b_data = timeline_to_arrays(baseline_tl, molecules)
    p_times, p_data = timeline_to_arrays(perturbed_tl, molecules)

    fig, ax = plt.subplots(figsize=(10, 6))

    cmap = plt.colormaps["tab10"]
    colors = [cmap(i) for i in range(10)]
    for i, mol_name in enumerate(b_data):
        color = colors[i % len(colors)]
        ax.plot(b_times, b_data[mol_name], color=color, alpha=0.4,
                linestyle="--", label=f"{mol_name} (baseline)")
        if mol_name in p_data:
            ax.plot(p_times, p_data[mol_name], color=color,
                    label=f"{mol_name} (perturbed)")

    if result.recovery_step is not None:
        ax.axvline(x=result.recovery_step, color="green", linestyle=":",
                   alpha=0.8, label=f"recovery @ step {result.recovery_step}")

    ax.set_xlabel("Time Step")
    ax.set_ylabel("Concentration")
    ax.set_title(title or "Perturbation Response")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    fig.tight_layout()
    save_or_show(fig, save_path)
    return fig


def symptom_chart(
    symptoms: List[Any],
    baseline: Any,
    title: Optional[str] = None,
    save_path: Optional[str] = None,
) -> matplotlib.figure.Figure:
    """Horizontal bars showing healthy ranges with actual diseased values.

    Args:
        symptoms: List of Symptom objects
        baseline: Baseline with steady_state and ranges
        title: Plot title
        save_path: Save path

    Returns:
        The matplotlib Figure.
    """
    fig, ax = plt.subplots(figsize=(10, max(4, len(symptoms) * 0.8 + 1)))

    range_map = {r.molecule: r for r in baseline.ranges}
    y_positions = list(range(len(symptoms)))
    mol_labels = []

    for i, symptom in enumerate(symptoms):
        mol = symptom.molecule
        mol_labels.append(mol)

        hr = range_map.get(mol, symptom.healthy_range)
        ax.barh(i, hr.high - hr.low, left=hr.low, height=0.5,
                color="green", alpha=0.25, label="Healthy range" if i == 0 else None)

        ax.plot(symptom.value, i, "ro", markersize=10, zorder=5,
                label="Actual value" if i == 0 else None)

        ax.plot(baseline.steady_state.get(mol, (hr.low + hr.high) / 2), i,
                "b|", markersize=15, markeredgewidth=2, zorder=4,
                label="Steady state" if i == 0 else None)

    ax.set_yticks(y_positions)
    ax.set_yticklabels(mol_labels)
    ax.set_xlabel("Concentration")
    ax.set_title(title or "Symptom Chart")
    ax.legend()
    ax.grid(True, axis="x", alpha=0.3)

    fig.tight_layout()
    save_or_show(fig, save_path)
    return fig


def compartment_heatmap(
    world_timeline: List[Any],
    molecule_id: int,
    compartment_names: Optional[Dict[int, str]] = None,
    title: Optional[str] = None,
    save_path: Optional[str] = None,
) -> matplotlib.figure.Figure:
    """Heatmap of molecule concentration across compartments over time.

    Args:
        world_timeline: List of WorldStateImpl
        molecule_id: Which molecule to visualize
        compartment_names: Optional {id: name} mapping for y-axis labels
        title: Plot title
        save_path: Save path

    Returns:
        The matplotlib Figure.
    """
    _times, data = world_timeline_to_arrays(world_timeline, molecule_id)

    comp_ids = sorted(data.keys())
    matrix = np.array([data[cid] for cid in comp_ids])

    fig, ax = plt.subplots(figsize=(12, max(4, len(comp_ids) * 0.6 + 1)))
    im = ax.imshow(matrix, aspect="auto", cmap="viridis", interpolation="nearest")

    ax.set_xlabel("Time Step")
    ax.set_ylabel("Compartment")
    ax.set_title(title or f"Compartment Heatmap (molecule {molecule_id})")

    if compartment_names:
        labels = [compartment_names.get(cid, str(cid)) for cid in comp_ids]
    else:
        labels = [str(cid) for cid in comp_ids]
    ax.set_yticks(range(len(comp_ids)))
    ax.set_yticklabels(labels)

    fig.colorbar(im, ax=ax, label="Concentration")

    fig.tight_layout()
    save_or_show(fig, save_path)
    return fig


def population_dynamics(
    timeline: List[Any],
    species: List[str],
    title: Optional[str] = None,
    save_path: Optional[str] = None,
) -> matplotlib.figure.Figure:
    """Multi-line chart of predator/prey population curves.

    Args:
        timeline: List of StateImpl (molecules represent species populations)
        species: List of molecule names representing species
        title: Plot title
        save_path: Save path

    Returns:
        The matplotlib Figure.
    """
    times, data = timeline_to_arrays(timeline, species)

    fig, ax = plt.subplots(figsize=(10, 6))
    for sp_name, conc in data.items():
        ax.plot(times, conc, label=sp_name, linewidth=2)

    ax.set_xlabel("Time Step")
    ax.set_ylabel("Population")
    ax.set_title(title or "Population Dynamics")
    ax.legend()
    ax.grid(True, alpha=0.3)

    fig.tight_layout()
    save_or_show(fig, save_path)
    return fig


def difficulty_curve_plot(
    curves: List[Any],
    threshold: float = 0.5,
    title: Optional[str] = None,
    save_path: Optional[str] = None,
) -> matplotlib.figure.Figure:
    """Score vs difficulty level for multiple agents.

    Args:
        curves: List of DifficultyCurve objects
        threshold: Pass/fail threshold line
        title: Plot title
        save_path: Save path

    Returns:
        The matplotlib Figure.
    """
    fig, ax = plt.subplots(figsize=(10, 6))

    for curve in curves:
        levels = curve.levels
        scores = curve.mean_scores
        ax.plot(levels, scores, "o-", label=curve.agent_name, linewidth=2, markersize=8)

    ax.axhline(y=threshold, color="red", linestyle="--", alpha=0.6,
               label=f"threshold = {threshold}")

    ax.set_xlabel("Difficulty Level")
    ax.set_ylabel("Mean Score")
    ax.set_title(title or "Difficulty Curves")
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.set_ylim(-0.05, 1.05)

    fig.tight_layout()
    save_or_show(fig, save_path)
    return fig


def agent_comparison_chart(
    table: Any,
    title: Optional[str] = None,
    save_path: Optional[str] = None,
) -> matplotlib.figure.Figure:
    """Grouped bar chart of agent performance with error bars.

    Args:
        table: ComparisonTable with agents list
        title: Plot title
        save_path: Save path

    Returns:
        The matplotlib Figure.
    """
    agents = table.ranking
    names = [a.agent_name for a in agents]
    means = [a.mean for a in agents]
    stds = [a.std for a in agents]

    fig, ax = plt.subplots(figsize=(max(8, len(names) * 1.5), 6))

    cmap = plt.colormaps["Set2"]
    colors = [cmap(i) for i in range(8)]
    bars = ax.bar(range(len(names)), means, yerr=stds, capsize=5,
                  color=[colors[i % len(colors)] for i in range(len(names))],
                  edgecolor="black", linewidth=0.5)

    ax.set_xticks(range(len(names)))
    ax.set_xticklabels(names, rotation=30, ha="right")
    ax.set_ylabel("Mean Score")
    ax.set_title(title or "Agent Comparison")
    ax.set_ylim(0, 1.1)
    ax.grid(True, axis="y", alpha=0.3)

    for i, (bar, mean) in enumerate(zip(bars, means)):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + stds[i] + 0.02,
                f"{mean:.2f}", ha="center", va="bottom", fontsize=9)

    fig.tight_layout()
    save_or_show(fig, save_path)
    return fig


def envelope_timeline(
    state_history: List[Any],
    envelope: Any,
    molecule_id: int,
    compartment_id: int,
    title: Optional[str] = None,
    save_path: Optional[str] = None,
) -> matplotlib.figure.Figure:
    """Trajectory with shaded viable region and violation markers.

    Args:
        state_history: List of WorldStateImpl
        envelope: OperatingEnvelope
        molecule_id: Which molecule to track
        compartment_id: Which compartment to track
        title: Plot title
        save_path: Save path

    Returns:
        The matplotlib Figure.
    """
    times = np.arange(len(state_history))
    values = np.array([s.get(compartment_id, molecule_id) for s in state_history])

    # Find the matching envelope bound
    bound = None
    for b in envelope.bounds:
        if b.molecule_id == molecule_id and b.compartment_id == compartment_id:
            bound = b
            break

    fig, ax = plt.subplots(figsize=(10, 6))

    if bound is not None:
        ax.axhspan(bound.low, bound.high, alpha=0.15, color="green",
                   label=f"Viable range [{bound.low:.1f}, {bound.high:.1f}]")

        violations = (values < bound.low) | (values > bound.high)
        if np.any(violations):
            ax.scatter(times[violations], values[violations],
                       color="red", marker="x", s=50, zorder=5,
                       label="Violations")

    ax.plot(times, values, "b-", linewidth=1.5, label="Concentration")

    ax.set_xlabel("Time Step")
    ax.set_ylabel("Concentration")
    ax.set_title(title or f"Envelope Timeline (mol={molecule_id}, comp={compartment_id})")
    ax.legend()
    ax.grid(True, alpha=0.3)

    fig.tight_layout()
    save_or_show(fig, save_path)
    return fig
