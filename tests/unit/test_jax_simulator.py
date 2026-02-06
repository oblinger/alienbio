"""Tests for M13 JAX Simulator."""

from __future__ import annotations

import pytest

try:
    import jax
    HAS_JAX = True
except ImportError:
    HAS_JAX = False

from alienbio.bio import (
    CompartmentTreeImpl,
    ReactionSpec,
    WorldStateImpl,
    WorldSimulatorImpl,
)

pytestmark = pytest.mark.skipif(not HAS_JAX, reason="JAX not installed")


def _make_tree_and_state():
    """Simple tree with one compartment, 2 molecules."""
    tree = CompartmentTreeImpl()
    tree.add_root("organism")
    state = WorldStateImpl(tree=tree, num_molecules=2)
    state.set(0, 0, 10.0)  # molecule 0 = 10.0
    state.set(0, 1, 0.0)   # molecule 1 = 0.0
    return tree, state


class TestJaxCore:

    def test_import(self):
        """M13.1: JaxWorldSimulator can be imported."""
        from alienbio.bio.jax_simulator import JaxWorldSimulator
        assert JaxWorldSimulator is not None

    def test_step(self):
        """M13.1 key test: step() produces valid output."""
        from alienbio.bio.jax_simulator import JaxWorldSimulator

        tree, state = _make_tree_and_state()
        rxn = ReactionSpec("r1", {0: 1.0}, {1: 1.0}, rate_constant=0.1)
        sim = JaxWorldSimulator(tree, [rxn], num_molecules=2, dt=1.0)

        new_state = sim.step(state)
        assert new_state.get(0, 0) < 10.0
        assert new_state.get(0, 1) > 0.0

    def test_run(self):
        """M13.1 key test: run() produces timeline."""
        from alienbio.bio.jax_simulator import JaxWorldSimulator

        tree, state = _make_tree_and_state()
        rxn = ReactionSpec("r1", {0: 1.0}, {1: 1.0}, rate_constant=0.01)
        sim = JaxWorldSimulator(tree, [rxn], num_molecules=2, dt=1.0)

        history = sim.run(state, steps=10)
        assert len(history) == 11

    def test_mass_conservation(self):
        """1:1 reaction conserves mass."""
        from alienbio.bio.jax_simulator import JaxWorldSimulator

        tree, state = _make_tree_and_state()
        rxn = ReactionSpec("r1", {0: 1.0}, {1: 1.0}, rate_constant=0.01)
        sim = JaxWorldSimulator(tree, [rxn], num_molecules=2, dt=1.0)

        new_state = sim.step(state)
        total = new_state.get(0, 0) + new_state.get(0, 1)
        assert total == pytest.approx(10.0, rel=1e-5)


class TestJaxVerification:

    def test_matches_python_simulator(self):
        """M13.3 key test: JAX and Python outputs match within tolerance."""
        from alienbio.bio.jax_simulator import JaxWorldSimulator

        tree, state = _make_tree_and_state()
        rxn = ReactionSpec("r1", {0: 1.0}, {1: 1.0}, rate_constant=0.01)

        py_sim = WorldSimulatorImpl(tree, [rxn], [], num_molecules=2, dt=1.0)
        jax_sim = JaxWorldSimulator(tree, [rxn], num_molecules=2, dt=1.0)

        py_history = py_sim.run(state, steps=100)
        jax_history = jax_sim.run(state, steps=100)

        # Compare final states
        for mol in range(2):
            py_val = py_history[-1].get(0, mol)
            jax_val = jax_history[-1].get(0, mol)
            assert abs(py_val - jax_val) < 1e-4, (
                f"mol {mol}: python={py_val}, jax={jax_val}"
            )

    def test_two_compartments_match(self):
        """Multi-compartment simulation matches Python."""
        from alienbio.bio.jax_simulator import JaxWorldSimulator

        tree = CompartmentTreeImpl()
        root = tree.add_root("organism")
        tree.add_child(root, "cell")

        state = WorldStateImpl(tree=tree, num_molecules=2)
        state.set(0, 0, 10.0)
        state.set(1, 0, 5.0)

        rxn = ReactionSpec("r1", {0: 1.0}, {1: 1.0}, rate_constant=0.01)

        py_sim = WorldSimulatorImpl(tree, [rxn], [], num_molecules=2, dt=1.0)
        jax_sim = JaxWorldSimulator(tree, [rxn], num_molecules=2, dt=1.0)

        py_final = py_sim.run(state, steps=50)[-1]
        jax_final = jax_sim.run(state, steps=50)[-1]

        for c in range(2):
            for m in range(2):
                assert abs(py_final.get(c, m) - jax_final.get(c, m)) < 1e-4


class TestNoJaxFallback:

    @pytest.mark.skipif(HAS_JAX, reason="Only test fallback when JAX missing")
    def test_import_error_without_jax(self):
        from alienbio.bio.jax_simulator import JaxWorldSimulator

        tree = CompartmentTreeImpl()
        tree.add_root("root")
        with pytest.raises(ImportError):
            JaxWorldSimulator(tree, [], num_molecules=2)
