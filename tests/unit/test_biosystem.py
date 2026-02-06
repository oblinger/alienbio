"""Tests for M6.1 BioSystem Assembly."""

from __future__ import annotations

import pytest

from alienbio.bio import (
    AtomImpl,
    BioSystem,
    ChemistryImpl,
    MoleculeImpl,
    ReactionImpl,
    ReferenceSimulatorImpl,
    StateImpl,
)


class MockDat:
    """Mock DAT for testing."""

    def __init__(self, path: str):
        self._path = path

    def get_path_name(self) -> str:
        return self._path

    def get_path(self) -> str:
        return f"/tmp/{self._path}"

    def save(self) -> None:
        pass


# --- Helpers ---

def _make_chemistry(n_molecules: int = 3, n_reactions: int = 1) -> ChemistryImpl:
    """Create a simple chemistry with n molecules and n reactions."""
    carbon = AtomImpl("C", name="Carbon", atomic_weight=12.0)

    molecules = {}
    for i in range(n_molecules):
        name = f"M{i}"
        molecules[name] = MoleculeImpl(
            name, atoms={carbon: i + 1}, bdepth=0,
            dat=MockDat(f"mol/{name}"),
        )

    reactions = {}
    mol_list = list(molecules.values())
    for i in range(min(n_reactions, n_molecules - 1)):
        name = f"R{i}"
        reactions[name] = ReactionImpl(
            name,
            reactants={mol_list[i]: 1.0},
            products={mol_list[i + 1]: 1.0},
            rate=0.1,
            dat=MockDat(f"rxn/{name}"),
        )

    return ChemistryImpl(
        "test_chem",
        atoms={"C": carbon},
        molecules=molecules,
        reactions=reactions,
        dat=MockDat("chem/test_chem"),
    )


# === BioSystem Construction ===

class TestBioSystemConstruction:

    def test_create_with_chemistry_only(self):
        chem = _make_chemistry()
        system = BioSystem(chem)
        assert system.chemistry is chem
        assert system.num_molecules == 3
        assert system.num_reactions == 1

    def test_create_with_state(self):
        chem = _make_chemistry()
        state = StateImpl(chem, initial={"M0": 5.0, "M1": 3.0, "M2": 0.0})
        system = BioSystem(chem, state)
        assert system.state is state
        assert system.state["M0"] == 5.0

    def test_create_with_custom_simulator(self):
        chem = _make_chemistry()
        sim = ReferenceSimulatorImpl(chem, dt=0.5)
        system = BioSystem(chem, simulator=sim)
        assert system.simulator is sim
        assert system.simulator.dt == 0.5

    def test_default_state_is_zeroed(self):
        chem = _make_chemistry()
        system = BioSystem(chem)
        for name in chem.molecules:
            assert system.state[name] == 0.0

    def test_default_simulator_created(self):
        chem = _make_chemistry()
        system = BioSystem(chem, dt=0.25)
        assert isinstance(system.simulator, ReferenceSimulatorImpl)
        assert system.simulator.dt == 0.25


# === Molecule and Reaction Counts ===

class TestCounts:

    @pytest.mark.parametrize("n_mol", [1, 3, 5, 10])
    def test_molecule_count(self, n_mol):
        chem = _make_chemistry(n_molecules=n_mol, n_reactions=0)
        system = BioSystem(chem)
        assert system.num_molecules == n_mol

    @pytest.mark.parametrize("n_rxn", [0, 1, 2, 4])
    def test_reaction_count(self, n_rxn):
        chem = _make_chemistry(n_molecules=max(n_rxn + 1, 2), n_reactions=n_rxn)
        system = BioSystem(chem)
        assert system.num_reactions == n_rxn

    def test_empty_chemistry(self):
        chem = ChemistryImpl("empty", dat=MockDat("chem/empty"))
        system = BioSystem(chem)
        assert system.num_molecules == 0
        assert system.num_reactions == 0


# === Random Initialization ===

class TestRandomInitialization:

    def test_random_sets_all_molecules(self):
        chem = _make_chemistry(n_molecules=5, n_reactions=0)
        system = BioSystem.random(chem, seed=42)
        for name in chem.molecules:
            assert system.state[name] >= 0.0

    def test_random_respects_bounds(self):
        chem = _make_chemistry(n_molecules=10, n_reactions=0)
        system = BioSystem.random(chem, seed=0, min_conc=1.0, max_conc=5.0)
        for name in chem.molecules:
            assert 1.0 <= system.state[name] <= 5.0

    def test_random_deterministic_with_seed(self):
        chem = _make_chemistry()
        s1 = BioSystem.random(chem, seed=99)
        s2 = BioSystem.random(chem, seed=99)
        for name in chem.molecules:
            assert s1.state[name] == s2.state[name]

    def test_random_different_seeds_differ(self):
        chem = _make_chemistry(n_molecules=5, n_reactions=0)
        s1 = BioSystem.random(chem, seed=0)
        s2 = BioSystem.random(chem, seed=1)
        values1 = [s1.state[n] for n in chem.molecules]
        values2 = [s2.state[n] for n in chem.molecules]
        assert values1 != values2

    def test_random_default_range(self):
        chem = _make_chemistry(n_molecules=5, n_reactions=0)
        system = BioSystem.random(chem, seed=42)
        for name in chem.molecules:
            assert 0.0 <= system.state[name] <= 10.0

    def test_random_passes_dt(self):
        chem = _make_chemistry()
        system = BioSystem.random(chem, seed=0, dt=0.01)
        assert system.simulator.dt == 0.01


# === Simulation ===

class TestSimulation:

    def test_step_advances_state(self):
        chem = _make_chemistry(n_molecules=3, n_reactions=1)
        state = StateImpl(chem, initial={"M0": 10.0, "M1": 0.0, "M2": 0.0})
        system = BioSystem(chem, state)

        initial_m0 = system.state["M0"]
        system.step()
        # M0 should decrease (it's a reactant)
        assert system.state["M0"] < initial_m0

    def test_step_returns_new_state(self):
        chem = _make_chemistry()
        system = BioSystem(chem, StateImpl(chem, initial={"M0": 5.0}))
        result = system.step()
        assert result is system.state

    def test_run_returns_timeline(self):
        chem = _make_chemistry()
        system = BioSystem(chem, StateImpl(chem, initial={"M0": 5.0}))
        timeline = system.run(steps=10)
        assert len(timeline) == 11  # initial + 10 steps

    def test_run_updates_internal_state(self):
        chem = _make_chemistry()
        system = BioSystem(chem, StateImpl(chem, initial={"M0": 10.0}))
        timeline = system.run(steps=5)
        # Internal state should match the final timeline entry
        for name in chem.molecules:
            assert system.state[name] == timeline[-1][name]

    def test_run_with_reaction_produces_product(self):
        chem = _make_chemistry(n_molecules=2, n_reactions=1)
        system = BioSystem(chem, StateImpl(chem, initial={"M0": 10.0, "M1": 0.0}))
        system.run(steps=20)
        # M1 should have increased (product of R0: M0 -> M1)
        assert system.state["M1"] > 0.0


# === Repr ===

class TestRepr:

    def test_repr_format(self):
        chem = _make_chemistry(n_molecules=4, n_reactions=2)
        system = BioSystem(chem)
        r = repr(system)
        assert "molecules=4" in r
        assert "reactions=2" in r
        assert "dt=1.0" in r
