"""Tests for F015 S2: bidirectional rate modulation (activators/inhibitors).

A reaction can carry modifier species that scale its rate WITHOUT being consumed or
produced (they never enter ``reactants``/``products``). The factor is a pure function
of the frozen start-of-step state: an ``"activator"`` (param ``a``) speeds the reaction
up, an ``"inhibitor"`` (param ``Ki``) slows it down — bidirectional, since mass-action
alone can only ever increase with more reactant. A bare ``str`` modifier role (the
pre-F015 form) coerces to a label-only, rate-inert ``Modulation`` (factor 1.0), so every
existing call site keeps working unchanged.
"""

from __future__ import annotations

from typing import cast

import pytest

from alienbio.bio import AtomImpl, ChemistryImpl, MoleculeImpl, Modulation, ReactionImpl
from alienbio.bio import makers as _makers  # noqa: F401  (registers mk.M/mk.R/mk.C)
from alienbio.bio.compartment_tree import CompartmentTreeImpl
from alienbio.bio.conservation import check_conservation, molecule_quantity, total_quantity
from alienbio.bio.world_simulator import ReactionSpec, WorldSimulatorImpl
from alienbio.bio.world_state import WorldStateImpl
from alienbio.infra.mk import mk


class MockDat:
    def __init__(self, path: str):
        self._path = path

    def get_path_name(self) -> str:
        return self._path

    def get_path(self) -> str:
        return f"/tmp/{self._path}"

    def save(self) -> None:
        pass


def _one_compartment() -> tuple[CompartmentTreeImpl, int]:
    tree = CompartmentTreeImpl()
    root = tree.add_root("organism")
    return tree, root


class TestModulationBidirectional:
    """An activator speeds a reaction up; an inhibitor slows it down."""

    def test_activator_speeds_reaction_up(self):
        tree, root = _one_compartment()
        base = ReactionSpec("r1", reactants={0: 1.0}, products={1: 1.0}, rate_constant=0.1)
        activated = ReactionSpec(
            "r1", reactants={0: 1.0}, products={1: 1.0}, rate_constant=0.1,
            modulators={2: Modulation(kind="activator", a=1.0)},
        )
        state = WorldStateImpl(tree=tree, num_molecules=3)
        state.set(root, 0, 10.0)
        state.set(root, 2, 5.0)  # activator concentration

        sim_base = WorldSimulatorImpl(tree=tree, reactions=[base], flows=[], num_molecules=3, dt=1.0)
        sim_act = WorldSimulatorImpl(tree=tree, reactions=[activated], flows=[], num_molecules=3, dt=1.0)

        after_base = sim_base.step(state)
        after_act = sim_act.step(state)
        assert after_act.get(root, 1) > after_base.get(root, 1)
        # factor = (1 + 1.0 * 5.0) = 6.0 -> extent = 0.1 * 10.0 * 6.0 * 1.0 = 6.0
        assert after_act.get(root, 1) == pytest.approx(6.0)

    def test_inhibitor_slows_reaction_down_monotonically(self):
        """Bidirectionality: increasing [inhibitor] strictly decreases the extent."""
        tree, root = _one_compartment()

        def extent_at(conc_i: float) -> float:
            rxn = ReactionSpec(
                "r1", reactants={0: 1.0}, products={1: 1.0}, rate_constant=0.1,
                modulators={2: Modulation(kind="inhibitor", Ki=2.0)},
            )
            sim = WorldSimulatorImpl(tree=tree, reactions=[rxn], flows=[], num_molecules=3, dt=1.0)
            state = WorldStateImpl(tree=tree, num_molecules=3)
            state.set(root, 0, 10.0)
            state.set(root, 2, conc_i)
            return sim.step(state).get(root, 1)

        e0 = extent_at(0.0)
        e1 = extent_at(1.0)
        e2 = extent_at(5.0)
        assert e0 > e1 > e2
        # factor = 1 / (1 + 0/2) = 1.0 -> extent = 1.0
        assert e0 == pytest.approx(1.0)
        # factor = 1 / (1 + 1/2) -> extent = 0.1*10*1.0/1.5 = 0.6666...
        assert e1 == pytest.approx(0.1 * 10.0 / 1.5)


