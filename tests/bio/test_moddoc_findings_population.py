"""Module-doc findings on the population pass (``bio/population.py``): the
pass conserves molecule AMOUNT wherever a law moves content.

Repros (before the fix):

- a ``PerCapitaGrowth`` drawing its resource from its own compartment
  (N = 2, [R] = 1, V = 1, k = 1, stoich = 1, dt = 0.1) ended at R amount
  1.98, not 1.8: the draw was converted to a concentration on the old count
  and the newborns then held the post-draw concentration;
- a ``CountFlow`` moving one of ten instances holding [X] = 2 into an empty
  size class took the world's X from 20 to 18: the movers took on the
  destination's concentration;
- a ``PerCapitaDeath`` releasing into a compartment of multiplicity 0
  dropped the released biomass.
"""

from __future__ import annotations

import pytest

from alienbio.bio.compartment_tree import CompartmentTreeImpl
from alienbio.bio.population import CountFlow, PerCapitaDeath, PerCapitaGrowth
from alienbio.bio.world_simulator import WorldSimulatorImpl
from alienbio.bio.world_state import WorldStateImpl


def _state(n_comp: int, n_mol: int) -> tuple[CompartmentTreeImpl, WorldStateImpl]:
    tree = CompartmentTreeImpl()
    ids = [tree.add_root("c0")]
    for i in range(1, n_comp):
        ids.append(tree.add_child(ids[0], f"c{i}"))
    state = WorldStateImpl(
        tree=tree, num_molecules=n_mol,
        compartment_ids=[f"c{i}" for i in range(n_comp)],
        molecule_ids=[f"m{j}" for j in range(n_mol)],
    )
    return tree, state


def _step(tree, state, laws, n_mol: int, dt: float) -> WorldStateImpl:
    sim = WorldSimulatorImpl(
        tree=tree, reactions=[], flows=[], num_molecules=n_mol, dt=dt,
        population_laws=laws,
    )
    return sim.step(state)


def _total(state: WorldStateImpl, n_comp: int, n_mol: int) -> float:
    return sum(state.amount(c, m) for c in range(n_comp) for m in range(n_mol))


def test_growth_drawing_its_own_compartment_conserves_the_resource_amount() -> None:
    tree, state = _state(1, 1)
    state.set_multiplicity(0, 2.0)
    state.set(0, 0, 1.0)
    law = PerCapitaGrowth(
        compartment=0, resource_compartment=0, resource=0, stoich=1.0, rate_constant=1.0
    )
    out = _step(tree, state, [law], 1, 0.1)
    assert out.get_multiplicity(0) == pytest.approx(2.2)
    # 2.0 held, 0.2 drawn to fund the 0.2 newborns
    assert out.amount(0, 0) == pytest.approx(1.8)


def test_growth_drawing_its_own_compartment_keeps_other_contents_born_full() -> None:
    tree, state = _state(1, 2)
    state.set_multiplicity(0, 2.0)
    state.set(0, 0, 1.0)  # the resource
    state.set(0, 1, 3.0)  # biomass: newborns are born holding it
    law = PerCapitaGrowth(
        compartment=0, resource_compartment=0, resource=0, stoich=1.0, rate_constant=1.0
    )
    out = _step(tree, state, [law], 2, 0.1)
    assert out.get(0, 1) == 3.0


def test_count_flow_movers_carry_their_own_amounts() -> None:
    tree, state = _state(2, 1)
    state.set_multiplicity(0, 10.0)
    state.set(0, 0, 2.0)
    state.set_multiplicity(1, 10.0)  # holds no X
    law = CountFlow(origin=0, dest=1, rate_constant=0.1)
    out = _step(tree, state, [law], 1, 1.0)
    assert out.get_multiplicity(0) == pytest.approx(9.0)
    assert out.get_multiplicity(1) == pytest.approx(11.0)
    assert _total(out, 2, 1) == pytest.approx(20.0)
    assert out.get(0, 0) == 2.0  # the stayers keep their concentration
    assert out.get(1, 0) == pytest.approx(2.0 / 11.0)  # amount-weighted mix


def test_count_flow_mix_is_amount_weighted_across_volumes() -> None:
    tree, state = _state(2, 1)
    state.set_multiplicity(0, 10.0)
    state.set(0, 0, 2.0)
    state.set_multiplicity(1, 10.0)
    state.set_volume(1, 2.0)
    state.set(1, 0, 0.5)  # amount 10
    out = _step(tree, state, [CountFlow(origin=0, dest=1, rate_constant=0.1)], 1, 1.0)
    assert _total(out, 2, 1) == pytest.approx(30.0)
    # one mover of volume 1 brings amount 2 into 11 instances of volume 2
    assert out.get(1, 0) == pytest.approx(12.0 / 22.0)


def test_count_flow_into_an_empty_size_class_carries_the_concentration() -> None:
    tree, state = _state(2, 1)
    state.set_multiplicity(0, 10.0)
    state.set(0, 0, 2.0)
    state.set_multiplicity(1, 0.0)
    out = _step(tree, state, [CountFlow(origin=0, dest=1, rate_constant=0.1)], 1, 1.0)
    assert out.get(1, 0) == pytest.approx(2.0)
    assert _total(out, 2, 1) == pytest.approx(20.0)


def test_death_release_into_a_zero_size_compartment_stays_in_the_dying_one() -> None:
    tree, state = _state(2, 2)
    state.set_multiplicity(0, 10.0)
    state.set(0, 0, 1.0)  # biomass B, amount 10
    state.set_multiplicity(1, 0.0)  # the named release compartment is empty
    law = PerCapitaDeath(
        compartment=0, rate_constant=0.1, release_compartment=1, release_resource=1,
        release_stoich=1.0,
    )
    out = _step(tree, state, [law], 2, 1.0)
    assert out.get_multiplicity(0) == pytest.approx(9.0)
    # the dead instance's biomass (1.0) came back as R in the dying compartment
    assert out.amount(0, 1) == pytest.approx(1.0)
    assert _total(out, 2, 2) == pytest.approx(10.0)


def test_death_release_into_its_own_compartment_keeps_the_dying_share_out() -> None:
    """A death whose release names its own compartment still removes the
    dead instances' contents of that molecule (die-full) before adding the
    release."""
    tree, state = _state(1, 1)
    state.set_multiplicity(0, 10.0)
    state.set(0, 0, 1.0)
    law = PerCapitaDeath(
        compartment=0, rate_constant=0.1, release_compartment=0, release_resource=0,
        release_stoich=1.0,
    )
    out = _step(tree, state, [law], 1, 1.0)
    assert out.amount(0, 0) == pytest.approx(10.0)


def test_a_self_draw_and_a_death_together_never_over_draw_the_pool() -> None:
    """The growth draw is rationed against the pool LESS what the deaths
    carry out with them, so the two together cannot take it negative."""
    tree, state = _state(1, 1)
    state.set_multiplicity(0, 10.0)
    state.set(0, 0, 1.0)
    grow = PerCapitaGrowth(
        compartment=0, resource_compartment=0, resource=0, stoich=5.0, rate_constant=1.0
    )
    die = PerCapitaDeath(compartment=0, rate_constant=0.5)
    out = _step(tree, state, [grow, die], 1, 1.0)
    assert out.get(0, 0) >= 0.0
    assert out.amount(0, 0) == pytest.approx(0.0, abs=1e-12)
