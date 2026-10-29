"""Module-doc findings on the step's three passes (reaction -> flow ->
population): each pass computes its demands off the FROZEN start-of-step
state, but a later pass rations against the pool as it stands in the state
being written, so the passes together can never over-draw a pool.

Repro (before the fix): one pool A = 1.0, a fast A -> B and a fast transport
of A out (or a growth law drawing A) each rationed against the frozen 1.0, so
their combined draw took A to -1.0 at step end with total mass conserved.
"""

from __future__ import annotations

import pytest

from alienbio.bio.compartment_tree import CompartmentTreeImpl
from alienbio.bio.flow import TransportFlux
from alienbio.bio.population import PerCapitaGrowth
from alienbio.bio.rate_expr import parity_agrees
from alienbio.bio.world_simulator import ReactionSpec, WorldSimulatorImpl
from alienbio.bio.world_state import WorldStateImpl


def _world():
    tree = CompartmentTreeImpl()
    a = tree.add_root("a")
    b = tree.add_child(a, "b")
    state = WorldStateImpl(
        tree=tree, num_molecules=2, compartment_ids=["a", "b"], molecule_ids=["A", "B"]
    )
    state.set(a, 0, 1.0)
    state.set_multiplicity(b, 1.0)
    fast = ReactionSpec(name="r", reactants={0: 1.0}, products={1: 1.0}, rate_constant=50.0)
    return tree, state, a, b, fast


def _flux(a: int, b: int) -> TransportFlux:
    return TransportFlux(
        origin=a, dest=b, stoichiometry={0: 1.0}, driver_molecule=0,
        rate_constant=50.0, rate_law="first_order",
    )


def _growth(a: int, b: int) -> PerCapitaGrowth:
    return PerCapitaGrowth(
        compartment=b, resource_compartment=a, resource=0, stoich=1.0, rate_constant=50.0
    )


def _total(state: WorldStateImpl, tree: CompartmentTreeImpl) -> float:
    return sum(
        state.amount(c, m) for c in range(tree.num_compartments) for m in range(2)
    )


def test_reaction_then_flow_never_over_draws_the_pool() -> None:
    tree, state, a, b, fast = _world()
    sim = WorldSimulatorImpl(
        tree=tree, reactions=[fast], flows=[_flux(a, b)], num_molecules=2, dt=1.0
    )
    out = sim.step(state)
    assert out.get(a, 0) >= 0.0
    # the reaction took the whole pool first; the flow had nothing left
    assert out.get(a, 0) == 0.0 and out.get(a, 1) == pytest.approx(1.0)
    assert _total(out, tree) == pytest.approx(_total(state, tree))


def test_reaction_then_growth_never_over_draws_the_pool() -> None:
    tree, state, a, b, fast = _world()
    sim = WorldSimulatorImpl(
        tree=tree, reactions=[fast], flows=[], num_molecules=2, dt=1.0,
        population_laws=[_growth(a, b)],
    )
    out = sim.step(state)
    assert out.get(a, 0) >= 0.0
    # nothing left to draw, so nothing grew
    assert out.get_multiplicity(b) == 1.0


def test_flow_then_growth_never_over_draws_the_pool() -> None:
    tree, state, a, b, _ = _world()
    sim = WorldSimulatorImpl(
        tree=tree, reactions=[], flows=[_flux(a, b)], num_molecules=2, dt=1.0,
        population_laws=[_growth(a, b)],
    )
    out = sim.step(state)
    assert out.get(a, 0) >= 0.0


def test_a_later_pass_draws_what_the_earlier_pass_left() -> None:
    """A slow reaction leaves half the pool; the fast flow takes exactly that."""
    tree, state, a, b, _ = _world()
    slow = ReactionSpec(name="r", reactants={0: 1.0}, products={1: 1.0}, rate_constant=0.5)
    sim = WorldSimulatorImpl(
        tree=tree, reactions=[slow], flows=[_flux(a, b)], num_molecules=2, dt=1.0
    )
    out = sim.step(state)
    assert out.get(a, 0) == pytest.approx(0.0, abs=1e-15)
    assert out.get(b, 0) == pytest.approx(0.5)