class TestModulationFastPath:
    """A reaction with no modulators is byte-identical to before F015."""

    def test_no_modulators_matches_plain_mass_action(self):
        tree, root = _one_compartment()
        no_mod = ReactionSpec("r1", reactants={0: 1.0}, products={1: 1.0}, rate_constant=0.1)
        empty_mod = ReactionSpec(
            "r1", reactants={0: 1.0}, products={1: 1.0}, rate_constant=0.1, modulators={},
        )
        state = WorldStateImpl(tree=tree, num_molecules=2)
        state.set(root, 0, 10.0)

        sim_no_mod = WorldSimulatorImpl(tree=tree, reactions=[no_mod], flows=[], num_molecules=2, dt=1.0)
        sim_empty_mod = WorldSimulatorImpl(tree=tree, reactions=[empty_mod], flows=[], num_molecules=2, dt=1.0)

        result_no_mod = sim_no_mod.step(state)
        result_empty_mod = sim_empty_mod.step(state)
        # exactly the pre-F015 mass-action extent: 0.1 * 10.0 * dt(1.0) = 1.0
        assert result_no_mod.get(root, 1) == 1.0
        assert result_empty_mod.get(root, 1) == result_no_mod.get(root, 1)


class TestModulationConservation:
    """F012 regression: modifiers stay out of the balance/mass-canary machinery."""

    def test_check_conservation_clean_with_activating_modifier(self):
        h_atom = AtomImpl("H", "Hydrogen", 1.0)
        o_atom = AtomImpl("O", "Oxygen", 16.0)
        h2 = cast(MoleculeImpl, mk.M("h2", atoms={h_atom: 2}))
        o2 = cast(MoleculeImpl, mk.M("o2", atoms={o_atom: 2}))
        water = cast(MoleculeImpl, mk.M("water", atoms={h_atom: 2, o_atom: 1}))
        enzyme = cast(MoleculeImpl, mk.M("enzyme"))  # atom-free catalyst

        rxn = cast(
            ReactionImpl,
            mk.R(
                "cat", reactants={h2: 2, o2: 1}, products={water: 2},
                modifiers={enzyme: Modulation(kind="activator", a=0.5)}, rate=0.01,
            ),
        )
        chem = cast(ChemistryImpl, mk.C("chem", [h2, o2, water, enzyme], [rxn]))
        assert check_conservation(chem) == []

    def test_total_quantity_canary_invariant_with_catalyst(self):
        """The catalyst is never consumed/produced; the mass canary stays invariant."""
        carbon = AtomImpl("C", name="Carbon", atomic_weight=12.0)
        a = MoleculeImpl("A", atoms={carbon: 1}, bdepth=0, dat=MockDat("mol/A"))
        b = MoleculeImpl("B", atoms={carbon: 1}, bdepth=0, dat=MockDat("mol/B"))
        enzyme = MoleculeImpl("E", atoms={}, bdepth=0, dat=MockDat("mol/E"))

        rxn = ReactionImpl(
            "r1", reactants={a: 1.0}, products={b: 1.0},
            modifiers={enzyme: Modulation(kind="activator", a=0.3)},
            rate=0.05, dat=MockDat("rxn/r1"),
        )
        chem = ChemistryImpl(
            "test", atoms={"C": carbon},
            molecules={"A": a, "B": b, "E": enzyme}, reactions={"r1": rxn},
            dat=MockDat("chem/test"),
        )

        tree, root = _one_compartment()
        sim = WorldSimulatorImpl.from_chemistry(chem, tree, dt=1.0)

        mol_names = list(chem.molecules.keys())
        idx = {name: i for i, name in enumerate(mol_names)}
        state = WorldStateImpl(tree=tree, num_molecules=sim.num_molecules)
        state.set(root, idx["A"], 10.0)
        state.set(root, idx["E"], 4.0)  # catalyst present, never consumed

        per_index = [molecule_quantity(chem.molecules[name]) for name in mol_names]
        total0 = total_quantity(state, per_index)

        current = state
        for _ in range(5):
            current = sim.step(current)
            assert total_quantity(current, per_index) == pytest.approx(total0, rel=1e-9)

        # the catalyst's own concentration never moves
        assert current.get(root, idx["E"]) == pytest.approx(4.0)


