"""Tests for M8.2 Experiment Protocol."""

from __future__ import annotations

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
    run_experiment,
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
    """BioSystem with A->B at rate 0.1*[A], dt=0.1."""
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


class TestRunExperiment:

    def test_returns_experiment_result(self):
        """M8.2 key test: run experiment with mock agent, returns numeric score."""
        iface = AgentInterface(_make_system())
        task = PredictTask("A", steps=10)

        def mock_agent(interface, t):
            return 5.0  # some prediction

        result = run_experiment(iface, task, mock_agent)
        assert isinstance(result, ExperimentResult)
        assert isinstance(result.score, float)

    def test_perfect_agent_scores_one(self):
        iface = AgentInterface(_make_system())
        task = PredictTask("A", steps=10, tolerance=0.1)

        # Agent that computes exact answer
        copy_sys = _make_system()
        copy_sys.run(10)
        exact = copy_sys.state["A"]

        def perfect_agent(interface, t):
            return exact

        result = run_experiment(iface, task, perfect_agent)
        assert result.score == pytest.approx(1.0)

    def test_bad_agent_scores_low(self):
        iface = AgentInterface(_make_system())
        task = PredictTask("A", steps=10, tolerance=0.1)

        def bad_agent(interface, t):
            return 999.0

        result = run_experiment(iface, task, bad_agent)
        assert result.score < 0.5

    def test_result_has_task_name(self):
        iface = AgentInterface(_make_system())
        task = PredictTask("A", steps=10)

        def agent(interface, t):
            return 5.0

        result = run_experiment(iface, task, agent)
        assert result.task_name == "predict"

    def test_result_has_prediction(self):
        iface = AgentInterface(_make_system())
        task = PredictTask("A", steps=10)

        def agent(interface, t):
            return 42.0

        result = run_experiment(iface, task, agent)
        assert result.prediction == 42.0

    def test_result_has_details(self):
        iface = AgentInterface(_make_system())
        task = PredictTask("A", steps=10)

        def agent(interface, t):
            return 5.0

        result = run_experiment(iface, task, agent)
        assert "actual" in result.details
        assert "predicted" in result.details

    def test_agent_can_use_interface(self):
        """Agent can measure the system before predicting."""
        iface = AgentInterface(_make_system())
        task = PredictTask("A", steps=10, tolerance=0.1)

        def smart_agent(interface, t):
            # Agent reads current concentration
            current = interface.measure("concentration", molecule="A")
            # Naive estimate: assume some decay
            return current * 0.9

        result = run_experiment(iface, task, smart_agent)
        # Should get a reasonable score (not perfect, not terrible)
        assert 0.0 <= result.score <= 1.0

    def test_experiment_result_dataclass(self):
        r = ExperimentResult(
            task_name="test", score=0.5,
            prediction=3.0, details={"a": 1},
        )
        assert r.task_name == "test"
        assert r.score == 0.5
        assert r.prediction == 3.0
        assert r.details == {"a": 1}
