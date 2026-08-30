"""Visualization plots: reusable matplotlib figures for alienbio data."""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Union

import numpy as np
from matplotlib.figure import Figure
import matplotlib.pyplot as plt

from ..bio.state import StateImpl
from ..bio.world_state import WorldStateImpl
from ..bio.disease import Symptom, Baseline
from .helpers import timeline_to_arrays, world_timeline_to_arrays


# ---------------------------------------------------------------------------
# 1. Concentration trajectory
# ---------------------------------------------------------------------------

def concentration_trajectory(
    timeline: Union[List[StateImpl], List[Dict[str, float]]],
    molecules: Optional[Sequence[str]] = None,
    *,
    title: str = "Concentration Trajectory",
    save_path: Optional[str] = None,
) -> Figure:
    """Line plot of molecule concentrations over time.

    Args:
        timeline: Simulation timeline (StateImpl list or dicts).
        molecules: Molecule names to plot (default: all).
        title: Figure title.
        save_path: If given, save figure and close it.

    Returns:
        The matplotlib Figure.
    """
    steps, arrays = timeline_to_arrays(timeline, molecules)
    fig, ax = plt.subplots()
    for mol, concs in arrays.items():
        ax.plot(steps, concs, label=mol)
    ax.set_xlabel("Time Step")
    ax.set_ylabel("Concentration")
    ax.set_title(title)
    ax.legend()

    if save_path is not None:
        from .helpers import save_or_show
        save_or_show(fig, save_path)
    return fig


# ---------------------------------------------------------------------------
# 2. Equilibrium convergence
# ---------------------------------------------------------------------------

def equilibrium_convergence(
    timeline: Union[List[StateImpl], List[Dict[str, float]]],
    *,
    window: int = 100,
    threshold: float = 1e-4,
    title: str = "Equilibrium Convergence",
    save_path: Optional[str] = None,
) -> Figure:
    """Two-subplot figure: trajectories (top) and rolling variance (bottom).

    Args:
        timeline: Simulation timeline.
        window: Rolling-window size for variance.
        threshold: Horizontal line marking the stability threshold.
        title: Figure title.
        save_path: Optional save path.

    Returns:
        The matplotlib Figure.
    """
    steps, arrays = timeline_to_arrays(timeline)

    fig, (ax_top, ax_bot) = plt.subplots(2, 1, sharex=True, figsize=(8, 6))
    fig.suptitle(title)

    # Top: trajectories
    for mol, concs in arrays.items():
        ax_top.plot(steps, concs, label=mol)
    ax_top.set_ylabel("Concentration")
    ax_top.legend(fontsize="small")

    # Bottom: rolling variance per molecule
    for mol, concs in arrays.items():
        arr = np.array(concs)
        var_series: List[float] = []
        for i in range(len(arr)):
            start = max(0, i - window + 1)
            segment = arr[start:i + 1]
            var_series.append(float(np.var(segment)))
        ax_bot.plot(steps, var_series, label=mol)

    ax_bot.axhline(threshold, color="red", linestyle="--", linewidth=0.8, label="threshold")
    ax_bot.set_xlabel("Time Step")
    ax_bot.set_ylabel("Variance")
    ax_bot.set_yscale("log")
    ax_bot.legend(fontsize="small")

    fig.tight_layout()
    if save_path is not None:
        from .helpers import save_or_show
        save_or_show(fig, save_path)
    return fig


# ---------------------------------------------------------------------------
# 3. Perturbation response
# ---------------------------------------------------------------------------

