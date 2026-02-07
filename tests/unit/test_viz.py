"""Tests for M20.1-M20.2 Visualization Module."""

from __future__ import annotations

import os
import tempfile

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import matplotlib.figure
import numpy as np
import pytest

from alienbio.bio import (
    AtomImpl,
    BioSystem,
    ChemistryImpl,
    CompartmentTreeImpl,
    MoleculeImpl,
    ReactionImpl,
    StateImpl,
    WorldStateImpl,
)
from alienbio.bio.equilibrium import StabilityResult
from alienbio.bio.perturbation import PerturbationResult
from alienbio.scenarios.disease import Baseline, HealthRange, Symptom
from alienbio.scenarios.organism_features import OperatingEnvelope
from alienbio.scenarios.difficulty_curve import DifficultyCurve, DifficultyPoint
from alienbio.bio.comparison import AgentStats, ComparisonTable

from alienbio.viz import (
    timeline_to_arrays,
    world_timeline_to_arrays,
    save_or_show,
    concentration_trajectory,
    equilibrium_convergence,
    perturbation_response,
    symptom_chart,
    compartment_heatmap,
    population_dynamics,
    difficulty_curve_plot,
    agent_comparison_chart,
    envelope_timeline,
)


# --- Fixtures ---

class MockDat:
    def __init__(self, path: str):
        self._path = path
    def get_path_name(self) -> str:
        return self._path
    def get_path(self) -> str:
        return f"/tmp/{self._path}"
    def save(self) -> None:
        pass


@pytest.fixture
def tmp_png(tmp_path):
    """Provide a temp .png path for saving figures."""
    return str(tmp_path / "test_plot.png")


def _make_chemistry() -> ChemistryImpl:
    """3-molecule chemistry with source/degradation reactions."""
    carbon = AtomImpl("C", name="Carbon", atomic_weight=12.0)
    molecules = {}
    for name in ["A", "B", "C"]:
        molecules[name] = MoleculeImpl(
            name, atoms={carbon: 1}, bdepth=0,
            dat=MockDat(f"mol/{name}"),
        )
    mol_list = list(molecules.values())
    reactions = {
        "R0": ReactionImpl("R0", reactants={mol_list[0]: 1.0},
                           products={mol_list[1]: 1.0}, rate=0.1,
                           dat=MockDat("rxn/R0")),
        "R1": ReactionImpl("R1", reactants={mol_list[1]: 1.0},
                           products={mol_list[2]: 1.0}, rate=0.05,
                           dat=MockDat("rxn/R1")),
    }
    return ChemistryImpl(
        "test_chem", atoms={"C": carbon},
        molecules=molecules, reactions=reactions,
        dat=MockDat("chem/test"),
    )


def _make_timeline(n_steps: int = 50) -> list:
    """Run a system and return timeline."""
    chem = _make_chemistry()
    state = StateImpl(chem, initial={"A": 10.0, "B": 2.0, "C": 0.0})
    system = BioSystem(chem, state)
    return system.run(n_steps)


def _make_world_timeline(n_steps: int = 20) -> list:
    """Create a simple world state timeline."""
    tree = CompartmentTreeImpl()
    root = tree.add_root("body")
    tree.add_child(root, "organ_a")
    tree.add_child(root, "organ_b")
    num_mols = 3

    states = []
    for t in range(n_steps):
        ws = WorldStateImpl(tree, num_mols)
        for comp in range(tree.num_compartments):
            for mol in range(num_mols):
                ws.set(comp, mol, float(t + comp + mol))
        states.append(ws)
    return states


# === Helper Tests ===

class TestTimelineToArrays:

    def test_normal_data(self):
        tl = _make_timeline(30)
        times, data = timeline_to_arrays(tl)
        assert isinstance(times, np.ndarray)
        assert len(times) == 31  # steps + 1
        assert set(data.keys()) == {"A", "B", "C"}
        for arr in data.values():
            assert isinstance(arr, np.ndarray)
            assert len(arr) == 31

    def test_subset_molecules(self):
        tl = _make_timeline(10)
        times, data = timeline_to_arrays(tl, molecules=["A", "C"])
        assert set(data.keys()) == {"A", "C"}

    def test_empty_timeline(self):
        times, data = timeline_to_arrays([])
        assert len(times) == 0
        assert data == {}

    def test_single_step(self):
        tl = _make_timeline(0)
        times, data = timeline_to_arrays(tl)
        assert len(times) == 1


