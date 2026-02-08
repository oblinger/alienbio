"""Visualization helpers: data extraction and figure management."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple, Union

from matplotlib.figure import Figure

from ..bio.state import StateImpl
from ..bio.world_state import WorldStateImpl


def timeline_to_arrays(
    timeline: Union[List[StateImpl], List[Dict[str, float]]],
    molecules: Optional[Sequence[str]] = None,
) -> Tuple[List[int], Dict[str, List[float]]]:
    """Extract time-step indices and per-molecule concentration arrays.

    Args:
        timeline: List of StateImpl objects or plain dicts mapping
            molecule name to concentration.
        molecules: Subset of molecule names to extract. If *None*, all
            molecules present in the first snapshot are used.

    Returns:
        ``(time_steps, {molecule_name: [concentration, ...]})``.
    """
    if not timeline:
        return [], {}

    first = timeline[0]
    if molecules is None:
        molecules = list(first.keys() if isinstance(first, dict) else first)

    time_steps = list(range(len(timeline)))
    arrays: Dict[str, List[float]] = {m: [] for m in molecules}

    for snapshot in timeline:
        for m in molecules:
            if isinstance(snapshot, dict):
                arrays[m].append(snapshot.get(m, 0.0))
            else:
                arrays[m].append(snapshot.get(m, 0.0))

    return time_steps, arrays


def world_timeline_to_arrays(
    timeline: List[WorldStateImpl],
    molecule_id: int,
    compartment_ids: Optional[Sequence[int]] = None,
) -> Tuple[List[int], Dict[int, List[float]]]:
    """Extract per-compartment concentration arrays for one molecule.

    Args:
        timeline: List of WorldStateImpl snapshots.
        molecule_id: Which molecule to extract.
        compartment_ids: Subset of compartment IDs.  If *None*, all
            compartments are used.

    Returns:
        ``(time_steps, {compartment_id: [concentration, ...]})``.
    """
    if not timeline:
        return [], {}

    first = timeline[0]
    if compartment_ids is None:
        compartment_ids = list(range(first.num_compartments))

    time_steps = list(range(len(timeline)))
    arrays: Dict[int, List[float]] = {c: [] for c in compartment_ids}

    for snapshot in timeline:
        for c in compartment_ids:
            arrays[c].append(snapshot.get(c, molecule_id))

    return time_steps, arrays


def save_or_show(fig: Figure, path: Optional[Union[str, Path]] = None) -> None:
    """Save figure to *path* or show interactively.

    When *path* is given, intermediate directories are created automatically,
    the figure is saved at 150 dpi with tight bounding box, and the figure is
    closed to free memory.  Otherwise ``plt.show()`` is called.
    """
    import matplotlib.pyplot as plt

    if path is not None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(str(p), dpi=150, bbox_inches="tight")
        plt.close(fig)
    else:
        plt.show()