class TestModulationDeterminismOrderIndependence:
    """Pure function of the frozen state: deterministic and order-independent (H4)."""

    def test_repeated_step_from_same_state_is_deterministic(self):
        tree, root = _one_compartment()
        rxn = ReactionSpec(
            "r1", reactants={0: 1.0}, products={1: 1.0}, rate_constant=0.1,
            modulators={2: Modulation(kind="activator", a=0.3)},
        )
        sim = WorldSimulatorImpl(tree=tree, reactions=[rxn], flows=[], num_molecules=3, dt=1.0)
        state = WorldStateImpl(tree=tree, num_molecules=3)
        state.set(root, 0, 10.0)
        state.set(root, 2, 4.0)

        result1 = sim.step(state)
        result2 = sim.step(state)
        assert result1.get(root, 1) == result2.get(root, 1)

    def test_order_independent_among_competing_modulated_reactions(self):
        """Permuting the reaction list changes nothing, even with modulators active (H4)."""
        tree, root = _one_compartment()
        rxn_a = ReactionSpec(
            "a", reactants={0: 1.0}, products={1: 1.0}, rate_constant=0.5,
            modulators={3: Modulation(kind="activator", a=1.0)},
        )
        rxn_b = ReactionSpec(
            "b", reactants={0: 1.0}, products={2: 1.0}, rate_constant=0.5,
            modulators={3: Modulation(kind="inhibitor", Ki=2.0)},
        )
        state = WorldStateImpl(tree=tree, num_molecules=4)
        state.set(root, 0, 1.0)  # scarce reactant -> forces rationing/competition
        state.set(root, 3, 2.0)

        sim_ab = WorldSimulatorImpl(tree=tree, reactions=[rxn_a, rxn_b], flows=[], num_molecules=4, dt=1.0)
        sim_ba = WorldSimulatorImpl(tree=tree, reactions=[rxn_b, rxn_a], flows=[], num_molecules=4, dt=1.0)

        result_ab = sim_ab.step(state)
        result_ba = sim_ba.step(state)
        for mol_id in (0, 1, 2):
            assert result_ab.get(root, mol_id) == pytest.approx(result_ba.get(root, mol_id))


class TestBareStringModifierBackwardCompat:
    """Every existing call site passes a bare str role; it must keep working, inertly."""

    def test_bare_str_modifier_constructs_and_reads_back_unchanged(self):
        carbon = AtomImpl("C", name="Carbon", atomic_weight=12.0)
        a = MoleculeImpl("A", atoms={carbon: 1}, bdepth=0, dat=MockDat("mol/A"))
        b = MoleculeImpl("B", atoms={carbon: 1}, bdepth=0, dat=MockDat("mol/B"))
        e = MoleculeImpl("E", atoms={carbon: 1}, bdepth=0, dat=MockDat("mol/E"))

        rxn = ReactionImpl(
            "r1", reactants={a: 1.0}, products={b: 1.0},
            modifiers={e: "catalyst"}, rate=0.1, dat=MockDat("rxn/r1"),
        )
        # unchanged property access — no coercion at storage/read time
        assert rxn.modifiers[e] == "catalyst"

    def test_bare_str_modifier_is_inert_in_the_simulator(self):
        carbon = AtomImpl("C", name="Carbon", atomic_weight=12.0)
        a = MoleculeImpl("A", atoms={carbon: 1}, bdepth=0, dat=MockDat("mol/A"))
        b = MoleculeImpl("B", atoms={carbon: 1}, bdepth=0, dat=MockDat("mol/B"))
        e = MoleculeImpl("E", atoms={carbon: 1}, bdepth=0, dat=MockDat("mol/E"))

        rxn = ReactionImpl(
            "r1", reactants={a: 1.0}, products={b: 1.0},
            modifiers={e: "catalyst"}, rate=0.1, dat=MockDat("rxn/r1"),
        )
        chem = ChemistryImpl(
            "test", atoms={"C": carbon},
            molecules={"A": a, "B": b, "E": e}, reactions={"r1": rxn},
            dat=MockDat("chem/test"),
        )
        tree, root = _one_compartment()
        sim = WorldSimulatorImpl.from_chemistry(chem, tree, dt=1.0)

        spec = sim.reactions[0]
        mol_names = list(chem.molecules.keys())
        idx = {name: i for i, name in enumerate(mol_names)}
        assert spec.modulators[idx["E"]] == Modulation(kind="catalyst")

        state = WorldStateImpl(tree=tree, num_molecules=sim.num_molecules)
        state.set(root, idx["A"], 10.0)
        state.set(root, idx["E"], 999.0)  # a huge "catalyst" concentration must not matter

        after = sim.step(state)
        # exactly the plain mass-action extent: 0.1 * 10.0 * dt(1.0) = 1.0
        assert after.get(root, idx["B"]) == pytest.approx(1.0)