class TestWorldTimelineToArrays:

    def test_normal_data(self):
        tl = _make_world_timeline(15)
        times, data = world_timeline_to_arrays(tl, molecule_id=0)
        assert isinstance(times, np.ndarray)
        assert len(times) == 15
        assert 0 in data and 1 in data and 2 in data

    def test_subset_compartments(self):
        tl = _make_world_timeline(10)
        times, data = world_timeline_to_arrays(tl, molecule_id=1, compartment_ids=[0, 2])
        assert set(data.keys()) == {0, 2}

    def test_empty_timeline(self):
        times, data = world_timeline_to_arrays([], molecule_id=0)
        assert len(times) == 0
        assert data == {}


class TestSaveOrShow:

    def test_saves_to_file(self):
        fig, ax = plt.subplots()
        ax.plot([1, 2, 3], [1, 4, 9])

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test_plot.png")
            save_or_show(fig, path)
            assert os.path.exists(path)
            assert os.path.getsize(path) > 0

    def test_creates_directories(self):
        fig, ax = plt.subplots()
        ax.plot([1, 2], [1, 2])

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "subdir", "nested", "plot.png")
            save_or_show(fig, path)
            assert os.path.exists(path)


# === Plot Function Tests ===

class TestConcentrationTrajectory:

    def test_returns_figure(self, tmp_png):
        tl = _make_timeline(20)
        fig = concentration_trajectory(tl, save_path=tmp_png)
        assert isinstance(fig, matplotlib.figure.Figure)

    def test_with_title(self, tmp_png):
        tl = _make_timeline(10)
        fig = concentration_trajectory(tl, title="My Plot", save_path=tmp_png)
        assert fig.axes[0].get_title() == "My Plot"

    def test_subset_molecules(self, tmp_png):
        tl = _make_timeline(10)
        fig = concentration_trajectory(tl, molecules=["A"], save_path=tmp_png)
        assert isinstance(fig, matplotlib.figure.Figure)


class TestEquilibriumConvergence:

    def test_returns_figure(self, tmp_png):
        tl = _make_timeline(50)
        stability = StabilityResult(
            stable=True, variance={"A": 0.001, "B": 0.002, "C": 0.0005},
            max_variance=0.002, unstable_molecules=[], steps_run=50, window=10,
        )
        fig = equilibrium_convergence(tl, stability, save_path=tmp_png)
        assert isinstance(fig, matplotlib.figure.Figure)
        assert len(fig.axes) == 2  # trajectory + variance subplots


class TestPerturbationResponse:

    def test_returns_figure(self, tmp_png):
        tl1 = _make_timeline(20)
        tl2 = _make_timeline(20)
        result = PerturbationResult(
            recovered=True, baseline_final={"A": 5.0, "B": 3.0, "C": 2.0},
            perturbed_final={"A": 5.1, "B": 3.1, "C": 2.1},
            max_deviation=0.5, recovery_step=15, steps_run=20,
        )
        fig = perturbation_response(tl1, tl2, result, save_path=tmp_png)
        assert isinstance(fig, matplotlib.figure.Figure)

    def test_no_recovery(self, tmp_png):
        tl1 = _make_timeline(10)
        tl2 = _make_timeline(10)
        result = PerturbationResult(
            recovered=False, baseline_final={}, perturbed_final={},
            max_deviation=2.0, recovery_step=None, steps_run=10,
        )
        fig = perturbation_response(tl1, tl2, result, save_path=tmp_png)
        assert isinstance(fig, matplotlib.figure.Figure)


class TestSymptomChart:

    def test_returns_figure(self, tmp_png):
        baseline = Baseline(
            steady_state={"A": 5.0, "B": 3.0},
            ranges=[
                HealthRange("A", 4.0, 6.0),
                HealthRange("B", 2.0, 4.0),
            ],
        )
        symptoms = [
            Symptom("A", 7.5, HealthRange("A", 4.0, 6.0), 1.5),
            Symptom("B", 1.0, HealthRange("B", 2.0, 4.0), 1.0),
        ]
        fig = symptom_chart(symptoms, baseline, save_path=tmp_png)
        assert isinstance(fig, matplotlib.figure.Figure)

    def test_empty_symptoms(self, tmp_png):
        baseline = Baseline(steady_state={}, ranges=[])
        fig = symptom_chart([], baseline, save_path=tmp_png)
        assert isinstance(fig, matplotlib.figure.Figure)


