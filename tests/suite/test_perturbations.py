"""Unit tests for :mod:`alienbio.suite.perturbations`.

Self-contained: worlds are built directly from ``MoleculeImpl`` / ``ReactionImpl``
/ ``ChemistryImpl`` (no pipeline, no mk registration dependency), each
perturbation is exercised in isolation, and every test asserts that *exactly* the
intended field changed and nothing else — plus that the perturbed world still
simulates and (for rate/spike) yields a Timeline that differs from the baseline's.
"""

from __future__ import annotations

import numpy as np
import pytest

from alienbio.bio.chemistry import ChemistryImpl, _mock_dat
from alienbio.bio.molecule import MoleculeImpl
from alienbio.bio.reaction import ReactionImpl
from alienbio.bio.world import Compartment, WorldImpl
from alienbio.suite.perturbations import (
    perturb_rate,
    remove_reaction,
    spike_concentration,
)
from alienbio.suite.verify import SimConfig, simulate


def _toy_world() -> WorldImpl:
    """A 3-molecule irreversible chain A -A_B-> B -B_C-> C, A seeded high."""
    a = MoleculeImpl("A", name="A", dat=_mock_dat("mol/A"))
    b = MoleculeImpl("B", name="B", dat=_mock_dat("mol/B"))
    c = MoleculeImpl("C", name="C", dat=_mock_dat("mol/C"))
    r_ab = ReactionImpl(
        "A_B", reactants={a: 1.0}, products={b: 1.0}, rate=0.5, dat=_mock_dat("rxn/A_B")
    )
    r_bc = ReactionImpl(
        "B_C", reactants={b: 1.0}, products={c: 1.0}, rate=0.5, dat=_mock_dat("rxn/B_C")
    )
    chem = ChemistryImpl(
        "host",
        molecules={"A": a, "B": b, "C": c},
        reactions={"A_B": r_ab, "B_C": r_bc},
        dat=_mock_dat("chem/host"),
    )
    comp = Compartment(
        "cell", None, "cell", 1.0, concentrations={"A": 100.0, "B": 0.0, "C": 0.0}
    )
    return WorldImpl(chem, (comp,))


def _reactant_names(rxn: ReactionImpl) -> set[str]:
    return {m.name for m in rxn.reactants}


def _product_names(rxn: ReactionImpl) -> set[str]:
    return {m.name for m in rxn.products}


def _timelines_differ(t1, t2) -> bool:
    """True if any co-sampled state array differs between two timelines."""
    if len(t1.states) != len(t2.states):
        return True
    return any(
        not np.allclose(s1.as_array(), s2.as_array())
        for s1, s2 in zip(t1.states, t2.states)
    )


# ── perturb_rate ────────────────────────────────────────────────────────────

def test_perturb_rate_scales_only_target_reaction():
    world = _toy_world()
    out = perturb_rate(world, "A_B", 3.0)

    # Exactly the target rate scaled.
    assert out.chemistry.reactions["A_B"].rate == pytest.approx(1.5)
    # Every other reaction untouched.
    assert out.chemistry.reactions["B_C"].rate == pytest.approx(0.5)
    # Reaction + molecule id sets unchanged.
    assert set(out.chemistry.reactions) == set(world.chemistry.reactions)
    assert set(out.chemistry.molecules) == set(world.chemistry.molecules)
    # Stoichiometry of the perturbed reaction is intact.
    assert _reactant_names(out.chemistry.reactions["A_B"]) == {"A"}
    assert _product_names(out.chemistry.reactions["A_B"]) == {"B"}
    # Input world is not mutated.
    assert world.chemistry.reactions["A_B"].rate == pytest.approx(0.5)


def test_perturb_rate_changes_trajectory():
    world = _toy_world()
    out = perturb_rate(world, "A_B", 3.0)
    cfg = SimConfig()
    baseline = simulate(world, cfg)
    perturbed = simulate(out, cfg)
    assert _timelines_differ(baseline, perturbed)


def test_perturb_rate_unknown_id_raises():
    world = _toy_world()
    with pytest.raises(KeyError):
        perturb_rate(world, "does_not_exist", 2.0)


