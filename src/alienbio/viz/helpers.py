"""Data conversion utilities for visualization."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

try:
    import matplotlib
    import matplotlib.pyplot as plt
    import matplotlib.figure
except ImportError:
    raise ImportError("matplotlib is required for alienbio.viz — pip install matplotlib")


def timeline_to_arrays(
    timeline: List[Any],
    molecules: Optional[List[str]] = None,
) -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
    """Convert a list of StateImpl to numpy arrays for plotting.

    Args:
        timeline: List of StateImpl objects (from BioSystem.run())
        molecules: Which molecules to extract. None = all molecules.

    Returns:
        (time_steps, {molecule_name: concentration_array})
    """
    if not timeline:
        return np.array([]), {}

    if molecules is None:
        molecules = [name for name, _ in timeline[0].items()]

    time_steps = np.arange(len(timeline))
    data: Dict[str, np.ndarray] = {}
    for mol in molecules:
        data[mol] = np.array([state[mol] for state in timeline])

    return time_steps, data


def world_timeline_to_arrays(
    timeline: List[Any],
    molecule_id: int,
    compartment_ids: Optional[List[int]] = None,
) -> Tuple[np.ndarray, Dict[int, np.ndarray]]:
    """Convert a list of WorldStateImpl to numpy arrays for plotting.

    Args:
        timeline: List of WorldStateImpl objects
        molecule_id: Which molecule (by index) to extract
        compartment_ids: Which compartments to extract. None = all.

    Returns:
        (time_steps, {compartment_id: concentration_array})
    """
    if not timeline:
        return np.array([]), {}

    if compartment_ids is None:
        compartment_ids = list(range(timeline[0].num_compartments))

    time_steps = np.arange(len(timeline))
    data: Dict[int, np.ndarray] = {}
    for comp_id in compartment_ids:
        data[comp_id] = np.array(
            [state.get(comp_id, molecule_id) for state in timeline]
        )

    return time_steps, data


def save_or_show(fig: matplotlib.figure.Figure, path: Optional[str] = None) -> None:
    """Save figure to path, or show interactively.

    Args:
        fig: The matplotlib figure
        path: File path to save to. If None, calls plt.show().
    """
    if path is not None:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        fig.savefig(path, dpi=150, bbox_inches="tight")
        plt.close(fig)
    else:
        plt.show()