class TestCompartmentHeatmap:

    def test_returns_figure(self, tmp_png):
        tl = _make_world_timeline(20)
        fig = compartment_heatmap(tl, molecule_id=0, save_path=tmp_png)
        assert isinstance(fig, matplotlib.figure.Figure)

    def test_with_names(self, tmp_png):
        tl = _make_world_timeline(10)
        names = {0: "body", 1: "liver", 2: "kidney"}
        fig = compartment_heatmap(tl, molecule_id=1, compartment_names=names,
                                  save_path=tmp_png)
        assert isinstance(fig, matplotlib.figure.Figure)


class TestPopulationDynamics:

    def test_returns_figure(self, tmp_png):
        tl = _make_timeline(30)
        fig = population_dynamics(tl, species=["A", "B"], save_path=tmp_png)
        assert isinstance(fig, matplotlib.figure.Figure)


class TestDifficultyCurvePlot:

    def test_returns_figure(self, tmp_png):
        curves = [
            DifficultyCurve("oracle", [
                DifficultyPoint(1, "easy", 0.95, [1.0, 0.9], 2, 1.0),
                DifficultyPoint(2, "medium", 0.7, [0.8, 0.6], 2, 0.5),
                DifficultyPoint(3, "hard", 0.3, [0.4, 0.2], 2, 0.0),
            ]),
            DifficultyCurve("random", [
                DifficultyPoint(1, "easy", 0.5, [0.6, 0.4], 2, 0.5),
                DifficultyPoint(2, "medium", 0.3, [0.4, 0.2], 2, 0.0),
                DifficultyPoint(3, "hard", 0.1, [0.2, 0.0], 2, 0.0),
            ]),
        ]
        fig = difficulty_curve_plot(curves, save_path=tmp_png)
        assert isinstance(fig, matplotlib.figure.Figure)

    def test_empty_curves(self, tmp_png):
        fig = difficulty_curve_plot([], save_path=tmp_png)
        assert isinstance(fig, matplotlib.figure.Figure)


class TestAgentComparisonChart:

    def test_returns_figure(self, tmp_png):
        table = ComparisonTable(agents=[
            AgentStats("oracle", 0.9, 0.05, 0.8, 1.0, 10, 0.9),
            AgentStats("random", 0.4, 0.2, 0.1, 0.7, 10, 0.3),
            AgentStats("zero", 0.0, 0.0, 0.0, 0.0, 10, 0.0),
        ])
        fig = agent_comparison_chart(table, save_path=tmp_png)
        assert isinstance(fig, matplotlib.figure.Figure)


class TestEnvelopeTimeline:

    def test_returns_figure(self, tmp_png):
        tl = _make_world_timeline(20)
        envelope = OperatingEnvelope()
        envelope.add(molecule_id=0, compartment_id=0, low=2.0, high=15.0)
        fig = envelope_timeline(tl, envelope, molecule_id=0, compartment_id=0,
                                save_path=tmp_png)
        assert isinstance(fig, matplotlib.figure.Figure)

    def test_no_matching_bound(self, tmp_png):
        tl = _make_world_timeline(10)
        envelope = OperatingEnvelope()
        fig = envelope_timeline(tl, envelope, molecule_id=0, compartment_id=0,
                                save_path=tmp_png)
        assert isinstance(fig, matplotlib.figure.Figure)

    def test_with_violations(self, tmp_png):
        tl = _make_world_timeline(20)
        envelope = OperatingEnvelope()
        # Tight bounds that will be violated (values go up to t+comp+mol)
        envelope.add(molecule_id=0, compartment_id=0, low=5.0, high=10.0)
        fig = envelope_timeline(tl, envelope, molecule_id=0, compartment_id=0,
                                save_path=tmp_png)
        assert isinstance(fig, matplotlib.figure.Figure)
