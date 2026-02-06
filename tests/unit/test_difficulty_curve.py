"""Tests for M8.2 Difficulty Scaling: performance curves."""

from __future__ import annotations

import pytest

from alienbio.bio import (
    AtomImpl,
    BioSystem,
    ChemistryImpl,
    MoleculeImpl,
    PredictTask,
    ReactionImpl,
    StateImpl,
    AgentInterface,
)
from alienbio.scenarios.difficulty_curve import (
    DifficultyLevel,
    DifficultyPoint,
    DifficultyCurve,
    DifficultySpec,
    measure_difficulty_curve,
    compare_difficulty_curves,
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
    """Simple system for testing."""
    carbon = AtomImpl("C", name="Carbon", atomic_weight=12.0)
    a = MoleculeImpl("A", atoms={carbon: 1}, bdepth=0, dat=MockDat("mol/A"))
    b = MoleculeImpl("B", atoms={carbon: 2}, bdepth=0, dat=MockDat("mol/B"))

    source = ReactionImpl(
        "source", reactants={}, products={a: 1.0},
        rate=1.0, dat=MockDat("rxn/source"),
    )
    degrade = ReactionImpl(
        "degrade", reactants={a: 1.0}, products={},
        rate=lambda state: 0.1 * state["A"],
        dat=MockDat("rxn/degrade"),
    )
    chem = ChemistryImpl(
        "test", atoms={"C": carbon},
        molecules={"A": a, "B": b},
        reactions={"source": source, "degrade": degrade},
        dat=MockDat("chem/test"),
    )
    state = StateImpl(chem, initial={"A": 1.0, "B": 0.0})
    return BioSystem(chem, state, dt=0.1)


def _perfect_agent(interface, task):
    """Agent that always returns exact prediction (cheats by running sim)."""
    system = interface.system
    system.run(task.steps)
    return interface.measure("concentration", molecule=task.target_molecule)


def _bad_agent(interface, task):
    """Agent that always predicts 0."""
    return 0.0


# === DifficultyLevel ===

class TestDifficultyLevel:

    def test_dataclass(self):
        dl = DifficultyLevel(level=1, label="easy")
        assert dl.level == 1
        assert dl.label == "easy"
        assert dl.tasks == []

    def test_with_tasks(self):
        task = PredictTask("A", steps=10)
        dl = DifficultyLevel(level=2, label="medium", tasks=[task])
        assert len(dl.tasks) == 1


# === DifficultyPoint ===

class TestDifficultyPoint:

    def test_dataclass(self):
        p = DifficultyPoint(
            level=1, label="easy", mean_score=0.8,
            scores=[0.7, 0.9], count=2, pass_rate=1.0,
        )
        assert p.level == 1
        assert p.mean_score == 0.8
        assert p.count == 2


# === DifficultyCurve ===

class TestDifficultyCurve:

    def test_levels_and_scores(self):
        points = [
            DifficultyPoint(1, "easy", 0.9, [0.9], 1, 1.0),
            DifficultyPoint(2, "medium", 0.6, [0.6], 1, 1.0),
            DifficultyPoint(3, "hard", 0.2, [0.2], 1, 0.0),
        ]
        curve = DifficultyCurve("test_agent", points)
        assert curve.levels == [1, 2, 3]
        assert curve.mean_scores == [0.9, 0.6, 0.2]

    def test_monotonic_decreasing(self):
        points = [
            DifficultyPoint(1, "easy", 0.9, [], 1, 1.0),
            DifficultyPoint(2, "medium", 0.6, [], 1, 1.0),
            DifficultyPoint(3, "hard", 0.2, [], 1, 0.0),
        ]
        curve = DifficultyCurve("agent", points)
        assert curve.is_monotonic_decreasing()

    def test_not_monotonic(self):
        points = [
            DifficultyPoint(1, "easy", 0.5, [], 1, 1.0),
            DifficultyPoint(2, "medium", 0.9, [], 1, 1.0),  # goes up
            DifficultyPoint(3, "hard", 0.2, [], 1, 0.0),
        ]
        curve = DifficultyCurve("agent", points)
        assert not curve.is_monotonic_decreasing()

    def test_monotonic_with_tolerance(self):
        points = [
            DifficultyPoint(1, "easy", 0.9, [], 1, 1.0),
            DifficultyPoint(2, "medium", 0.91, [], 1, 1.0),  # tiny increase
        ]
        curve = DifficultyCurve("agent", points)
        assert not curve.is_monotonic_decreasing()
        assert curve.is_monotonic_decreasing(tolerance=0.05)

    def test_capability_threshold(self):
        points = [
            DifficultyPoint(1, "easy", 0.9, [], 1, 1.0),
            DifficultyPoint(2, "medium", 0.6, [], 1, 1.0),
            DifficultyPoint(3, "hard", 0.3, [], 1, 0.0),
        ]
        curve = DifficultyCurve("agent", points)
        assert curve.capability_threshold(min_score=0.5) == 2
        assert curve.capability_threshold(min_score=0.8) == 1
        assert curve.capability_threshold(min_score=0.95) is None

    def test_to_dict(self):
        points = [
            DifficultyPoint(1, "easy", 0.9, [0.9], 1, 1.0),
        ]
        curve = DifficultyCurve("agent", points)
        d = curve.to_dict()
        assert d["agent_name"] == "agent"
        assert len(d["points"]) == 1
        assert d["points"][0]["level"] == 1

    def test_empty_curve(self):
        curve = DifficultyCurve("agent", [])
        assert curve.levels == []
        assert curve.mean_scores == []
        assert curve.capability_threshold() is None


# === DifficultySpec ===

class TestDifficultySpec:

    def test_add_level(self):
        spec = DifficultySpec(levels=[])
        spec.add_level(1, "easy")
        spec.add_level(2, "hard")
        assert spec.num_levels == 2

    def test_add_level_with_tasks(self):
        spec = DifficultySpec(levels=[])
        task = PredictTask("A", steps=10)
        dl = spec.add_level(1, "easy", tasks=[task])
        assert len(dl.tasks) == 1


# === measure_difficulty_curve ===

class TestMeasureDifficultyCurve:

    def test_measures_curve(self):
        """Run agent on tasks at different difficulties."""
        system = _make_system()
        interface = AgentInterface(system)

        spec = DifficultySpec(levels=[])
        # Easy: predict after 1 step
        spec.add_level(1, "easy", tasks=[PredictTask("A", steps=1)])
        # Hard: predict after 100 steps
        spec.add_level(2, "hard", tasks=[PredictTask("A", steps=100)])

        # Bad agent always predicts 0
        curve = measure_difficulty_curve(spec, interface, _bad_agent, agent_name="bad")

        assert len(curve.points) == 2
        assert curve.points[0].level == 1
        assert curve.points[1].level == 2
        assert curve.agent_name == "bad"

    def test_empty_level(self):
        """Level with no tasks produces zero score."""
        system = _make_system()
        interface = AgentInterface(system)

        spec = DifficultySpec(levels=[])
        spec.add_level(1, "empty")  # no tasks

        curve = measure_difficulty_curve(spec, interface, _bad_agent)
        assert curve.points[0].mean_score == 0.0
        assert curve.points[0].count == 0


# === compare_difficulty_curves ===

class TestCompareDifficultyCurves:

    def test_compare_two_agents(self):
        p1 = [DifficultyPoint(1, "easy", 0.9, [], 1, 1.0)]
        p2 = [DifficultyPoint(1, "easy", 0.3, [], 1, 0.0)]
        c1 = DifficultyCurve("good", p1)
        c2 = DifficultyCurve("bad", p2)

        result = compare_difficulty_curves([c1, c2])
        assert 1 in result["rankings"]
        assert result["rankings"][1][0]["agent"] == "good"

    def test_compare_empty(self):
        result = compare_difficulty_curves([])
        assert result["levels"] == []

    def test_compare_multiple_levels(self):
        p1 = [
            DifficultyPoint(1, "easy", 0.9, [], 1, 1.0),
            DifficultyPoint(2, "hard", 0.5, [], 1, 1.0),
        ]
        p2 = [
            DifficultyPoint(1, "easy", 0.7, [], 1, 1.0),
            DifficultyPoint(2, "hard", 0.8, [], 1, 1.0),
        ]
        c1 = DifficultyCurve("agent_a", p1)
        c2 = DifficultyCurve("agent_b", p2)

        result = compare_difficulty_curves([c1, c2])
        assert result["levels"] == [1, 2]
        # At level 1, agent_a leads
        assert result["rankings"][1][0]["agent"] == "agent_a"
        # At level 2, agent_b leads
        assert result["rankings"][2][0]["agent"] == "agent_b"
