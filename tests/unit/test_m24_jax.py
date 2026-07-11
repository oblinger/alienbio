"""M24 JAX vectorization + Task A correctness tests.

Covers:
  A1  C1 mass-creation fix (WorldSimulatorImpl + JaxWorldSimulator)
  A2  F8 flows applied in JAX (parity with a GeneralFlow reference)
  A3  F9 float64 default dtype (parity), float32 opt-in
  M24.1/2  vectorized multi-reaction / multi-compartment parity
  M24.3     GPU-resident run_fast (fori_loop + jit) parity
  M24.4     run_batch vmap parity
  M24.5     native flows compiled into the jitted path
"""

from __future__ import annotations

import pytest

try:
    import jax  # noqa: F401

    HAS_JAX = True
except ImportError:
    HAS_JAX = False

from alienbio.bio import (
    CompartmentTreeImpl,
    ReactionSpec,
    WorldStateImpl,
    WorldSimulatorImpl,
)
from alienbio.bio.flow import GeneralFlow

pytestmark = pytest.mark.skipif(not HAS_JAX, reason="JAX not installed")


def _single_root(num_molecules=2):
    tree = CompartmentTreeImpl()
    tree.add_root("organism")
    return tree, WorldStateImpl(tree=tree, num_molecules=num_molecules)


# ── A1: C1 mass-creation fix ───────────────────────────────────────────────────


class TestC1MassConservation:
    """A reactant that depletes must NOT manufacture product mass."""

    def test_reference_no_mass_creation_on_depletion(self):
        tree, state = _single_root()
        state.set(0, 0, 1.0)  # tiny substrate
        state.set(0, 1, 0.0)
        # rate_constant huge so naive rate would consume >> available in 1 step
        rxn = ReactionSpec("r1", {0: 1.0}, {1: 1.0}, rate_constant=100.0)
        sim = WorldSimulatorImpl(tree, [rxn], [], num_molecules=2, dt=1.0)

        prev_total = 1.0
        cur = state
        for _ in range(20):
            cur = sim.step(cur)
            total = cur.get(0, 0) + cur.get(0, 1)
            assert cur.get(0, 0) >= -1e-12, "reactant went negative"
            assert total <= prev_total + 1e-9, (
                f"mass created: {total} > {prev_total}"
            )
            prev_total = total
        # All converted, nothing manufactured.
        assert cur.get(0, 1) == pytest.approx(1.0, abs=1e-9)

    def test_jax_no_mass_creation_on_depletion(self):
        from alienbio.bio.jax_simulator import JaxWorldSimulator

        tree, state = _single_root()
        state.set(0, 0, 1.0)
        state.set(0, 1, 0.0)
        rxn = ReactionSpec("r1", {0: 1.0}, {1: 1.0}, rate_constant=100.0)
        sim = JaxWorldSimulator(tree, [rxn], num_molecules=2, dt=1.0)

        prev_total = 1.0
        cur = state
        for _ in range(20):
            cur = sim.step(cur)
            total = cur.get(0, 0) + cur.get(0, 1)
            assert cur.get(0, 0) >= -1e-9
            assert total <= prev_total + 1e-6, (
                f"mass created: {total} > {prev_total}"
            )
            prev_total = total
        assert cur.get(0, 1) == pytest.approx(1.0, abs=1e-5)

    def test_jax_matches_reference_through_depletion(self):
        from alienbio.bio.jax_simulator import JaxWorldSimulator

        tree, state = _single_root()
        state.set(0, 0, 3.0)
        rxn = ReactionSpec("r1", {0: 1.0}, {1: 1.0}, rate_constant=2.0)
        py = WorldSimulatorImpl(tree, [rxn], [], num_molecules=2, dt=1.0)
        jx = JaxWorldSimulator(tree, [rxn], num_molecules=2, dt=1.0)

        pf = py.run(state, steps=30)[-1]
        jf = jx.run(state, steps=30)[-1]
        for m in range(2):
            assert abs(pf.get(0, m) - jf.get(0, m)) < 1e-6