def test_the_jax_host_step_follows_the_same_rule() -> None:
    """``JaxWorldSimulator.step`` runs the same host flow and population
    passes on the post-reaction state, so it inherits the rule. Its
    ``native_flows`` (device-side, ``jax_core.apply_native_flows``) already
    ration against the post-reaction pool (they move a fraction <= 1 of what
    the reaction kernel left) but compute that fraction off the
    post-reaction pool, not the frozen one — they have no reference
    counterpart beyond an equivalent ``GeneralFlow`` sequence, which also
    reads the state being written."""
    pytest.importorskip("jax")
    from alienbio.bio.jax_simulator import JaxWorldSimulator

    tree, state, a, b, fast = _world()
    flows = [_flux(a, b)]
    laws = [_growth(a, b)]
    ref = WorldSimulatorImpl(
        tree=tree, reactions=[fast], flows=flows, num_molecules=2, dt=1.0,
        population_laws=laws,
    ).step(state)
    jx = JaxWorldSimulator(
        tree, [fast], num_molecules=2, dt=1.0, flows=flows, population_laws=laws
    ).step(state)
    assert jx.get(a, 0) >= 0.0
    for comp in (a, b):
        for mol in (0, 1):
            assert parity_agrees(jx.get(comp, mol), ref.get(comp, mol)), (comp, mol)
    assert jx.get_multiplicity(b) == ref.get_multiplicity(b)

    native = JaxWorldSimulator(
        tree, [fast], num_molecules=2, dt=1.0, native_flows=[(a, b, 0, 50.0)]
    ).step(state)
    assert native.get(a, 0) >= 0.0


# ---- conc ** stoich on a negative concentration ----------------------------
#
# Repro (before the fix): a concentration below the rounding snap (here -0.5,
# as an Intervene or a GeneralFlow can leave it) under a non-integer
# stoichiometry made ``conc ** stoich`` complex on the reference, which then
# raised ``TypeError`` at ``max(0.0, rate)``; JAX reads the power as NaN and
# the clamp as no reaction. Both mass-action products now go through
# ``ieee_pow``.


def _negative_world(rate_law=None):
    from alienbio.bio import rate_expr as rx

    tree = CompartmentTreeImpl()
    a = tree.add_root("a")
    state = WorldStateImpl(tree=tree, num_molecules=2, compartment_ids=["a"], molecule_ids=["A", "B"])
    state.set(a, 0, -0.5)
    law = rx.const(2.0) if rate_law == "factor" else None
    rxn = ReactionSpec(
        name="r", reactants={0: 0.5}, products={1: 1.0}, rate_constant=2.0, rate_law=law
    )
    return tree, state, a, rxn


@pytest.mark.parametrize("rate_law", [None, "factor"])
def test_a_negative_base_under_a_fractional_stoich_is_no_reaction(rate_law) -> None:
    tree, state, a, rxn = _negative_world(rate_law)
    if rate_law == "factor":
        assert rxn.implicit_mass_action  # the law multiplies mass action
    sim = WorldSimulatorImpl(tree=tree, reactions=[rxn], flows=[], num_molecules=2, dt=0.1)
    out = sim.step(state)
    assert out.get(a, 0) == -0.5
    assert out.get(a, 1) == 0.0


def test_the_negative_base_reads_the_same_on_jax() -> None:
    pytest.importorskip("jax")
    from alienbio.bio.jax_simulator import JaxWorldSimulator

    tree, state, a, rxn = _negative_world()
    ref = WorldSimulatorImpl(tree=tree, reactions=[rxn], flows=[], num_molecules=2, dt=0.1).step(state)
    jx = JaxWorldSimulator(tree, [rxn], num_molecules=2, dt=0.1).step(state)
    for mol in (0, 1):
        assert parity_agrees(jx.get(a, mol), ref.get(a, mol)), mol
