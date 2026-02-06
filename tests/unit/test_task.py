"""Tests for M8.1 Task Protocol and M8.3 Hardcoded Predict Task."""

from __future__ import annotations

import pytest

from alienbio.bio import (
    AgentInterface,
    AtomImpl,
    BioSystem,
    ChemistryImpl,
    MoleculeImpl,
    PredictTask,
    ReactionImpl,
    StateImpl,
    Task,
    TaskResult,
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


# === M8.1 Task Protocol ===

class TestTaskProtocol:

    def test_task_is_abstract(self):
        """Cannot instantiate Task directly."""
        with pytest.raises(TypeError):
            Task()  # type: ignore[abstract]

    def test_predict_task_is_task(self):
        task = PredictTask("A", steps=10)
        assert isinstance(task, Task)

    def test_predict_task_has_name(self):
        task = PredictTask("A", steps=10)
        assert task.name == "predict"

    def test_predict_task_has_description(self):
        task = PredictTask("A", steps=10)
        desc = task.description
        assert "A" in desc
        assert "10" in desc

    def test_predict_task_properties(self):
        task = PredictTask("B", steps=50)
        assert task.target_molecule == "B"
        assert task.steps == 50

    def test_task_result_dataclass(self):
        result = TaskResult(score=0.85, details={"x": 1})
        assert result.score == 0.85
        assert result.details == {"x": 1}


# === M8.3 Hardcoded Predict Task ===

class TestPredictTaskScoring:

    def test_perfect_prediction_scores_one(self):
        """M8.3 key test: perfect prediction scores 1.0."""
        system = _make_system()
        iface = AgentInterface(system)
        task = PredictTask("A", steps=10, tolerance=0.1)

        # Compute actual answer by running a copy
        copy_sys = _make_system()
        copy_sys.run(10)
        actual = copy_sys.state["A"]

        result = task.score(iface, actual)
        assert result.score == pytest.approx(1.0)

    def test_random_prediction_scores_low(self):
        """M8.3 key test: random prediction scores < 0.5."""
        system = _make_system()
        iface = AgentInterface(system)
        task = PredictTask("A", steps=10, tolerance=0.1)

        # Wildly wrong prediction
        result = task.score(iface, 999.0)
        assert result.score < 0.5

    def test_close_prediction_scores_high(self):
        system = _make_system()
        iface = AgentInterface(system)
        task = PredictTask("A", steps=10, tolerance=0.1)

        # Compute actual and predict slightly off
        copy_sys = _make_system()
        copy_sys.run(10)
        actual = copy_sys.state["A"]

        result = task.score(iface, actual * 1.05)  # 5% off
        assert result.score > 0.9

    def test_score_result_has_details(self):
        system = _make_system()
        iface = AgentInterface(system)
        task = PredictTask("A", steps=10)

        result = task.score(iface, 5.0)
        assert "predicted" in result.details
        assert "actual" in result.details
        assert "error" in result.details
        assert "steps" in result.details
        assert "target" in result.details

    def test_score_in_zero_one_range(self):
        system = _make_system()
        iface = AgentInterface(system)
        task = PredictTask("A", steps=10)

        result = task.score(iface, -100.0)
        assert 0.0 <= result.score <= 1.0

    def test_predict_different_molecules(self):
        system = _make_system()
        iface = AgentInterface(system)
        task_b = PredictTask("B", steps=10, tolerance=0.1)

        copy_sys = _make_system()
        copy_sys.run(10)
        actual_b = copy_sys.state["B"]

        result = task_b.score(iface, actual_b)
        assert result.score == pytest.approx(1.0)

    def test_zero_actual_with_zero_prediction(self):
        """When actual is 0 and prediction is 0, score should be 1.0."""
        carbon = AtomImpl("C", name="Carbon", atomic_weight=12.0)
        a = MoleculeImpl("A", atoms={carbon: 1}, bdepth=0, dat=MockDat("mol/A"))
        b = MoleculeImpl("B", atoms={carbon: 2}, bdepth=0, dat=MockDat("mol/B"))
        # No reactions — concentrations stay constant
        chem = ChemistryImpl(
            "test", atoms={"C": carbon},
            molecules={"A": a, "B": b}, reactions={},
            dat=MockDat("chem/test"),
        )
        state = StateImpl(chem, initial={"A": 0.0, "B": 0.0})
        system = BioSystem(chem, state, dt=0.1)
        iface = AgentInterface(system)

        task = PredictTask("A", steps=5, tolerance=0.1)
        result = task.score(iface, 0.0)
        assert result.score == pytest.approx(1.0)
