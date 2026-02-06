"""Difficulty scaling for diagnosis tasks."""

from __future__ import annotations

import random
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .biosystem import BioSystem
    from .disease import Perturbation
    from .diagnosis import DiagnoseTask


def generate_diagnosis_task(
    system: "BioSystem",
    perturbations: List["Perturbation"],
    *,
    difficulty: int = 1,
    seed: Optional[int] = None,
) -> "DiagnoseTask":
    """Generate a diagnosis task at a given difficulty level.

    Difficulty controls the number of candidate perturbations:
    - difficulty=1: 2 candidates (easy — binary choice)
    - difficulty=2: 4 candidates
    - difficulty=N: min(2*N, len(perturbations)) candidates

    Args:
        system: The biological system
        perturbations: Pool of all possible perturbations
        difficulty: Difficulty level (1 = easiest)
        seed: Random seed for reproducibility

    Returns:
        DiagnoseTask with appropriate number of candidates
    """
    from .diagnosis import DiagnoseTask

    rng = random.Random(seed)

    num_candidates = min(2 * difficulty, len(perturbations))
    num_candidates = max(2, num_candidates)  # at least 2

    candidates = rng.sample(perturbations, num_candidates)
    applied_index = rng.randrange(len(candidates))

    return DiagnoseTask(candidates, applied_index=applied_index)