def perturbation_response(
    baseline_timeline: Union[List[StateImpl], List[Dict[str, float]]],
    perturbed_timeline: Union[List[StateImpl], List[Dict[str, float]]],
    *,
    molecules: Optional[Sequence[str]] = None,
    title: str = "Perturbation Response",
    save_path: Optional[str] = None,
) -> Figure:
    """Overlay baseline and perturbed trajectories.

    Args:
        baseline_timeline: Unperturbed simulation.
        perturbed_timeline: Perturbed simulation.
        molecules: Which molecules to plot.
        title: Figure title.
        save_path: Optional save path.

    Returns:
        The matplotlib Figure.
    """
    b_steps, b_arrays = timeline_to_arrays(baseline_timeline, molecules)
    p_steps, p_arrays = timeline_to_arrays(perturbed_timeline, molecules)

    fig, ax = plt.subplots()
    for mol in b_arrays:
        ax.plot(b_steps, b_arrays[mol], label=f"{mol} (baseline)", linestyle="--", alpha=0.7)
        if mol in p_arrays:
            ax.plot(p_steps, p_arrays[mol], label=f"{mol} (perturbed)")
    ax.set_xlabel("Time Step")
    ax.set_ylabel("Concentration")
    ax.set_title(title)
    ax.legend(fontsize="small")

    if save_path is not None:
        from .helpers import save_or_show
        save_or_show(fig, save_path)
    return fig


# ---------------------------------------------------------------------------
# 4. Symptom chart
# ---------------------------------------------------------------------------

def symptom_chart(
    symptoms: List[Symptom],
    baseline: Optional[Baseline] = None,
    *,
    title: str = "Symptoms",
    save_path: Optional[str] = None,
) -> Figure:
    """Horizontal bar chart of symptom values with healthy ranges.

    Args:
        symptoms: Detected symptoms.
        baseline: If given, healthy ranges are shown as green spans.
        title: Figure title.
        save_path: Optional save path.

    Returns:
        The matplotlib Figure.
    """
    fig, ax = plt.subplots()

    if not symptoms:
        ax.set_title(title)
        ax.text(0.5, 0.5, "No symptoms detected", transform=ax.transAxes,
                ha="center", va="center")
        if save_path is not None:
            from .helpers import save_or_show
            save_or_show(fig, save_path)
        return fig

    names = [s.molecule for s in symptoms]
    values = [s.value for s in symptoms]
    y_pos = list(range(len(names)))

    # Draw healthy ranges if available
    if baseline is not None:
        range_map = {r.molecule: r for r in baseline.ranges}
        for i, s in enumerate(symptoms):
            r = range_map.get(s.molecule)
            if r is not None:
                ax.barh(i, r.high - r.low, left=r.low, height=0.4,
                        color="green", alpha=0.2, label="healthy" if i == 0 else "")

    ax.barh(y_pos, values, height=0.4, color="red", alpha=0.7, label="observed")
    ax.set_yticks(y_pos)
    ax.set_yticklabels(names)
    ax.set_xlabel("Concentration")
    ax.set_title(title)
    ax.legend()

    if save_path is not None:
        from .helpers import save_or_show
        save_or_show(fig, save_path)
    return fig


# ---------------------------------------------------------------------------
# 5. Compartment heatmap
# ---------------------------------------------------------------------------

def compartment_heatmap(
    world_timeline: List[WorldStateImpl],
    molecule_id: int,
    *,
    compartment_ids: Optional[Sequence[int]] = None,
    title: str = "Compartment Heatmap",
    save_path: Optional[str] = None,
) -> Figure:
    """Heatmap: compartments (y) vs time (x), coloured by concentration.

    Args:
        world_timeline: List of WorldStateImpl snapshots.
        molecule_id: Which molecule to visualise.
        compartment_ids: Subset of compartments (default: all).
        title: Figure title.
        save_path: Optional save path.

    Returns:
        The matplotlib Figure.
    """
    _, arrays = world_timeline_to_arrays(world_timeline, molecule_id, compartment_ids)

    comp_ids = sorted(arrays.keys())
    data = np.array([arrays[c] for c in comp_ids])

    fig, ax = plt.subplots()
    im = ax.imshow(data, aspect="auto", interpolation="nearest")
    ax.set_xlabel("Time Step")
    ax.set_ylabel("Compartment")
    ax.set_yticks(range(len(comp_ids)))
    ax.set_yticklabels([str(c) for c in comp_ids])
    ax.set_title(title)
    fig.colorbar(im, ax=ax, label="Concentration")

    if save_path is not None:
        from .helpers import save_or_show
        save_or_show(fig, save_path)
    return fig


