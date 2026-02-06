"""Tests for M12 Test Harness."""

from __future__ import annotations

import json

import pytest

from alienbio.bio import (
    AgentInterface,
    AtomImpl,
    BioSystem,
    ChemistryImpl,
    ExperimentResult,
    MoleculeImpl,
    PredictTask,
    ReactionImpl,
    StateImpl,
    TestResults,
    TestSuite,
    run_suite,
)


class MockDat:
    def __init__(self, path: str):
        self._path = path
    def get_path_name(self) -> str:
        return self._path
    def get_path(self) -> str:
        return f"/tmp/{self._path}"
    def save(self) -> None:
        pass


def _make_system() -> BioSystem:
    carbon = AtomImpl("C", name="Carbon", atomic_weight=12.0)
    a = MoleculeImpl("A", atoms={carbon: 1}, bdepth=0, dat=MockDat("mol/A"))
    b = MoleculeImpl("B", atoms={carbon: 2}, bdepth=0, dat=MockDat("mol/B"))
    r1 = ReactionImpl(
        "r1", reactants={a: 1.0}, products={b: 1.0},
        rate=lambda state: 0.1 * state["A"],
        dat=MockDat("rxn/r1"),
    )
    chem = ChemistryImpl(
        "test", atoms={"C": carbon},
        molecules={"A": a, "B": b}, reactions={"r1": r1},
        dat=MockDat("chem/test"),
    )
    state = StateImpl(chem, initial={"A": 10.0, "B": 0.0})
    return BioSystem(chem, state, dt=0.1)


# === M12.1 Test Definition ===

class TestTestSuite:

    def test_create_suite(self):
        suite = TestSuite(name="basic")
        assert suite.name == "basic"
        assert suite.count == 0

    def test_add_experiments(self):
        """M12.1 key test: create Test with 10 experiments, assert count matches."""
        suite = TestSuite(name="batch")
        for _ in range(10):
            iface = AgentInterface(_make_system())
            task = PredictTask("A", steps=5)
            suite.add(iface, task)
        assert suite.count == 10


# === M12.2 Execution Runner ===

class TestRunSuite:

    def test_run_returns_results(self):
        suite = TestSuite(name="test")
        for _ in range(5):
            iface = AgentInterface(_make_system())
            task = PredictTask("A", steps=5)
            suite.add(iface, task)

        def agent(interface, t):
            return 5.0

        results = run_suite(suite, agent)
        assert isinstance(results, TestResults)

    def test_run_5_experiments_5_scores(self):
        """M12.2 key test: run batch of 5 experiments, receive 5 scores."""
        suite = TestSuite(name="test")
        for _ in range(5):
            iface = AgentInterface(_make_system())
            task = PredictTask("A", steps=5)
            suite.add(iface, task)

        def agent(interface, t):
            return 5.0

        results = run_suite(suite, agent)
        assert results.count == 5
        assert len(results.scores) == 5
        for s in results.scores:
            assert isinstance(s, float)

    def test_mean_score(self):
        suite = TestSuite(name="test")
        for _ in range(3):
            iface = AgentInterface(_make_system())
            task = PredictTask("A", steps=5)
            suite.add(iface, task)

        def agent(interface, t):
            return 5.0

        results = run_suite(suite, agent)
        assert 0.0 <= results.mean_score <= 1.0

    def test_scores_by_task(self):
        suite = TestSuite(name="test")
        for _ in range(3):
            iface = AgentInterface(_make_system())
            suite.add(iface, PredictTask("A", steps=5))
        for _ in range(2):
            iface = AgentInterface(_make_system())
            suite.add(iface, PredictTask("B", steps=5))

        def agent(interface, t):
            return 5.0

        results = run_suite(suite, agent)
        by_task = results.scores_by_task()
        assert "predict" in by_task
        assert len(by_task["predict"]) == 5

    def test_suite_name_in_results(self):
        suite = TestSuite(name="my_suite")
        iface = AgentInterface(_make_system())
        suite.add(iface, PredictTask("A", steps=5))

        def agent(interface, t):
            return 5.0

        results = run_suite(suite, agent)
        assert results.suite_name == "my_suite"


# === M12.3 Result Analysis ===

class TestResultsExport:

    def test_to_json_and_back(self):
        """M12.3 key test: export to JSON, re-import, assert data integrity."""
        results = TestResults(
            suite_name="test_suite",
            results=[
                ExperimentResult("predict", 0.95, 9.5, {"actual": 10.0}),
                ExperimentResult("predict", 0.80, 8.0, {"actual": 10.0}),
                ExperimentResult("diagnose", 1.0, 2, {"correct": True}),
            ],
        )

        json_str = results.to_json()
        restored = TestResults.from_json(json_str)

        assert restored.suite_name == "test_suite"
        assert restored.count == 3
        assert restored.scores == [0.95, 0.80, 1.0]

    def test_to_dict_structure(self):
        results = TestResults(
            suite_name="test",
            results=[
                ExperimentResult("predict", 0.9, 9.0, {"a": 1}),
            ],
        )
        d = results.to_dict()
        assert d["suite_name"] == "test"
        assert d["count"] == 1
        assert "mean_score" in d
        assert len(d["results"]) == 1

    def test_json_is_valid(self):
        results = TestResults(
            suite_name="test",
            results=[
                ExperimentResult("predict", 0.5, 5.0, {"x": [1, 2, 3]}),
            ],
        )
        json_str = results.to_json()
        parsed = json.loads(json_str)
        assert isinstance(parsed, dict)

    def test_empty_results(self):
        results = TestResults(suite_name="empty", results=[])
        assert results.count == 0
        assert results.mean_score == 0.0
        assert results.scores == []

    def test_roundtrip_preserves_details(self):
        results = TestResults(
            suite_name="rt",
            results=[
                ExperimentResult("predict", 0.9, 9.0, {"nested": {"a": 1}}),
            ],
        )
        restored = TestResults.from_json(results.to_json())
        assert restored.results[0].details == {"nested": {"a": 1}}
