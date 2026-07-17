"""M27.3 — world-validity predicates (the "realness" gates).

Two opaque predicates the suite reject-samples worlds against, encoding the Q5
world-validity gates. Both are framework machinery — opaque tests over
trajectories / graphs, with no experiment content:

- :func:`non_obvious_causal` — **(A)** the target causal structure must be
  *invisible in the baseline trajectory alone and only revealed under
  perturbation*. Returned as a ``Callable[[Timeline, Timeline], bool]`` matching
  the :func:`~alienbio.suite.verify.verify` reject-sampling seam: it accepts a
  world only when the perturbation produces a non-trivial trajectory change.
- :func:`is_shortcut_resistant` — **(C)** the ground-truth answer must not
  coincide with the top-ranked node under a small battery of cheap *structural*
  heuristics (degree centrality, two-hop reach), so a heuristic shortcut cannot
  crack the task.
"""

from __future__ import annotations

from typing import Callable, Iterable, TYPE_CHECKING

import numpy as np

from .types import NodeId, Timeline

if TYPE_CHECKING:
    from ..bio.chemistry import ChemistryImpl


# ── (A) non-obvious causal structure ────────────────────────────────────────

def _stack(trace: Timeline) -> np.ndarray:
    """[n_samples x n_comp x n_species] array of a timeline's sampled states."""
    return np.array(
        [np.asarray(st.as_array(), dtype=np.float64) for st in trace.states],
        dtype=np.float64,
    )


def non_obvious_causal(
    min_deviation: float = 1e-3,
) -> Callable[[Timeline, Timeline], bool]:
    """A verify-predicate: the perturbation must reveal real, non-trivial structure.

    Returns ``pred(baseline, perturbed) -> bool`` for the
    :func:`~alienbio.suite.verify.verify` seam. The world is *valid* (``True``)
    only when the perturbed trajectory deviates from the baseline by more than
    ``min_deviation`` in total L2 — i.e. the target relationship is **not**
    readable from the baseline alone and **is** exposed by the intervention.
    Worlds whose perturbation changes nothing (deviation ~ 0) are rejected: the
    causal structure is either absent or not perturbation-revealed.
    """

    def _predicate(baseline: Timeline, perturbed: Timeline) -> bool:
        b = _stack(baseline)
        p = _stack(perturbed)
        if b.shape != p.shape or b.size == 0:
            return False
        deviation = float(np.sqrt(((p - b) ** 2).sum()))
        return deviation > min_deviation

    return _predicate


# ── (C) shortcut-resistance ─────────────────────────────────────────────────

def _degree(chem: "ChemistryImpl", node: NodeId) -> int:
    """Immediate-neighbor count (degree centrality)."""
    return len(chem.neighbors(node))


def _two_hop(chem: "ChemistryImpl", node: NodeId) -> int:
    """Distinct nodes reachable within two hops (a cheap centrality proxy)."""
    reach: set[str] = set()
    for nb in chem.neighbors(node):
        reach |= chem.neighbors(nb)
    reach.discard(node)
    return len(reach)


# The cheap-heuristic battery: each maps a node to a scalar "salience" score an
# agent might rank by. Extend this tuple to harden shortcut-resistance further.
_HEURISTICS: tuple[Callable[["ChemistryImpl", NodeId], int], ...] = (_degree, _two_hop)


def is_shortcut_resistant(
    chemistry: "ChemistryImpl",
    answer_nodes: Iterable[NodeId],
    top_k: int | None = None,
) -> bool:
    """(C) The answer must not be reproducible by any cheap structural heuristic.

    For each heuristic in the battery, rank all nodes by score (descending, ties
    broken by id) and take the top ``k`` (default: as many nodes as the answer
    has). The world is *shortcut-resistant* (``True``) only if **no** heuristic's
    top-``k`` pick equals the ground-truth ``answer_nodes`` set — otherwise a
    degree/centrality shortcut cracks the task and the world is rejected.

    An empty answer is trivially resistant.
    """
    answer = set(answer_nodes)
    if not answer:
        return True

    nodes = list(chemistry.molecules) + list(chemistry.reactions)
    k = top_k if top_k is not None else len(answer)
    for score_fn in _HEURISTICS:
        ranked = sorted(nodes, key=lambda n: (-score_fn(chemistry, n), n))
        if set(ranked[:k]) == answer:
            return False
    return True
