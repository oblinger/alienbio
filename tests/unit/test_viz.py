"""Tests for M20 Visualization module."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.figure import Figure

from alienbio.bio import (
    AtomImpl,
    BioSystem,
    ChemistryImpl,
    ComparisonTable,
    AgentStats,
    MoleculeImpl,
    ReactionImpl,
    StateImpl,
    CompartmentTreeImpl,
    WorldStateImpl,
    Baseline,
    HealthRange,
    Symptom,
)
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
    envelope_timeline,
    difficulty_curve_plot,
    agent_comparison_chart,
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


# --- Fixtures ---

def _make_abc_system() -> BioSystem:
    """3-molecule A<->B<->C reversible system."""
    c_atom = AtomImpl("C", name="Carbon", atomic_weight=12.0)
    a = MoleculeImpl("A", atoms={c_atom: 1}, bdepth=0, dat=MockDat("mol/A"))
    b = MoleculeImpl("B", atoms={c_atom: 1}, bdepth=0, dat=MockDat("mol/B"))
    c = MoleculeImpl("C", atoms={c_atom: 1}, bdepth=0, dat=MockDat("mol/C"))
    r_ab = ReactionImpl(
        "r_ab", reactants={a: 1.0}, products={b: 1.0},
        rate=lambda s: 0.1 * s["A"], dat=MockDat("rxn/r_ab"),
    )
    r_ba = ReactionImpl(
        "r_ba", reactants={b: 1.0}, products={a: 1.0},
        rate=lambda s: 0.05 * s["B"], dat=MockDat("rxn/r_ba"),
    )
    r_bc = ReactionImpl(
        "r_bc", reactants={b: 1.0}, products={c: 1.0},
        rate=lambda s: 0.08 * s["B"], dat=MockDat("rxn/r_bc"),
    )
    r_cb = ReactionImpl(
        "r_cb", reactants={c: 1.0}, products={b: 1.0},
        rate=lambda s: 0.04 * s["C"], dat=MockDat("rxn/r_cb"),
    )
    chem = ChemistryImpl(
        "abc", atoms={"C": c_atom},
        molecules={"A": a, "B": b, "C": c},
        reactions={"r_ab": r_ab, "r_ba": r_ba, "r_bc": r_bc, "r_cb": r_cb},
        dat=MockDat("chem/abc"),
    )
    state = StateImpl(chem, initial={"A": 10.0, "B": 0.0, "C": 0.0})
    return BioSystem(chem, state, dt=0.1)


def _make_timeline(n: int = 50) -> list[StateImpl]:
    sys = _make_abc_system()
    return sys.run(n)


def _make_dict_timeline(n: int = 50) -> list[dict[str, float]]:
    tl = _make_timeline(n)
    return [{m: s[m] for m in s} for s in tl]


def _make_world_timeline(steps: int = 30) -> list[WorldStateImpl]:
    tree = CompartmentTreeImpl()
    tree.add_root("body")
    tree.add_child(0, "organ_0")
    tree.add_child(0, "organ_1")

    timeline: list[WorldStateImpl] = []
    for t in range(steps):
        ws = WorldStateImpl(tree=tree, num_molecules=3)
        for comp in range(3):
            for mol in range(3):
                ws.set(comp, mol, float(comp + mol + t * 0.1))
        timeline.append(ws)
    return timeline


# ========================================================================
# Helper tests
# ========================================================================

class TestTimelineToArrays:
    def test_normal(self) -> None:
        tl = _make_timeline(20)
        steps, arrays = timeline_to_arrays(tl)
        assert steps == list(range(21))
        assert set(arrays.keys()) == {"A", "B", "C"}
        assert len(arrays["A"]) == 21

    def test_subset_molecules(self) -> None:
        tl = _make_timeline(10)
        _, arrays = timeline_to_arrays(tl, molecules=["A", "C"])
        assert set(arrays.keys()) == {"A", "C"}

    def test_empty_timeline(self) -> None:
        steps, arrays = timeline_to_arrays([])
        assert steps == []
        assert arrays == {}

    def test_dict_input(self) -> None:
        tl = _make_dict_timeline(10)
        steps, arrays = timeline_to_arrays(tl)
        assert len(steps) == 11
        assert "A" in arrays

    def test_single_step(self) -> None:
        tl = _make_timeline(0)
        steps, arrays = timeline_to_arrays(tl)
        assert steps == [0]
        assert len(arrays["A"]) == 1


class TestWorldTimelineToArrays:
    def test_normal(self) -> None:
        tl = _make_world_timeline(10)
        steps, arrays = world_timeline_to_arrays(tl, molecule_id=0)
        assert steps == list(range(10))
        assert set(arrays.keys()) == {0, 1, 2}
        assert len(arrays[0]) == 10

    def test_subset_compartments(self) -> None:
        tl = _make_world_timeline(5)
        _, arrays = world_timeline_to_arrays(tl, molecule_id=1, compartment_ids=[0, 2])
        assert set(arrays.keys()) == {0, 2}

    def test_empty(self) -> None:
        steps, arrays = world_timeline_to_arrays([], molecule_id=0)
        assert steps == []
        assert arrays == {}


class TestSaveOrShow:
    def test_save_writes_file(self) -> None:
        fig, ax = plt.subplots()
        ax.plot([0, 1], [0, 1])
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "sub" / "test.png"
            save_or_show(fig, path)
            assert path.exists()
            assert path.stat().st_size > 0


# ========================================================================
# Plot tests
# ========================================================================

class TestConcentrationTrajectory:
    def test_returns_figure(self) -> None:
        tl = _make_timeline(20)
        fig = concentration_trajectory(tl)
        assert isinstance(fig, Figure)
        ax = fig.axes[0]
        assert ax.get_xlabel() == "Time Step"
        assert ax.get_ylabel() == "Concentration"
        plt.close(fig)

    def test_single_molecule(self) -> None:
        tl = _make_timeline(10)
        fig = concentration_trajectory(tl, molecules=["A"])
        assert isinstance(fig, Figure)
        plt.close(fig)


class TestEquilibriumConvergence:
    def test_returns_figure_with_two_axes(self) -> None:
        tl = _make_timeline(200)
        fig = equilibrium_convergence(tl, window=50)
        assert isinstance(fig, Figure)
        assert len(fig.axes) == 2  # top + bottom
        plt.close(fig)


class TestPerturbationResponse:
    def test_returns_figure(self) -> None:
        sys = _make_abc_system()
        baseline = sys.run(50)
        sys2 = _make_abc_system()
        sys2.state["A"] = 20.0
        perturbed = sys2.run(50)
        fig = perturbation_response(baseline, perturbed)
        assert isinstance(fig, Figure)
        ax = fig.axes[0]
        assert ax.get_xlabel() == "Time Step"
        plt.close(fig)


class TestSymptomChart:
    def test_returns_figure(self) -> None:
        symptoms = [
            Symptom(molecule="A", value=15.0,
                    healthy_range=HealthRange("A", 3.0, 7.0), deviation=8.0),
            Symptom(molecule="B", value=0.5,
                    healthy_range=HealthRange("B", 2.0, 5.0), deviation=1.5),
        ]
        baseline = Baseline(
            steady_state={"A": 5.0, "B": 3.5},
            ranges=[HealthRange("A", 3.0, 7.0), HealthRange("B", 2.0, 5.0)],
        )
        fig = symptom_chart(symptoms, baseline)
        assert isinstance(fig, Figure)
        plt.close(fig)

    def test_empty_symptoms(self) -> None:
        fig = symptom_chart([])
        assert isinstance(fig, Figure)
        plt.close(fig)


class TestCompartmentHeatmap:
    def test_returns_figure(self) -> None:
        tl = _make_world_timeline(20)
        fig = compartment_heatmap(tl, molecule_id=0)
        assert isinstance(fig, Figure)
        ax = fig.axes[0]
        assert ax.get_xlabel() == "Time Step"
        plt.close(fig)


class TestPopulationDynamics:
    def test_returns_figure(self) -> None:
        tl = _make_timeline(30)
        fig = population_dynamics(tl, species=["A", "B"])
        assert isinstance(fig, Figure)
        ax = fig.axes[0]
        assert ax.get_ylabel() == "Population"
        plt.close(fig)


class TestEnvelopeTimeline:
    def test_returns_figure(self) -> None:
        tl = _make_timeline(30)
        envelope = {"A": (0.0, 12.0)}
        fig = envelope_timeline(tl, envelope, "A")
        assert isinstance(fig, Figure)
        plt.close(fig)


class TestDifficultyCurvePlot:
    def test_returns_figure(self) -> None:
        curves = {
            "oracle": [(1, 1.0), (2, 0.8), (3, 0.6)],
            "random": [(1, 0.5), (2, 0.3), (3, 0.1)],
        }
        fig = difficulty_curve_plot(curves)
        assert isinstance(fig, Figure)
        ax = fig.axes[0]
        assert ax.get_xlabel() == "Difficulty"
        plt.close(fig)


class TestAgentComparisonChart:
    def test_returns_figure(self) -> None:
        table = ComparisonTable(agents=[
            AgentStats("oracle", mean=0.9, std=0.05, min=0.8, max=1.0, count=10, pass_rate=1.0),
            AgentStats("random", mean=0.3, std=0.2, min=0.0, max=0.7, count=10, pass_rate=0.2),
        ])
        fig = agent_comparison_chart(table)
        assert isinstance(fig, Figure)
        ax = fig.axes[0]
        assert ax.get_ylabel() == "Score"
        plt.close(fig)


# ========================================================================
# Edge-case tests
# ========================================================================

class TestEdgeCases:
    def test_short_timeline_convergence(self) -> None:
        """Convergence plot with timeline shorter than window."""
        tl = _make_timeline(5)
        fig = equilibrium_convergence(tl, window=100)
        assert isinstance(fig, Figure)
        plt.close(fig)

    def test_dict_timeline_trajectory(self) -> None:
        tl = _make_dict_timeline(10)
        fig = concentration_trajectory(tl)
        assert isinstance(fig, Figure)
        plt.close(fig)

    def test_save_path_creates_dirs(self) -> None:
        tl = _make_timeline(10)
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "a", "b", "plot.png")
            concentration_trajectory(tl, save_path=path)
            assert os.path.exists(path)