def test_perturb_rate_callable_rate_raises():
    a = MoleculeImpl("A", name="A", dat=_mock_dat("mol/A"))
    b = MoleculeImpl("B", name="B", dat=_mock_dat("mol/B"))
    r = ReactionImpl(
        "A_B",
        reactants={a: 1.0},
        products={b: 1.0},
        rate=lambda state: 1.0,
        dat=_mock_dat("rxn/A_B"),
    )
    chem = ChemistryImpl(
        "host",
        molecules={"A": a, "B": b},
        reactions={"A_B": r},
        dat=_mock_dat("chem/host"),
    )
    comp = Compartment("cell", None, "cell", 1.0, concentrations={"A": 1.0, "B": 0.0})
    world = WorldImpl(chem, (comp,))
    with pytest.raises(TypeError):
        perturb_rate(world, "A_B", 2.0)


# ── remove_reaction ─────────────────────────────────────────────────────────

def test_remove_reaction_drops_only_that_reaction():
    world = _toy_world()
    out = remove_reaction(world, "B_C")

    assert "B_C" not in out.chemistry.reactions
    assert "A_B" in out.chemistry.reactions
    # Molecules are unchanged (removal drops a reaction, not any species).
    assert set(out.chemistry.molecules) == set(world.chemistry.molecules)
    # Input world is not mutated.
    assert "B_C" in world.chemistry.reactions


def test_remove_reaction_still_simulates_and_differs():
    world = _toy_world()
    out = remove_reaction(world, "B_C")
    cfg = SimConfig()
    baseline = simulate(world, cfg)
    perturbed = simulate(out, cfg)
    # With B_C gone, C never forms — the trajectory must differ.
    assert _timelines_differ(baseline, perturbed)


def test_remove_reaction_unknown_id_raises():
    world = _toy_world()
    with pytest.raises(KeyError):
        remove_reaction(world, "nope")


# ── spike_concentration ─────────────────────────────────────────────────────

def test_spike_concentration_adds_to_only_target_molecule():
    world = _toy_world()
    out = spike_concentration(world, "B", 10.0)

    conc = out.compartments[0].concentrations
    assert conc["B"] == pytest.approx(10.0)   # was 0.0, +10.0
    assert conc["A"] == pytest.approx(100.0)  # untouched
    assert conc["C"] == pytest.approx(0.0)    # untouched
    # Chemistry is reused by identity — nothing structural changed.
    assert out.chemistry is world.chemistry
    # Input world is not mutated.
    assert world.compartments[0].concentrations["B"] == pytest.approx(0.0)


def test_spike_concentration_changes_trajectory():
    world = _toy_world()
    out = spike_concentration(world, "B", 50.0)
    cfg = SimConfig()
    baseline = simulate(world, cfg)
    perturbed = simulate(out, cfg)
    assert _timelines_differ(baseline, perturbed)


def test_spike_concentration_defaults_missing_to_zero():
    # A molecule absent from the compartment's concentration map spikes from 0.0.
    a = MoleculeImpl("A", name="A", dat=_mock_dat("mol/A"))
    b = MoleculeImpl("B", name="B", dat=_mock_dat("mol/B"))
    r = ReactionImpl(
        "A_B", reactants={a: 1.0}, products={b: 1.0}, rate=0.5, dat=_mock_dat("rxn/A_B")
    )
    chem = ChemistryImpl(
        "host",
        molecules={"A": a, "B": b},
        reactions={"A_B": r},
        dat=_mock_dat("chem/host"),
    )
    # Only A listed; B omitted.
    comp = Compartment("cell", None, "cell", 1.0, concentrations={"A": 5.0})
    world = WorldImpl(chem, (comp,))
    out = spike_concentration(world, "B", 3.0)
    assert out.compartments[0].concentrations["B"] == pytest.approx(3.0)


def test_spike_concentration_unknown_molecule_raises():
    world = _toy_world()
    with pytest.raises(KeyError):
        spike_concentration(world, "Z", 1.0)
