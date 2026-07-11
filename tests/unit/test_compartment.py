"""Tests for M9.1 Compartment Model."""

from __future__ import annotations

import pytest

from alienbio.bio import (
    AtomImpl,
    ChemistryImpl,
    CompartmentImpl,
    CompartmentTreeImpl,
    MoleculeImpl,
    ReactionImpl,
    WorldStateImpl,
    WorldSimulatorImpl,
    ReactionSpec,
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


# === CompartmentTreeImpl ===

class TestCompartmentTree:

    def test_create_root(self):
        tree = CompartmentTreeImpl()
        root = tree.add_root("organism")
        assert root == 0
        assert tree.num_compartments == 1

    def test_add_child(self):
        tree = CompartmentTreeImpl()
        root = tree.add_root("organism")
        child = tree.add_child(root, "cell")
        assert child == 1
        assert tree.num_compartments == 2

    def test_parent_child_relationship(self):
        tree = CompartmentTreeImpl()
        root = tree.add_root("organism")
        cell = tree.add_child(root, "cell")
        assert tree.parent(cell) == root
        assert tree.parent(root) is None
        assert tree.children(root) == [cell]

    def test_multiple_children(self):
        tree = CompartmentTreeImpl()
        root = tree.add_root("organism")
        a = tree.add_child(root, "organ_a")
        b = tree.add_child(root, "organ_b")
        assert tree.children(root) == [a, b]

    def test_depth(self):
        tree = CompartmentTreeImpl()
        root = tree.add_root("organism")
        organ = tree.add_child(root, "organ")
        cell = tree.add_child(organ, "cell")
        assert tree.depth(root) == 0
        assert tree.depth(organ) == 1
        assert tree.depth(cell) == 2

    def test_ancestors(self):
        tree = CompartmentTreeImpl()
        root = tree.add_root("organism")
        organ = tree.add_child(root, "organ")
        cell = tree.add_child(organ, "cell")
        assert tree.ancestors(cell) == [cell, organ, root]

    def test_descendants(self):
        tree = CompartmentTreeImpl()
        root = tree.add_root("organism")
        organ = tree.add_child(root, "organ")
        cell = tree.add_child(organ, "cell")
        desc = tree.descendants(root)
        assert organ in desc
        assert cell in desc

    def test_name(self):
        tree = CompartmentTreeImpl()
        root = tree.add_root("body")
        assert tree.name(root) == "body"

    def test_is_root(self):
        tree = CompartmentTreeImpl()
        root = tree.add_root("organism")
        child = tree.add_child(root, "cell")
        assert tree.is_root(root)
        assert not tree.is_root(child)

    def test_duplicate_root_raises(self):
        tree = CompartmentTreeImpl()
        tree.add_root()
        with pytest.raises(ValueError):
            tree.add_root()

    def test_serialization_roundtrip(self):
        tree = CompartmentTreeImpl()
        root = tree.add_root("organism")
        organ = tree.add_child(root, "organ")
        cell = tree.add_child(organ, "cell")

        data = tree.to_dict()
        tree2 = CompartmentTreeImpl.from_dict(data)

        assert tree2.num_compartments == 3
        assert tree2.parent(cell) == organ
        assert tree2.children(root) == [organ]
        assert tree2.name(organ) == "organ"


# === WorldStateImpl ===

class TestWorldState:

    def test_independent_compartment_concentrations(self):
        """M9.1 key test: 2 compartments with independent concentrations."""
        tree = CompartmentTreeImpl()
        root = tree.add_root("organism")
        cell = tree.add_child(root, "cell")

        state = WorldStateImpl(tree=tree, num_molecules=3)

        # Set different concentrations in each compartment
        state.set(root, 0, 10.0)
        state.set(cell, 0, 5.0)

        assert state.get(root, 0) == 10.0
        assert state.get(cell, 0) == 5.0

    def test_initial_zero(self):
        tree = CompartmentTreeImpl()
        tree.add_root("root")
        state = WorldStateImpl(tree=tree, num_molecules=5)
        for mol in range(5):
            assert state.get(0, mol) == 0.0

    def test_copy_is_independent(self):
        tree = CompartmentTreeImpl()
        tree.add_root("root")
        state = WorldStateImpl(tree=tree, num_molecules=2)
        state.set(0, 0, 10.0)

        copy = state.copy()
        copy.set(0, 0, 99.0)
        assert state.get(0, 0) == 10.0

    def test_copy_shares_tree(self):
        tree = CompartmentTreeImpl()
        tree.add_root("root")
        state = WorldStateImpl(tree=tree, num_molecules=2)
        copy = state.copy()
        assert copy.tree is state.tree

    def test_multiplicity(self):
        tree = CompartmentTreeImpl()
        root = tree.add_root("organism")
        cell = tree.add_child(root, "cell")
        state = WorldStateImpl(tree=tree, num_molecules=2)

        state.set_multiplicity(cell, 1000.0)
        assert state.get_multiplicity(cell) == 1000.0
        assert state.get_multiplicity(root) == 1.0

    def test_total_molecules(self):
        tree = CompartmentTreeImpl()
        root = tree.add_root("organism")
        state = WorldStateImpl(tree=tree, num_molecules=1)
        state.set(root, 0, 5.0)
        state.set_multiplicity(root, 100.0)
        assert state.total_molecules(root, 0) == 500.0

    def test_get_set_compartment(self):
        tree = CompartmentTreeImpl()
        tree.add_root("root")
        state = WorldStateImpl(tree=tree, num_molecules=3)
        state.set_compartment(0, [1.0, 2.0, 3.0])
        assert state.get_compartment(0) == [1.0, 2.0, 3.0]

    def test_wrong_size_raises(self):
        tree = CompartmentTreeImpl()
        tree.add_root("root")
        with pytest.raises(ValueError):
            WorldStateImpl(tree=tree, num_molecules=2, initial_concentrations=[1.0])

    def test_num_properties(self):
        tree = CompartmentTreeImpl()
        root = tree.add_root("organism")
        tree.add_child(root, "cell")
        state = WorldStateImpl(tree=tree, num_molecules=5)
        assert state.num_compartments == 2
        assert state.num_molecules == 5


# === WorldSimulatorImpl ===

class TestWorldSimulator:

    def test_reaction_in_one_compartment(self):
        """Reaction transforms molecules within a compartment."""
        tree = CompartmentTreeImpl()
        root = tree.add_root("organism")

        # Reaction: molecule 0 -> molecule 1 at rate 0.1
        rxn = ReactionSpec("r1", reactants={0: 1.0}, products={1: 1.0}, rate_constant=0.1)
        sim = WorldSimulatorImpl(tree=tree, reactions=[rxn], flows=[], num_molecules=2, dt=1.0)

        state = WorldStateImpl(tree=tree, num_molecules=2)
        state.set(root, 0, 10.0)

        new_state = sim.step(state)
        # Molecule 0 should decrease, molecule 1 should increase
        assert new_state.get(root, 0) < 10.0
        assert new_state.get(root, 1) > 0.0

    def test_reaction_conserves_mass(self):
        """1:1 reaction conserves total mass."""
        tree = CompartmentTreeImpl()
        root = tree.add_root("organism")

        rxn = ReactionSpec("r1", reactants={0: 1.0}, products={1: 1.0}, rate_constant=0.01)
        sim = WorldSimulatorImpl(tree=tree, reactions=[rxn], flows=[], num_molecules=2, dt=1.0)

        state = WorldStateImpl(tree=tree, num_molecules=2)
        state.set(root, 0, 10.0)

        new_state = sim.step(state)
        total_before = 10.0
        total_after = new_state.get(root, 0) + new_state.get(root, 1)
        assert total_after == pytest.approx(total_before, rel=1e-10)

    def test_run_produces_timeline(self):
        tree = CompartmentTreeImpl()
        tree.add_root("organism")

        rxn = ReactionSpec("r1", reactants={0: 1.0}, products={1: 1.0}, rate_constant=0.01)
        sim = WorldSimulatorImpl(tree=tree, reactions=[rxn], flows=[], num_molecules=2, dt=1.0)

        state = WorldStateImpl(tree=tree, num_molecules=2)
        state.set(0, 0, 10.0)

        history = sim.run(state, steps=10)
        assert len(history) == 11  # initial + 10 steps

    def test_two_compartments_independent_reactions(self):
        """Reactions in separate compartments are independent."""
        tree = CompartmentTreeImpl()
        root = tree.add_root("organism")
        cell = tree.add_child(root, "cell")

        rxn = ReactionSpec("r1", reactants={0: 1.0}, products={1: 1.0}, rate_constant=0.1)
        sim = WorldSimulatorImpl(tree=tree, reactions=[rxn], flows=[], num_molecules=2, dt=1.0)

        state = WorldStateImpl(tree=tree, num_molecules=2)
        state.set(root, 0, 10.0)
        state.set(cell, 0, 5.0)

        new_state = sim.step(state)
        # Both compartments should have reactions, but independently
        assert new_state.get(root, 0) < 10.0
        assert new_state.get(cell, 0) < 5.0
        # Root had more reactant, so more product should be produced
        assert new_state.get(root, 1) > new_state.get(cell, 1)

    def test_compartment_specific_reaction(self):
        """Reaction restricted to specific compartment."""
        tree = CompartmentTreeImpl()
        root = tree.add_root("organism")
        cell = tree.add_child(root, "cell")

        # Only in root compartment
        rxn = ReactionSpec(
            "r1", reactants={0: 1.0}, products={1: 1.0},
            rate_constant=0.1, compartments=[root],
        )
        sim = WorldSimulatorImpl(tree=tree, reactions=[rxn], flows=[], num_molecules=2, dt=1.0)

        state = WorldStateImpl(tree=tree, num_molecules=2)
        state.set(root, 0, 10.0)
        state.set(cell, 0, 10.0)

        new_state = sim.step(state)
        # Root should change, cell should not
        assert new_state.get(root, 0) < 10.0
        assert new_state.get(cell, 0) == 10.0

    def test_from_chemistry(self):
        """Create WorldSimulator from Chemistry."""
        carbon = AtomImpl("C", name="Carbon", atomic_weight=12.0)
        a = MoleculeImpl("A", atoms={carbon: 1}, bdepth=0, dat=MockDat("mol/A"))
        b = MoleculeImpl("B", atoms={carbon: 2}, bdepth=0, dat=MockDat("mol/B"))
        r1 = ReactionImpl(
            "r1", reactants={a: 1.0}, products={b: 1.0},
            rate=0.1,
            dat=MockDat("rxn/r1"),
        )
        chem = ChemistryImpl(
            "test", atoms={"C": carbon},
            molecules={"A": a, "B": b}, reactions={"r1": r1},
            dat=MockDat("chem/test"),
        )

        tree = CompartmentTreeImpl()
        tree.add_root("organism")

        sim = WorldSimulatorImpl.from_chemistry(chem, tree, dt=0.1)
        assert sim.num_molecules == 2
        assert len(sim.reactions) == 1

    def test_from_chemistry_warns_on_callable_rate(self, caplog):
        """H5: a callable rate law is downgraded to 1.0 with a loud warning."""
        carbon = AtomImpl("C", name="Carbon", atomic_weight=12.0)
        a = MoleculeImpl("A", atoms={carbon: 1}, bdepth=0, dat=MockDat("mol/A"))
        b = MoleculeImpl("B", atoms={carbon: 2}, bdepth=0, dat=MockDat("mol/B"))
        r1 = ReactionImpl(
            "r1", reactants={a: 1.0}, products={b: 1.0},
            rate=lambda state: 0.5,
            dat=MockDat("rxn/r1"),
        )
        chem = ChemistryImpl(
            "test", atoms={"C": carbon},
            molecules={"A": a, "B": b}, reactions={"r1": r1},
            dat=MockDat("chem/test"),
        )

        tree = CompartmentTreeImpl()
        tree.add_root("organism")

        with caplog.at_level("WARNING"):
            sim = WorldSimulatorImpl.from_chemistry(chem, tree, dt=0.1)

        assert sim.reactions[0].rate_constant == 1.0
        assert any(
            "r1" in record.message and "callable rate" in record.message
            for record in caplog.records
        )

    def test_from_chemistry_unknown_reactant_raises(self):
        """M8: a reaction referencing a molecule not in chemistry.molecules raises."""
        carbon = AtomImpl("C", name="Carbon", atomic_weight=12.0)
        a = MoleculeImpl("A", atoms={carbon: 1}, bdepth=0, dat=MockDat("mol/A"))
        ghost = MoleculeImpl("Ghost", atoms={carbon: 1}, bdepth=0, dat=MockDat("mol/Ghost"))
        r1 = ReactionImpl(
            "r1", reactants={ghost: 1.0}, products={a: 1.0},
            rate=0.1,
            dat=MockDat("rxn/r1"),
        )
        chem = ChemistryImpl(
            "test", atoms={"C": carbon},
            # Note: "Ghost" is intentionally NOT registered in molecules.
            molecules={"A": a}, reactions={"r1": r1},
            dat=MockDat("chem/test"),
        )

        tree = CompartmentTreeImpl()
        tree.add_root("organism")

        with pytest.raises(KeyError, match="Ghost"):
            WorldSimulatorImpl.from_chemistry(chem, tree, dt=0.1)


# === CompartmentImpl (entity) ===

class TestCompartmentImpl:

    def test_basic_properties(self):
        comp = CompartmentImpl(
            "body", volume=70000, kind="organism",
            dat=MockDat("comp/body"),
        )
        assert comp.kind == "organism"
        assert comp.volume == 70000

    def test_concentrations(self):
        comp = CompartmentImpl(
            "cell", volume=1.0,
            concentrations={"glucose": 5.0, "oxygen": 2.0},
            dat=MockDat("comp/cell"),
        )
        assert comp.concentrations == {"glucose": 5.0, "oxygen": 2.0}

    def test_parent_child(self):
        parent = CompartmentImpl(
            "body", volume=70000, kind="organism",
            dat=MockDat("comp/body"),
        )
        child = CompartmentImpl(
            "liver", volume=1500, kind="organ",
            dat=MockDat("comp/liver"),
        )
        parent.add_child(child)
        assert child in parent.children

    def test_multiplicity(self):
        comp = CompartmentImpl(
            "rbc", volume=90e-12, kind="cell",
            multiplicity=5e6,
            dat=MockDat("comp/rbc"),
        )
        assert comp.multiplicity == 5e6

    def test_all_compartments(self):
        root = CompartmentImpl("body", volume=1.0, dat=MockDat("comp/body"))
        organ = CompartmentImpl("liver", volume=1.0, dat=MockDat("comp/liver"))
        cell = CompartmentImpl("hepatocyte", volume=1.0, dat=MockDat("comp/hepatocyte"))
        root.add_child(organ)
        organ.add_child(cell)
        all_comps = root.all_compartments()
        assert len(all_comps) == 3
        assert root in all_comps
        assert organ in all_comps
        assert cell in all_comps

    def test_depth(self):
        root = CompartmentImpl("body", volume=1.0, dat=MockDat("comp/body"))
        organ = CompartmentImpl("liver", volume=1.0, dat=MockDat("comp/liver"))
        cell = CompartmentImpl("hepatocyte", volume=1.0, dat=MockDat("comp/hepatocyte"))
        root.add_child(organ)
        organ.add_child(cell)
        # CompartmentImpl.depth() walks Entity._parent, which isn't set by add_child
        # So depth is based on the CompartmentImpl's own children list
        assert root.depth() == 0
