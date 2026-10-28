"""Module-doc findings on ``bio/flow.py``.

Repros (before the fix):

- a ``Transport`` into a compartment of multiplicity 0 built a world whose
  flux drew its share out of the origin and dropped it (the receiving side
  of ``apply_events`` skipped a zero-size pool), so ``Σ amount`` fell every
  step with no error;
- ``TransportFlux.apply`` — the one-flux path neither simulator had called
  since T053 — throttled a co-transport twice and disagreed with
  ``apply_flows``; it is gone, and ``GeneralFlow.apply`` (the escape hatch
  the pass calls) stays.
"""

from __future__ import annotations

import pytest

from alienbio.bio.chemistry import ChemistryImpl, _mock_dat
from alienbio.bio.compartment_tree import CompartmentTreeImpl
from alienbio.bio.flow import Flow, GeneralFlow, TransportFlux, apply_flows
from alienbio.bio.molecule import MoleculeImpl
from alienbio.bio.world import Compartment, Transport, WorldImpl
from alienbio.bio.world_simulator import WorldSimulatorImpl
from alienbio.bio.world_state import WorldStateImpl


def _chem() -> ChemistryImpl:
    x = MoleculeImpl("X", name="X", dat=_mock_dat("mol/X"))
    y = MoleculeImpl("Y", name="Y", dat=_mock_dat("mol/Y"))
    return ChemistryImpl(
        "host", molecules={"X": x, "Y": y}, reactions={}, dat=_mock_dat("chem/host")
    )


def _comps(dest_mult: float = 1.0, dest_volume: float = 1.0) -> tuple[Compartment, ...]:
    return (
        Compartment("src", None, "env", 1.0, concentrations={"X": 4.0, "Y": 4.0}),
        Compartment("sink", "src", "cell", dest_volume, multiplicity=dest_mult),
    )


def _transport(stoich: dict[str, float]) -> Transport:
    return Transport(
        origin="src", dest="sink", stoichiometry=stoich, driver_molecule="X",
        rate_constant=0.5, rate_law="first_order", name="leak",
    )


def test_a_flux_into_a_zero_multiplicity_compartment_refuses_at_draft() -> None:
    with pytest.raises(ValueError, match=r"transport 'leak'.*'sink'.*size 0"):
        WorldImpl(_chem(), _comps(dest_mult=0.0), flows=(_transport({"X": 1.0}),))


def test_a_flux_into_a_zero_volume_compartment_refuses_at_draft() -> None:
    with pytest.raises(ValueError, match=r"transport 'leak'.*'sink'.*size 0"):
        WorldImpl(_chem(), _comps(dest_volume=0.0), flows=(_transport({"X": 1.0}),))


def test_an_antiported_species_makes_the_origin_a_receiver() -> None:
    """A negative-count species moves dest -> origin, so a zero-size origin
    would drop it the same way."""
    comps = (
        Compartment("src", None, "env", 1.0, multiplicity=0.0),
        Compartment("sink", "src", "cell", 1.0, concentrations={"X": 4.0, "Y": 4.0}),
    )
    with pytest.raises(ValueError, match=r"transport 'leak'.*'src'.*size 0"):
        WorldImpl(_chem(), comps, flows=(_transport({"X": 1.0, "Y": -1.0}),))


def test_a_flux_between_sized_compartments_still_builds() -> None:
    world = WorldImpl(_chem(), _comps(), flows=(_transport({"X": 1.0}),))
    assert len(world.flow_objs) == 1


def test_a_receiver_that_empties_mid_run_blocks_the_flux_and_conserves() -> None:
    """A population can die out after draft; the flux then moves nothing
    rather than drawing a share out of the origin into nowhere."""
    tree = CompartmentTreeImpl()
    a = tree.add_root("a")
    b = tree.add_child(a, "b")
    state = WorldStateImpl(tree=tree, num_molecules=1, compartment_ids=["a", "b"], molecule_ids=["X"])
    state.set(a, 0, 4.0)
    state.set_multiplicity(b, 0.0)
    flux = TransportFlux(
        origin=a, dest=b, stoichiometry={0: 1.0}, driver_molecule=0,
        rate_constant=0.5, rate_law="first_order",
    )
    out = WorldSimulatorImpl(tree=tree, reactions=[], flows=[flux], num_molecules=1, dt=1.0).step(state)
    assert out.amount(a, 0) + out.amount(b, 0) == pytest.approx(4.0)
    assert out.get(a, 0) == 4.0


def test_transport_flux_has_no_one_flow_apply() -> None:
    assert not hasattr(TransportFlux, "apply")
    assert "apply" not in getattr(Flow, "__abstractmethods__", frozenset())


def test_general_flow_apply_is_still_the_escape_hatch() -> None:
    tree = CompartmentTreeImpl()
    a = tree.add_root("a")
    state = WorldStateImpl(tree=tree, num_molecules=1, compartment_ids=["a"], molecule_ids=["X"])

    def bump(s: WorldStateImpl, _tree: CompartmentTreeImpl, dt: float) -> None:
        s.set(a, 0, s.get(a, 0) + dt)

    new_state = state.copy()
    apply_flows([GeneralFlow(origin=a, apply_fn=bump)], new_state, state, tree, 0.5)
    assert new_state.get(a, 0) == 0.5


def test_apply_flows_refuses_a_flow_it_cannot_run() -> None:
    class Odd(Flow):
        is_membrane_flow = False
        is_general_flow = False

        def compute_flux(self, state, tree):  # type: ignore[override]
            return 0.0

        def attributes(self):  # type: ignore[override]
            return {}

    tree = CompartmentTreeImpl()
    a = tree.add_root("a")
    state = WorldStateImpl(tree=tree, num_molecules=1, compartment_ids=["a"], molecule_ids=["X"])
    with pytest.raises(TypeError, match="apply_flows cannot run Odd"):
        apply_flows([Odd(origin=a)], state.copy(), state, tree, 1.0)