# ---------------------------------------------------------------------------
# 6. Population dynamics
# ---------------------------------------------------------------------------

def population_dynamics(
    timeline: Union[List[StateImpl], List[Dict[str, float]]],
    species: Optional[Sequence[str]] = None,
    *,
    title: str = "Population Dynamics",
    save_path: Optional[str] = None,
) -> Figure:
    """Multi-line chart of species populations over time.

    Args:
        timeline: Simulation timeline.
        species: Names to plot (default: all molecules).
        title: Figure title.
        save_path: Optional save path.

    Returns:
        The matplotlib Figure.
    """
    steps, arrays = timeline_to_arrays(timeline, species)

    fig, ax = plt.subplots()
    for name, concs in arrays.items():
        ax.plot(steps, concs, label=name, linewidth=2)
    ax.set_xlabel("Time Step")
    ax.set_ylabel("Population")
    ax.set_title(title)
    ax.legend()

    if save_path is not None:
        from .helpers import save_or_show
        save_or_show(fig, save_path)
    return fig


# ---------------------------------------------------------------------------
# 7. Envelope timeline
# ---------------------------------------------------------------------------

def envelope_timeline(
    timeline: Union[List[StateImpl], List[Dict[str, float]]],
    envelope: Dict[str, tuple[float, float]],
    molecule: str,
    *,
    title: str = "Concentration Envelope",
    save_path: Optional[str] = None,
) -> Figure:
    """Trajectory with shaded viable region.

    Args:
        timeline: Simulation timeline.
        envelope: Mapping of molecule name to ``(low, high)`` viable bounds.
        molecule: Which molecule to plot.
        title: Figure title.
        save_path: Optional save path.

    Returns:
        The matplotlib Figure.
    """
    steps, arrays = timeline_to_arrays(timeline, [molecule])
    concs = arrays[molecule]

    fig, ax = plt.subplots()
    low, high = envelope[molecule]
    ax.fill_between(steps, low, high, alpha=0.2, color="green", label="viable range")
    ax.plot(steps, concs, label=molecule, color="blue")
    ax.set_xlabel("Time Step")
    ax.set_ylabel("Concentration")
    ax.set_title(title)
    ax.legend()

    if save_path is not None:
        from .helpers import save_or_show
        save_or_show(fig, save_path)
    return fig


# ---------------------------------------------------------------------------
# 8. Difficulty curve plot
# ---------------------------------------------------------------------------

def difficulty_curve_plot(
    curves: Dict[str, List[tuple[int, float]]],
    *,
    threshold: float = 0.5,
    title: str = "Difficulty Curve",
    save_path: Optional[str] = None,
) -> Figure:
    """Line plot of score vs difficulty level for multiple agents.

    Args:
        curves: Mapping of agent name to list of ``(difficulty, score)`` pairs.
        threshold: Horizontal line for pass/fail threshold.
        title: Figure title.
        save_path: Optional save path.

    Returns:
        The matplotlib Figure.
    """
    fig, ax = plt.subplots()
    for agent_name, points in curves.items():
        points_sorted = sorted(points)
        xs = [p[0] for p in points_sorted]
        ys = [p[1] for p in points_sorted]
        ax.plot(xs, ys, marker="o", label=agent_name)

    ax.axhline(threshold, color="red", linestyle="--", linewidth=0.8, label="threshold")
    ax.set_xlabel("Difficulty")
    ax.set_ylabel("Score")
    ax.set_title(title)
    ax.legend()

    if save_path is not None:
        from .helpers import save_or_show
        save_or_show(fig, save_path)
    return fig

