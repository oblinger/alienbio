"""Acceptance tests for the pure graders (answer-vs-key + opaque outcome)."""

from __future__ import annotations

import pytest

from alienbio.bio.compartment_tree import CompartmentTreeImpl
from alienbio.bio.world_state import WorldStateImpl
from alienbio.suite.grade import grade_answer, grade_outcome
from alienbio.suite.types import Answer, GraderSpec, Timeline


# ═══════════════════════════════════════════════════════════════════════════
# grade_answer — table-driven, one row per kind x {perfect, partial, wrong}
# ═══════════════════════════════════════════════════════════════════════════

CASES = [
    # (label, kind, answer_value, key_value, config, expected)
    # -- node_set: Jaccard partial credit by default ------------------------
    ("node_set perfect", "node_set", ["A", "B"], ["B", "A"], {}, 1.0),
    ("node_set half overlap", "node_set", ["A", "B", "C"], ["B", "C", "D"], {}, 0.5),
    ("node_set disjoint", "node_set", ["A", "B"], ["C", "D"], {}, 0.0),
    ("node_set exact-mode equal", "node_set", ["A", "B"], ["B", "A"],
     {"partial": False}, 1.0),
    ("node_set exact-mode overlap", "node_set", ["A", "B", "C"], ["B", "C", "D"],
     {"partial": False}, 0.0),
    # -- ordered_path: equal -> 1.0; LCP ratio when partial ------------------
    ("ordered_path equal", "ordered_path", ["A", "B", "C"], ["A", "B", "C"], {}, 1.0),
    ("ordered_path shared prefix", "ordered_path", ["A", "B", "X"], ["A", "B", "C"],
     {"partial": True}, 2.0 / 3.0),
    ("ordered_path reversed", "ordered_path", ["C", "B", "A"], ["A", "B", "C"],
     {"partial": True}, 0.0),
    ("ordered_path near-miss, no partial", "ordered_path",
     ["A", "B", "X"], ["A", "B", "C"], {}, 0.0),
    # -- node_id: exact only --------------------------------------------------
    ("node_id equal", "node_id", "N7", "N7", {}, 1.0),
    ("node_id different", "node_id", "N7", "N8", {}, 0.0),
    # -- scalar: tolerance step (boundary inclusive) --------------------------
    ("scalar within tol", "scalar", 1.05, 1.0, {"tol": 0.1}, 1.0),
    ("scalar exact tol boundary", "scalar", 1.5, 1.0, {"tol": 0.5}, 1.0),
    ("scalar outside tol", "scalar", 2.0, 1.0, {"tol": 0.1}, 0.0),
    ("scalar default tol, exact", "scalar", 3.0, 3.0, {}, 1.0),
    ("scalar default tol, off", "scalar", 3.0, 3.0001, {}, 0.0),
    # -- json: deep structural equality ---------------------------------------
    ("json deep equal", "json",
     {"a": [1, {"b": 2.5}], "c": "x"}, {"a": [1, {"b": 2.5}], "c": "x"}, {}, 1.0),
    ("json one differing leaf", "json",
     {"a": [1, {"b": 2.5}], "c": "x"}, {"a": [1, {"b": 9.9}], "c": "x"}, {}, 0.0),
]


@pytest.mark.parametrize(
    "kind,answer_value,key_value,config,expected",
    [row[1:] for row in CASES],
    ids=[row[0] for row in CASES],
)
def test_grade_answer_table(kind, answer_value, key_value, config, expected):
    answer = Answer(value=answer_value, kind=kind)
    key = Answer(value=key_value, kind=kind)
    spec = GraderSpec(kind=kind, config=config)
    score = grade_answer(answer, key, spec)
    assert score == pytest.approx(expected)
    assert 0.0 <= score <= 1.0


def test_unknown_kind_raises():
    answer = Answer(value="x", kind="mystery")
    key = Answer(value="x", kind="mystery")
    with pytest.raises(ValueError):
        grade_answer(answer, key, GraderSpec(kind="mystery"))


# ═══════════════════════════════════════════════════════════════════════════
# grade_outcome — opaque scorer over a tiny synthetic Timeline
# ═══════════════════════════════════════════════════════════════════════════

def _snapshot(concentrations: list[float]) -> WorldStateImpl:
    """A self-describing 1-compartment ('c0') WorldState over species (A, B)."""
    tree = CompartmentTreeImpl()
    tree.add_root("c0")
    return WorldStateImpl(
        tree=tree,
        num_molecules=2,
        initial_concentrations=concentrations,
        compartment_ids=["c0"],
        molecule_ids=["A", "B"],
    )


def build_timeline() -> Timeline:
    """Two WorldState snapshots over one compartment and species (A, B); final B = 0.75."""
    s0 = _snapshot([1.0, 0.0])
    s1 = _snapshot([0.25, 0.75])
    return Timeline(times=(0.0, 1.0), states=(s0, s1))


def test_grade_outcome_returns_scorer_value():
    timeline = build_timeline()

    def final_b(tl: Timeline) -> float:
        return tl.states[-1].concentration("c0", "B")

    assert grade_outcome(timeline, final_b, target=None) == pytest.approx(0.75)


def test_grade_outcome_passes_trace_through_opaquely():
    timeline = build_timeline()
    seen: list[object] = []

    def spy_scorer(tl: object) -> float:
        seen.append(tl)
        return 42.0

    # The scorer receives the very Timeline object, and its value is returned as-is
    # (no clamping / normalization); target is opaque and never inspected.
    assert grade_outcome(timeline, spy_scorer, target={"anything": "opaque"}) == 42.0
    assert seen == [timeline]
    assert seen[0] is timeline