# ── A3: dtype ──────────────────────────────────────────────────────────────────


class TestDtype:
    def test_default_is_float64(self):
        from alienbio.bio.jax_simulator import JaxWorldSimulator

        tree, _ = _single_root()
        sim = JaxWorldSimulator(tree, [], num_molecules=2)
        assert sim.dtype == "float64"

    def test_float64_tighter_parity_than_float32(self):
        from alienbio.bio.jax_simulator import JaxWorldSimulator

        tree, state = _single_root()
        state.set(0, 0, 10.0)
        rxn = ReactionSpec("r1", {0: 1.0}, {1: 1.0}, rate_constant=0.01)
        py = WorldSimulatorImpl(tree, [rxn], [], num_molecules=2, dt=1.0)
        j64 = JaxWorldSimulator(tree, [rxn], num_molecules=2, dt=1.0, dtype="float64")
        j32 = JaxWorldSimulator(tree, [rxn], num_molecules=2, dt=1.0, dtype="float32")

        pf = py.run(state, steps=200)[-1]
        d64 = abs(pf.get(0, 0) - j64.run(state, steps=200)[-1].get(0, 0))
        d32 = abs(pf.get(0, 0) - j32.run(state, steps=200)[-1].get(0, 0))
        assert d64 < 1e-6
        assert d64 <= d32 + 1e-12


# ── M24.1/2: vectorized multi-reaction, multi-compartment parity ───────────────


class TestVectorizedParity:
    def test_multi_reaction_multi_compartment(self):
        from alienbio.bio.jax_simulator import JaxWorldSimulator

        tree = CompartmentTreeImpl()
        root = tree.add_root("organism")
        a = tree.add_child(root, "a")
        tree.add_child(a, "b")  # 3 compartments

        # Chain: 0->1 (all comps), 1->2 (only root), 2->0 (comp a only)
        rxns = [
            ReactionSpec("r0", {0: 1.0}, {1: 1.0}, rate_constant=0.05),
            ReactionSpec("r1", {1: 1.0}, {2: 1.0}, rate_constant=0.03, compartments=[root]),
            ReactionSpec("r2", {2: 1.0}, {0: 1.0}, rate_constant=0.02, compartments=[a]),
        ]
        state = WorldStateImpl(tree=tree, num_molecules=3)
        state.set(root, 0, 8.0)
        state.set(a, 0, 4.0)
        state.set(2, 1, 2.0)

        py = WorldSimulatorImpl(tree, rxns, [], num_molecules=3, dt=1.0)
        jx = JaxWorldSimulator(tree, rxns, num_molecules=3, dt=1.0)

        pf = py.run(state, steps=60)[-1]
        jf = jx.run(state, steps=60)[-1]
        for c in range(3):
            for m in range(3):
                assert abs(pf.get(c, m) - jf.get(c, m)) < 1e-6, (c, m)

    def test_stoichiometry_two_to_one(self):
        from alienbio.bio.jax_simulator import JaxWorldSimulator

        tree, state = _single_root(num_molecules=2)
        state.set(0, 0, 10.0)
        rxn = ReactionSpec("r1", {0: 2.0}, {1: 1.0}, rate_constant=0.01)
        py = WorldSimulatorImpl(tree, [rxn], [], num_molecules=2, dt=1.0)
        jx = JaxWorldSimulator(tree, [rxn], num_molecules=2, dt=1.0)
        pf = py.run(state, steps=40)[-1]
        jf = jx.run(state, steps=40)[-1]
        for m in range(2):
            assert abs(pf.get(0, m) - jf.get(0, m)) < 1e-6


# ── A2 / M24.5: flows ──────────────────────────────────────────────────────────


def _make_transfer_general_flow(src, dst, mol, rate):
    """A GeneralFlow that moves dt*rate*S[src,mol] from src to dst."""

    def apply_fn(state, tree, dt):
        moved = dt * rate * state.get(src, mol)
        state.set(src, mol, state.get(src, mol) - moved)
        state.set(dst, mol, state.get(dst, mol) + moved)

    return GeneralFlow(origin=src, apply_fn=apply_fn, name=f"xfer_{src}_{dst}_{mol}")


