"""Tests for M9.2 Organ Generator and M9.3 Cross-Compartment Simulation."""

from __future__ import annotations

import pytest

from alienbio.bio import (
    AtomImpl,
    ChemistryImpl,
    MoleculeImpl,
    Organism,
    OrganSpec,
    ReactionImpl,
    TransportLink,
    generate_organism,
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


def _make_chemistry() -> ChemistryImpl:
    """Simple chemistry with 3 molecules and 2 reactions."""
    carbon = AtomImpl("C", name="Carbon", atomic_weight=12.0)
    hydrogen = AtomImpl("H", name="Hydrogen", atomic_weight=1.0)

    a = MoleculeImpl("A", atoms={carbon: 1}, bdepth=0, dat=MockDat("mol/A"))
    b = MoleculeImpl("B", atoms={carbon: 2}, bdepth=0, dat=MockDat("mol/B"))
    c = MoleculeImpl("C_mol", atoms={hydrogen: 1}, bdepth=0, dat=MockDat("mol/C"))

    r1 = ReactionImpl(
        "synth", reactants={a: 1.0}, products={b: 1.0},
        rate=0.5, dat=MockDat("rxn/synth"),
    )
    r2 = ReactionImpl(
        "degrade", reactants={b: 1.0}, products={c: 1.0},
        rate=0.3, dat=MockDat("rxn/degrade"),
    )
    return ChemistryImpl(
        "test_chem",
        atoms={"C": carbon, "H": hydrogen},
        molecules={"A": a, "B": b, "C_mol": c},
        reactions={"synth": r1, "degrade": r2},
        dat=MockDat("chem/test"),
    )


# === M9.2: Organ Generator ===

class TestOrganGenerator:

    def test_generates_organism(self):
        """generate_organism returns an Organism."""
        chem = _make_chemistry()
        org = generate_organism(chem, num_organs=3, seed=42)
        assert isinstance(org, Organism)

    def test_compartment_count(self):
        """Organism has body + N organs."""
        chem = _make_chemistry()
        org = generate_organism(chem, num_organs=4, seed=42)
        assert org.num_compartments == 5  # 1 body + 4 organs

    def test_compartment_count_default(self):
        """Default num_organs=3 gives 4 compartments."""
        chem = _make_chemistry()
        org = generate_organism(chem, seed=42)
        assert org.num_compartments == 4  # 1 body + 3 organs

    def test_transport_links_exist(self):
        """Transport links connect adjacent organs (bidirectional)."""
        chem = _make_chemistry()
        org = generate_organism(chem, num_organs=3, seed=42)
        # 2 pairs of adjacent organs (0-1, 1-2), each bidirectional = 4 links
        assert org.num_transport_links == 4

    def test_transport_links_single_organ(self):
        """Single organ has no transport links."""
        chem = _make_chemistry()
        org = generate_organism(chem, num_organs=1, seed=42)
        assert org.num_transport_links == 0

    def test_transport_links_two_organs(self):
        """Two organs have 2 bidirectional links."""
        chem = _make_chemistry()
        org = generate_organism(chem, num_organs=2, seed=42)
        assert org.num_transport_links == 2

    def test_transport_link_dataclass(self):
        """TransportLink has expected fields."""
        link = TransportLink(source=1, target=2, molecule_id=0, rate=0.01)
        assert link.source == 1
        assert link.target == 2
        assert link.molecule_id == 0
        assert link.rate == 0.01

    def test_organ_spec_dataclass(self):
        """OrganSpec has expected fields."""
        spec = OrganSpec(name="liver", reactions=["synth"], initial_concentrations={0: 1.0})
        assert spec.name == "liver"
        assert spec.reactions == ["synth"]

    def test_seed_reproducibility(self):
        """Same seed produces same organism structure."""
        chem = _make_chemistry()
        org1 = generate_organism(chem, num_organs=3, seed=123)
        org2 = generate_organism(chem, num_organs=3, seed=123)
        assert org1.num_compartments == org2.num_compartments
        assert org1.num_transport_links == org2.num_transport_links
        # Check transport links are identical
        for l1, l2 in zip(org1.transport_links, org2.transport_links):
            assert l1.source == l2.source
            assert l1.target == l2.target
            assert l1.molecule_id == l2.molecule_id

    def test_different_seeds_may_differ(self):
        """Different seeds may produce different transport molecule choices."""
        chem = _make_chemistry()
        org1 = generate_organism(chem, num_organs=3, seed=1)
        org2 = generate_organism(chem, num_organs=3, seed=999)
        # Structure is same size but molecules may differ
        assert org1.num_compartments == org2.num_compartments

    def test_initial_concentrations_set(self):
        """Organs have non-negative initial concentrations."""
        chem = _make_chemistry()
        org = generate_organism(chem, num_organs=3, seed=42)
        num_molecules = len(chem.molecules)
        # Organs are compartments 1, 2, 3 (0 is body)
        for organ_id in range(1, 4):
            for mol_id in range(num_molecules):
                conc = org.state.get(organ_id, mol_id)
                assert conc >= 0.0

    def test_simulator_can_step(self):
        """The generated simulator can execute a step."""
        chem = _make_chemistry()
        org = generate_organism(chem, num_organs=3, seed=42)
        # Should not raise; step returns new state
        new_state = org.simulator.step(org.state)
        assert new_state is not org.state


# === M9.3: Cross-Compartment Simulation ===

class TestCrossCompartmentSimulation:

    def test_transport_moves_molecules(self):
        """Molecule injected in one compartment appears in adjacent after steps."""
        chem = _make_chemistry()
        org = generate_organism(chem, num_organs=2, seed=42, transport_rate=0.1)

        # Find what molecule is transported between organs 1 and 2
        link = org.transport_links[0]  # first link: organ_0 -> organ_1
        mol_id = link.molecule_id
        src = link.source
        tgt = link.target

        # Set high concentration in source, zero in target
        state = org.state
        state.set(src, mol_id, 100.0)
        state.set(tgt, mol_id, 0.0)

        # Run several steps (step returns new state)
        for _ in range(50):
            state = org.simulator.step(state)

        # Target should have gained some concentration
        tgt_conc = state.get(tgt, mol_id)
        assert tgt_conc > 0.0, "Transport should move molecules to target"

    def test_transport_conserves_mass_approximately(self):
        """Total mass is roughly conserved for transported molecule (no reactions)."""
        carbon = AtomImpl("C", name="Carbon", atomic_weight=12.0)
        x = MoleculeImpl("X", atoms={carbon: 1}, bdepth=0, dat=MockDat("mol/X"))
        # No reactions - pure transport test
        simple_chem = ChemistryImpl(
            "transport_test",
            atoms={"C": carbon},
            molecules={"X": x},
            reactions={},
            dat=MockDat("chem/transport"),
        )
        org = generate_organism(simple_chem, num_organs=2, seed=42, transport_rate=0.05)

        mol_id = 0
        state = org.state

        # Record total before
        total_before = sum(state.get(c, mol_id) for c in range(org.num_compartments))

        # Run steps (pure transport, no reactions)
        for _ in range(100):
            state = org.simulator.step(state)

        total_after = sum(state.get(c, mol_id) for c in range(org.num_compartments))
        assert total_after == pytest.approx(total_before, rel=0.01)

    def test_transport_equilibrates(self):
        """Bidirectional transport should equilibrate concentrations."""
        carbon = AtomImpl("C", name="Carbon", atomic_weight=12.0)
        x = MoleculeImpl("X", atoms={carbon: 1}, bdepth=0, dat=MockDat("mol/X"))
        simple_chem = ChemistryImpl(
            "eq_test",
            atoms={"C": carbon},
            molecules={"X": x},
            reactions={},
            dat=MockDat("chem/eq"),
        )
        org = generate_organism(simple_chem, num_organs=2, seed=42, transport_rate=0.05)

        mol_id = 0
        state = org.state
        # Set asymmetric initial conditions
        state.set(1, mol_id, 100.0)  # organ_0
        state.set(2, mol_id, 0.0)    # organ_1

        # Run many steps (step returns new state)
        for _ in range(500):
            state = org.simulator.step(state)

        conc_0 = state.get(1, mol_id)
        conc_1 = state.get(2, mol_id)
        # Should be approximately equal after equilibration
        assert conc_0 == pytest.approx(conc_1, rel=0.1)

    def test_multi_organ_transport_chain(self):
        """Molecule injected in organ_0 eventually reaches organ_2 through organ_1."""
        chem = _make_chemistry()
        org = generate_organism(chem, num_organs=3, seed=42, transport_rate=0.05)

        # Find transport chain: organ_0 -> organ_1 and organ_1 -> organ_2
        links_01 = [l for l in org.transport_links if l.source == 1 and l.target == 2]
        links_12 = [l for l in org.transport_links if l.source == 2 and l.target == 3]

        if links_01 and links_12:
            mol_01 = links_01[0].molecule_id
            mol_12 = links_12[0].molecule_id

            if mol_01 == mol_12:
                state = org.state
                state.set(1, mol_01, 100.0)
                state.set(2, mol_01, 0.0)
                state.set(3, mol_01, 0.0)

                for _ in range(200):
                    state = org.simulator.step(state)

                # Organ 2 (compartment 3) should have some concentration
                assert state.get(3, mol_01) > 0.0

    def test_reactions_in_compartments(self):
        """Reactions assigned to organs actually change concentrations."""
        chem = _make_chemistry()
        org = generate_organism(chem, num_organs=2, seed=42)

        # Record state before
        num_molecules = len(chem.molecules)
        state = org.state
        before = {}
        for c in range(org.num_compartments):
            for m in range(num_molecules):
                before[(c, m)] = state.get(c, m)

        # Run some steps (step returns new state)
        for _ in range(10):
            state = org.simulator.step(state)

        # Some concentration should have changed
        changed = False
        for c in range(org.num_compartments):
            for m in range(num_molecules):
                if state.get(c, m) != before[(c, m)]:
                    changed = True
                    break
        assert changed, "Reactions should change concentrations"
