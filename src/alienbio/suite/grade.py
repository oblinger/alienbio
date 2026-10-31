"""Pure grading functions — answer-vs-key and opaque outcome scoring.

This module is domain-neutral. :func:`grade_answer` compares two opaque
:class:`~alienbio.suite.types.Answer` payloads structurally, dispatching on the
:class:`~alienbio.suite.types.GraderSpec` kind; :func:`grade_outcome` invokes an
opaque scorer on a :class:`~alienbio.suite.types.Timeline` without ever inspecting
the trace semantically. No side effects; both functions are deterministic.

Per-kind scoring formulas (``grade_answer``, score always in ``[0.0, 1.0]``):

- ``node_set`` — Jaccard partial credit ``|A ∩ K| / |A ∪ K|`` (two empty sets
  are equal → 1.0). ``config {"partial": False}`` switches to exact set
  equality (1.0/0.0).
- ``ordered_path`` — 1.0 iff the sequences are exactly equal; otherwise 0.0,
  unless ``config {"partial": True}``, which grants longest-common-prefix
  credit ``lcp(A, K) / max(len(A), len(K))`` (two empty paths are equal → 1.0).
  ``config {"given_prefix": g}`` (T088 identify_pathway 1) withholds credit for
  the first ``g`` nodes when the question already states them:
  ``max(0, lcp - g) / (max(len(A), len(K)) - g)``, so echoing the given start
  scores 0. ``config {"given_suffix": s}`` (T091 AF11) does the same for the
  last ``s`` nodes: they are cut off the key, and off the answer when it ends
  with them, before the prefix ratio — so the stated end earns nothing and
  omitting it costs nothing.
- ``node_id`` — exact equality (1.0/0.0).
- ``scalar`` — tolerance step: 1.0 if ``|a - k| <= config["tol"]`` (default
  0.0, boundary inclusive), else 0.0. A step function is the simplest
  monotone falloff; graded decay can be layered on later via ``config``.
- ``json`` — deep structural equality via Python ``==`` on the (JSON-ish)
  nested values (1.0/0.0).

An unknown ``spec.kind`` raises :class:`ValueError` (fail visibly).

An answer of the wrong SHAPE for its kind (T088 grade 1–2) raises
:class:`MalformedAnswer` naming the mismatch: ``node_set`` wants a list,
tuple or set of hashable ids (a bare string is one id's characters, not a
set), ``ordered_path`` a list or tuple, ``scalar`` a real number (``bool``
excluded). The runner catches it and scores the trial 0.0 with the reason on
the record (``TrialRecord.grade_error``) — a wrong-shaped answer is a wrong
answer, kept in the denominator (the M46 rejection-as-data rule), never an
error record. ``config["partial"]`` must be a real ``bool`` (a ``"false"``
string is truthy) and is refused otherwise.
"""

from __future__ import annotations

import math
import numbers
from typing import Any, Callable

import numpy as np

from .types import Answer, GraderSpec, Timeline


class MalformedAnswer(ValueError):
    """An answer whose shape does not fit its grader kind (T088 grade 1–2):
    scored 0.0 by the runner, with this message on the record."""


_SEQUENCES = (list, tuple)
_COLLECTIONS = (list, tuple, set, frozenset)


def _as_set(a: Any) -> set:
    if not isinstance(a, _COLLECTIONS):
        raise MalformedAnswer(f"node_set answer must be a list or set of ids, got {type(a).__name__} {a!r}"[:200])
    try:
        return set(a)
    except TypeError as exc:
        raise MalformedAnswer(f"node_set answer holds an unhashable element: {exc}") from None


def _as_path(a: Any) -> list:
    if not isinstance(a, _SEQUENCES):
        raise MalformedAnswer(f"ordered_path answer must be a list of ids, got {type(a).__name__} {a!r}"[:200])
    return list(a)


def _as_real(a: Any) -> float:
    # T091 A7 — any ``numbers.Real`` but a bool (numpy scalars included, as
    # ``SimConfig`` accepts them); a non-finite value stays malformed.
    if isinstance(a, bool) or isinstance(a, np.bool_) or not isinstance(a, numbers.Real):
        raise MalformedAnswer(f"scalar answer must be a number, got {type(a).__name__} {a!r}"[:200])
    value = float(a)
    if not math.isfinite(value):
        raise MalformedAnswer(f"scalar answer must be finite, got {a!r}"[:200])
    return value


