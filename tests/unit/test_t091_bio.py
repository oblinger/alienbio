"""T091 round 4, investigator C — bio findings 1-3 and the antiport snap.

The governing contract: the reference simulator matches JAX to 1e-9, and
where IEEE / JAX semantics give NaN the reference gives NaN too."""

from __future__ import annotations

import math
import random

import pytest

from alienbio.bio import CompartmentTreeImpl, ReactionSpec, WorldSimulatorImpl, WorldStateImpl
from alienbio.bio import rate_expr as rx
from alienbio.bio.flow import TransportFlux
from alienbio.bio.rate_expr import ieee_pow, snap_residue

try:
    import jax.numpy as jnp

    from alienbio.bio.jax_simulator import JaxWorldSimulator

    HAS_JAX = True
except ImportError:  # pragma: no cover
    HAS_JAX = False

needs_jax = pytest.mark.skipif(not HAS_JAX, reason="JAX not installed")


def _tree():
    tree = CompartmentTreeImpl()
    tree.add_root("o")
    return tree


# ── C1: a negative base under a non-integer exponent is NaN, overflow included ──


@needs_jax
@pytest.mark.parametrize("a,b", [(-2.0, 1100.5), (-0.5, -1100.5), (-2.0, 2.5), (-2.0, 1101.0), (-2.0, 1100.0), (2.0, 1100.5), (0.0, -1.0), (-0.0, -1.0)])
def test_ieee_pow_reads_every_edge_as_jnp_power(a, b):
    from alienbio.bio import jax_core

    jax_core.enable_x64()
    want = float(jnp.power(jnp.float64(a), jnp.float64(b)))
    got = ieee_pow(a, b)
    assert (math.isnan(got) and math.isnan(want)) or got == want, (a, b, got, want)


@needs_jax
def test_an_overflowing_negative_base_runs_no_reaction_on_either_backend():
    tree = _tree()
    law = ("pow", ("sub", ("species", 1), ("species", 2)), ("const", 1100.5))
    rxns = [ReactionSpec("r", {0: 1.0}, {3: 1.0}, rate_constant=1.0, rate_law=law)]
    st = WorldStateImpl(tree=tree, num_molecules=4)
    st.set(0, 0, 1.0)
    st.set(0, 1, 1.0)
    st.set(0, 2, 3.0)
    ref = WorldSimulatorImpl(tree, rxns, [], num_molecules=4, dt=0.1).step(st)
    jx = JaxWorldSimulator(tree, rxns, num_molecules=4, dt=0.1).step(st)
    assert (ref.get(0, 0), ref.get(0, 3)) == (1.0, 0.0)
    assert (jx.get(0, 0), jx.get(0, 3)) == (1.0, 0.0)


# ── C2: a hill (K, n) with no finite real K**n refuses at compile time ──────


@pytest.mark.parametrize("K,n", [(0.0, -1.0), (0.0, 0.5), (-0.5, 0.5), (-0.5, 2.0), (float("nan"), 2.0)])
def test_a_hill_with_no_real_k_pow_n_refuses_on_every_route(K, n):
    params = {"K": K, "n": n, "Vmax": 1.0}
    with pytest.raises(ValueError, match="hill modulation: K="):
        rx.modulation("hill", "M", params)
    with pytest.raises(ValueError, match="hill modulation: K="):
        rx.from_json(["mod", "hill", "M", params])
    with pytest.raises(ValueError, match="hill modulation: K="):
        rx.from_json(("mul", ("const", 1.0), ("mod", "hill", "M", params)))
    # ReactionSpec is what both simulators are built from: one refusal, one message.
    with pytest.raises(ValueError, match="hill modulation: K="):
        ReactionSpec("r", {0: 1.0}, {2: 1.0}, rate_law=("mod", "hill", 1, params))


@pytest.mark.parametrize("K,n", [(0.0, 2.0), (0.0, 0.0), (0.5, -1.0), (0.5, 0.5), (2.0, 3.0)])
def test_a_hill_with_a_real_k_pow_n_compiles(K, n):
    rx.modulation("hill", "M", {"K": K, "n": n})
    ReactionSpec("r", {0: 1.0}, {2: 1.0}, rate_law=("mod", "hill", 1, {"K": K, "n": n, "Vmax": 1.0}))