class TestFlows:
    def test_jax_applies_python_flow_matches_reference(self):
        """A2: JAX must not drop flows -- host path matches WorldSimulatorImpl."""
        from alienbio.bio.jax_simulator import JaxWorldSimulator

        tree = CompartmentTreeImpl()
        root = tree.add_root("organism")
        tree.add_child(root, "cell")

        rxn = ReactionSpec("r1", {0: 1.0}, {1: 1.0}, rate_constant=0.02)
        flow = _make_transfer_general_flow(0, 1, 0, rate=0.1)

        state = WorldStateImpl(tree=tree, num_molecules=2)
        state.set(0, 0, 20.0)
        state.set(1, 0, 5.0)

        py = WorldSimulatorImpl(tree, [rxn], [flow], num_molecules=2, dt=1.0)
        jx = JaxWorldSimulator(tree, [rxn], num_molecules=2, dt=1.0, flows=[flow])

        pf = py.run(state, steps=40)[-1]
        jf = jx.run(state, steps=40)[-1]
        for c in range(2):
            for m in range(2):
                assert abs(pf.get(c, m) - jf.get(c, m)) < 1e-6, (c, m)

    def test_flowless_jax_drops_nothing_vs_flow_reference(self):
        """Guard: an empty-flow JAX sim must DIFFER from a with-flow reference
        (proves the flow actually moves mass; the old empty-list parity test
        masked F8)."""
        from alienbio.bio.jax_simulator import JaxWorldSimulator

        tree = CompartmentTreeImpl()
        root = tree.add_root("organism")
        tree.add_child(root, "cell")
        flow = _make_transfer_general_flow(0, 1, 0, rate=0.2)

        state = WorldStateImpl(tree=tree, num_molecules=2)
        state.set(0, 0, 20.0)

        py = WorldSimulatorImpl(tree, [], [flow], num_molecules=2, dt=1.0)
        jx_noflow = JaxWorldSimulator(tree, [], num_molecules=2, dt=1.0)

        pf = py.run(state, steps=10)[-1]
        jf = jx_noflow.run(state, steps=10)[-1]
        assert abs(pf.get(1, 0) - jf.get(1, 0)) > 1.0  # mass moved vs not

    def test_native_flow_matches_reference(self):
        """M24.5: native (compiled) flow matches an equivalent GeneralFlow."""
        from alienbio.bio.jax_simulator import JaxWorldSimulator

        tree = CompartmentTreeImpl()
        root = tree.add_root("organism")
        tree.add_child(root, "cell")

        rxn = ReactionSpec("r1", {0: 1.0}, {1: 1.0}, rate_constant=0.02)
        flow = _make_transfer_general_flow(0, 1, 0, rate=0.1)

        state = WorldStateImpl(tree=tree, num_molecules=2)
        state.set(0, 0, 20.0)
        state.set(1, 0, 5.0)

        py = WorldSimulatorImpl(tree, [rxn], [flow], num_molecules=2, dt=1.0)
        jx = JaxWorldSimulator(
            tree, [rxn], num_molecules=2, dt=1.0,
            native_flows=[(0, 1, 0, 0.1)],
        )

        pf = py.run(state, steps=40)[-1]
        # native flow rides the host run() path too (via _jit_step_fn)
        jf = jx.run(state, steps=40)[-1]
        for c in range(2):
            for m in range(2):
                assert abs(pf.get(c, m) - jf.get(c, m)) < 1e-6, (c, m)

    def test_run_fast_rejects_python_flows(self):
        from alienbio.bio.jax_simulator import JaxWorldSimulator

        tree, state = _single_root()
        state.set(0, 0, 10.0)
        flow = _make_transfer_general_flow(0, 0, 0, rate=0.0)
        jx = JaxWorldSimulator(tree, [], num_molecules=2, dt=1.0, flows=[flow])
        with pytest.raises(ValueError):
            jx.run_fast(state, 5)


