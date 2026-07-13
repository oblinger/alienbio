"""Pure grading functions — answer-vs-key and opaque outcome scoring.

This module is domain-neutral. :func:`grade_answer` compares two opaque
:class:`~alienbio.suite.types.Answer` payloads structurally, dispatching on the
:class:`~alienbio.suite.types.GraderSpec` kind; :func:`grade_outcome` invokes an
opaque scorer on a :class:`~alienbio.suite.types.Trace` without ever inspecting
the trace semantically. No side effects; both functions are deterministic.

Per-kind scoring formulas (``grade_answer``, score always in ``[0.0, 1.0]``):

- ``node_set`` — Jaccard partial credit ``|A ∩ K| / |A ∪ K|`` (two empty sets
  are equal → 1.0). ``config {"partial": False}`` switches to exact set
  equality (1.0/0.0).
- ``ordered_path`` — 1.0 iff the sequences are exactly equal; otherwise 0.0,
  unless ``config {"partial": True}``, which grants longest-common-prefix
  credit ``lcp(A, K) / max(len(A), len(K))`` (two empty paths are equal → 1.0).
- ``node_id`` — exact equality (1.0/0.0).
- ``scalar`` — tolerance step: 1.0 if ``|a - k| <= config["tol"]`` (default
  0.0, boundary inclusive), else 0.0. A step function is the simplest
  monotone falloff; graded decay can be layered on later via ``config``.
- ``json`` — deep structural equality via Python ``==`` on the (JSON-ish)
  nested values (1.0/0.0).

An unknown ``spec.kind`` raises :class:`ValueError` (fail visibly).
"""

from __future__ import annotations

from typing import Any, Callable

from .types import Answer, GraderSpec, Trace


def _grade_node_set(a: Any, k: Any, partial: bool) -> float:
    """Jaccard ``|A∩K| / |A∪K|`` (partial) or exact set equality."""
    a_set, k_set = set(a), set(k)
    if not partial:
        return 1.0 if a_set == k_set else 0.0
    union = a_set | k_set
    if not union:
        return 1.0  # both empty -> equal
    return len(a_set & k_set) / len(union)


def _grade_ordered_path(a: Any, k: Any, partial: bool) -> float:
    """1.0 iff equal; longest-common-prefix ratio when ``partial``."""
    a_seq, k_seq = list(a), list(k)
    if a_seq == k_seq:
        return 1.0
    if not partial:
        return 0.0
    lcp = 0
    for x, y in zip(a_seq, k_seq):
        if x != y:
            break
        lcp += 1
    return lcp / max(len(a_seq), len(k_seq))


def _grade_scalar(a: Any, k: Any, tol: float) -> float:
    """1.0 if ``|a - k| <= tol`` (boundary inclusive), else 0.0."""
    return 1.0 if abs(float(a) - float(k)) <= tol else 0.0


def grade_answer(answer: Answer, key: Answer, spec: GraderSpec) -> float:
    """Grade ``answer`` against ``key``, dispatching on ``spec.kind``.

    Returns a score in ``[0.0, 1.0]``. Values are opaque JSON-ish payloads
    compared structurally; the exact per-kind formulas are documented in the
    module docstring. Partial-credit behaviour is driven by ``spec.config``
    (``"partial"`` for node_set / ordered_path, ``"tol"`` for scalar).
    Raises :class:`ValueError` on an unknown kind.
    """
    config = spec.config
    if spec.kind == "node_set":
        return _grade_node_set(
            answer.value, key.value, partial=bool(config.get("partial", True))
        )
    if spec.kind == "ordered_path":
        return _grade_ordered_path(
            answer.value, key.value, partial=bool(config.get("partial", False))
        )
    if spec.kind == "node_id":
        return 1.0 if answer.value == key.value else 0.0
    if spec.kind == "scalar":
        return _grade_scalar(answer.value, key.value, tol=float(config.get("tol", 0.0)))
    if spec.kind == "json":
        return 1.0 if answer.value == key.value else 0.0
    raise ValueError(f"unknown grader kind: {spec.kind!r}")


def grade_outcome(trace: Trace, scorer: Callable[[Any], float], target: Any) -> float:
    """Score an outcome by invoking the opaque ``scorer`` on the whole ``trace``.

    The scorer receives the full :class:`~alienbio.suite.types.Trace` (it picks
    whatever it needs, e.g. the final :class:`~alienbio.suite.types.StateVector`)
    and its return value is passed through as a float, unmodified. ``target`` is
    opaque context kept for interface symmetry with
    :class:`~alienbio.suite.types.OutcomeObjective`; it is never inspected here —
    a scorer that needs it closes over it. The trace is never inspected
    semantically by this function.
    """
    del target  # opaque; scorers close over any context they need
    return float(scorer(trace))