@needs_jax
def test_an_admitted_hill_agrees_on_both_backends():
    tree = _tree()
    for p in ({"K": 0.0, "n": 2.0, "Vmax": 1.0}, {"K": 0.5, "n": -1.0, "Vmax": 1.0}, {"K": 1e200, "n": 2.0, "Vmax": 1.0}):
        rxns = [ReactionSpec("r", {0: 1.0}, {2: 1.0}, rate_constant=1.0, rate_law=("mod", "hill", 1, p))]
        st = WorldStateImpl(tree=tree, num_molecules=3)
        st.set(0, 0, 1.0)
        st.set(0, 1, 2.0)
        ref = WorldSimulatorImpl(tree, rxns, [], num_molecules=3, dt=0.1).step(st)
        jx = JaxWorldSimulator(tree, rxns, num_molecules=3, dt=0.1).step(st)
        assert jx.get(0, 0) == pytest.approx(ref.get(0, 0), abs=1e-12), p


# ── C3: the rounding snap is relative to the pool it was drawn from ─────────


def test_snap_residue_is_relative_to_the_pre_pass_value():
    assert snap_residue(-1e-11, 1e5) == 0.0
    assert snap_residue(-1.1e-10, 1e6) == 0.0
    assert snap_residue(-1e-11, 1.0) == -1e-11  # below 1, the floor is absolute
    assert snap_residue(-5e-13, 0.3) == 0.0
    assert snap_residue(0.25, 1e6) == 0.25
    assert snap_residue(-1e-3, 1e6) == -1e-3  # a real negative is not rounding


@needs_jax
def test_a_large_pool_rationed_to_exhaustion_never_ends_negative_on_either_backend():
    tree = _tree()
    for trial in range(200):
        R = random.Random(trial)
        A = R.choice([1e3, 1e4, 1e5, 1e6])
        rxns = [
            ReactionSpec("r1", {0: 1.0}, {1: 1.0}, rate_constant=R.uniform(1, 50)),
            ReactionSpec("r2", {0: 1.0}, {2: 1.0}, rate_constant=R.uniform(1, 50)),
        ]
        st = WorldStateImpl(tree=tree, num_molecules=3)
        st.set(0, 0, A)
        ref = WorldSimulatorImpl(tree, rxns, [], num_molecules=3, dt=0.1).step(st)
        jx = JaxWorldSimulator(tree, rxns, num_molecules=3, dt=0.1).step(st)
        # Exhausted or not, rounding may leave a positive residue; never a negative.
        assert ref.get(0, 0) >= 0.0 and jx.get(0, 0) >= 0.0, (trial, ref.get(0, 0), jx.get(0, 0))
        assert jx.get(0, 0) == pytest.approx(ref.get(0, 0), rel=1e-9, abs=1e-9 * A)
        for m in (1, 2):
            assert jx.get(0, m) == pytest.approx(ref.get(0, m), rel=1e-9)


def test_a_rationed_antiport_never_leaves_its_losing_pool_negative():
    tree = CompartmentTreeImpl()
    root = tree.add_root("o")
    tree.add_child(root, "c")
    for t in range(2000):
        R = random.Random(t)
        st = WorldStateImpl(tree=tree, num_molecules=2)
        st.set(0, 0, R.uniform(1, 10))
        st.set(1, 1, R.uniform(0.01, 1.0))
        st.set_multiplicity(1, R.choice([1.0, 3.0, 7.0]))
        flux = TransportFlux(
            0, 1, {0: 1.0, 1: -R.choice([1.0, 3.0])}, driver_molecule=0,
            rate_constant=R.uniform(10, 1000), rate_law="first_order",
        )
        out = WorldSimulatorImpl(tree, [], [flux], num_molecules=2, dt=0.1).step(st)
        assert out.get(1, 1) >= 0.0, (t, out.get(1, 1))