def _partial(config: Any, default: bool) -> bool:
    value = config.get("partial", default)
    if not isinstance(value, bool):
        raise ValueError(f"grader config 'partial' must be a bool, got {value!r}")
    return value


def _given_prefix(config: Any) -> int:
    value = config.get("given_prefix", 0)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"grader config 'given_prefix' must be a non-negative int, got {value!r}")
    return value


def _given_suffix(config: Any) -> int:
    value = config.get("given_suffix", 0)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"grader config 'given_suffix' must be a non-negative int, got {value!r}")
    return value


def _grade_node_set(a: Any, k: Any, partial: bool) -> float:
    """Jaccard ``|A∩K| / |A∪K|`` (partial) or exact set equality."""
    a_set, k_set = _as_set(a), set(k)
    if not partial:
        return 1.0 if a_set == k_set else 0.0
    union = a_set | k_set
    if not union:
        return 1.0  # both empty -> equal
    return len(a_set & k_set) / len(union)


def _grade_ordered_path(a: Any, k: Any, partial: bool, given: int = 0, given_end: int = 0) -> float:
    """1.0 iff equal; longest-common-prefix ratio when ``partial``, the first
    ``given`` and last ``given_end`` nodes (stated by the question) earning
    nothing."""
    a_seq, k_seq = _as_path(a), list(k)
    if a_seq == k_seq:
        return 1.0
    if not partial:
        return 0.0
    if given_end:
        tail = k_seq[-given_end:]
        if a_seq[-given_end:] == tail:
            a_seq = a_seq[:-given_end]
        k_seq = k_seq[:-given_end]
    lcp = 0
    for x, y in zip(a_seq, k_seq):
        if x != y:
            break
        lcp += 1
    span = max(len(a_seq), len(k_seq)) - given
    if span <= 0:
        return 0.0
    return max(0, lcp - given) / span


def _grade_scalar(a: Any, k: Any, tol: float) -> float:
    """1.0 if ``|a - k| <= tol`` (boundary inclusive), else 0.0."""
    return 1.0 if abs(_as_real(a) - float(k)) <= tol else 0.0


def grade_answer(answer: Answer, key: Answer, spec: GraderSpec) -> float:
    """Grade ``answer`` against ``key``, dispatching on ``spec.kind``.

    Returns a score in ``[0.0, 1.0]``. Values are opaque JSON-ish payloads
    compared structurally; the exact per-kind formulas are documented in the
    module docstring. Partial-credit behaviour is driven by ``spec.config``
    (``"partial"`` for node_set / ordered_path, ``"tol"`` for scalar).
    Raises :class:`ValueError` on an unknown kind or a non-bool
    ``partial``, and :class:`MalformedAnswer` on an answer of the wrong shape.
    """
    config = spec.config
    if spec.kind == "node_set":
        return _grade_node_set(
            answer.value, key.value, partial=_partial(config, True)
        )
    if spec.kind == "ordered_path":
        return _grade_ordered_path(
            answer.value, key.value, partial=_partial(config, False),
            given=_given_prefix(config), given_end=_given_suffix(config),
        )
    if spec.kind == "node_id":
        return 1.0 if answer.value == key.value else 0.0
    if spec.kind == "scalar":
        return _grade_scalar(answer.value, key.value, tol=float(config.get("tol", 0.0)))
    if spec.kind == "json":
        return 1.0 if answer.value == key.value else 0.0
    raise ValueError(f"unknown grader kind: {spec.kind!r}")


def grade_outcome(trace: Timeline, scorer: Callable[[Any], float], target: Any) -> float:
    """Score an outcome by invoking the opaque ``scorer`` on the whole ``trace``.

    The scorer receives the full :class:`~alienbio.suite.types.Timeline` (it picks
    whatever it needs, e.g. the final :class:`~alienbio.protocols.bio.WorldState`)
    and its return value is passed through as a float, unmodified. ``target`` is
    opaque context kept for interface symmetry with
    :class:`~alienbio.suite.types.OutcomeObjective`; it is never inspected here —
    a scorer that needs it closes over it. The trace is never inspected
    semantically by this function.
    """
    del target  # opaque; scorers close over any context they need
    return float(scorer(trace))