# ── M24.3: GPU-resident run_fast ───────────────────────────────────────────────


class TestRunFast:
    def test_run_fast_matches_reference(self):
        from alienbio.bio.jax_simulator import JaxWorldSimulator

        tree = CompartmentTreeImpl()
        root = tree.add_root("organism")
        tree.add_child(root, "cell")
        rxns = [
            ReactionSpec("r0", {0: 1.0}, {1: 1.0}, rate_constant=0.03),
            ReactionSpec("r1", {1: 1.0}, {0: 1.0}, rate_constant=0.01),
        ]
        state = WorldStateImpl(tree=tree, num_molecules=2)
        state.set(0, 0, 10.0)
        state.set(1, 0, 7.0)

        py = WorldSimulatorImpl(tree, rxns, [], num_molecules=2, dt=1.0)
        jx = JaxWorldSimulator(tree, rxns, num_molecules=2, dt=1.0)

        pf = py.run(state, steps=200)[-1]
        jf = jx.run_fast(state, 200)
        for c in range(2):
            for m in range(2):
                assert abs(pf.get(c, m) - jf.get(c, m)) < 1e-5

    def test_run_fast_with_native_flow(self):
        from alienbio.bio.jax_simulator import JaxWorldSimulator

        tree = CompartmentTreeImpl()
        root = tree.add_root("organism")
        tree.add_child(root, "cell")
        rxn = ReactionSpec("r1", {0: 1.0}, {1: 1.0}, rate_constant=0.02)
        flow = _make_transfer_general_flow(0, 1, 0, rate=0.05)

        state = WorldStateImpl(tree=tree, num_molecules=2)
        state.set(0, 0, 15.0)

        py = WorldSimulatorImpl(tree, [rxn], [flow], num_molecules=2, dt=1.0)
        jx = JaxWorldSimulator(
            tree, [rxn], num_molecules=2, dt=1.0,
            native_flows=[(0, 1, 0, 0.05)],
        )
        pf = py.run(state, steps=100)[-1]
        jf = jx.run_fast(state, 100)
        for c in range(2):
            for m in range(2):
                assert abs(pf.get(c, m) - jf.get(c, m)) < 1e-5


# ── M24.4: run_batch vmap ──────────────────────────────────────────────────────


class TestRunBatch:
    def test_batch_matches_sequential(self):
        from alienbio.bio.jax_simulator import JaxWorldSimulator

        tree, _ = _single_root()
        rxn = ReactionSpec("r1", {0: 1.0}, {1: 1.0}, rate_constant=0.02)
        jx = JaxWorldSimulator(tree, [rxn], num_molecules=2, dt=1.0)

        states = []
        for init in (5.0, 10.0, 20.0, 50.0):
            s = WorldStateImpl(tree=tree, num_molecules=2)
            s.set(0, 0, init)
            states.append(s)

        batched = jx.run_batch(states, 100)
        assert len(batched) == 4
        for s, bf in zip(states, batched):
            single = jx.run_fast(s, 100)
            for m in range(2):
                assert abs(single.get(0, m) - bf.get(0, m)) < 1e-6

    def test_batch_matches_reference(self):
        from alienbio.bio.jax_simulator import JaxWorldSimulator

        tree, _ = _single_root()
        rxn = ReactionSpec("r1", {0: 1.0}, {1: 1.0}, rate_constant=0.05)
        py = WorldSimulatorImpl(tree, [rxn], [], num_molecules=2, dt=1.0)
        jx = JaxWorldSimulator(tree, [rxn], num_molecules=2, dt=1.0)

        states = []
        for init in (3.0, 30.0):
            s = WorldStateImpl(tree=tree, num_molecules=2)
            s.set(0, 0, init)
            states.append(s)

        batched = jx.run_batch(states, 80)
        for s, bf in zip(states, batched):
            pf = py.run(s, steps=80)[-1]
            for m in range(2):
                assert abs(pf.get(0, m) - bf.get(0, m)) < 1e-5
