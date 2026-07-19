"""Tests for the opt-in boundedness/homeostasis gate (suite/boundedness.py, F019)."""

from __future__ import annotations

from typing import cast

from alienbio.bio import makers as _makers  # noqa: F401  (registers mk.M/mk.R/mk.C)
from alienbio.bio.chemistry import ChemistryImpl
from alienbio.bio.molecule import MoleculeImpl
from alienbio.bio.reaction import ReactionImpl
from alienbio.bio.world import Compartment, WorldImpl
from alienbio.infra.mk import mk
from alienbio.suite.boundedness import (
    check_boundedness,
    repair_static,
    simulate_boundedness,
    static_bounded_fate,
)
from alienbio.suite.conflict_gen import draft_conflict_world
from alienbio.suite.dist import Seed


def _mol(name: str) -> MoleculeImpl:
    return cast(MoleculeImpl, mk.M(name))


def _rxn(name: str, reactants=None, products=None, rate: float = 1.0) -> ReactionImpl:
    return cast(ReactionImpl, mk.R(name, reactants=reactants, products=products, rate=rate))


def _chem(molecules, *reactions: ReactionImpl) -> ChemistryImpl:
    return cast(ChemistryImpl, mk.C("test", molecules, list(reactions)))


def _world(chem: ChemistryImpl, concentrations: dict[str, float] | None = None) -> WorldImpl:
    comp = Compartment("cell", None, "cell", 1.0, concentrations=concentrations or {})
    return WorldImpl(chem, (comp,))


# ── Static layer ─────────────────────────────────────────────────────────────


def test_static_bounded_fate_flags_pure_accumulator():
    x = _mol("x")
    source = _rxn("source", reactants=None, products={x: 1})
    chem = _chem([x], source)

    flagged = static_bounded_fate(chem)

    assert [p.name for p in flagged] == ["x"]
    assert "source" in flagged[0].reason


def test_static_bounded_fate_passes_well_formed_chemistry():
    x = _mol("x")
    source = _rxn("source", reactants=None, products={x: 1})
    sink = _rxn("sink", reactants={x: 1}, products=None, rate=0.5)
    chem = _chem([x], source, sink)

    assert static_bounded_fate(chem) == []


def test_repair_static_gives_bounded_fate_and_is_idempotent():
    x = _mol("x")
    source = _rxn("source", reactants=None, products={x: 1})
    chem = _chem([x], source)

    repaired = repair_static(chem)

    assert static_bounded_fate(repaired) == []
    assert len(repaired.reactions) == 2  # original source + the added dilution sink

    # A chemistry with nothing flagged is returned unchanged.
    assert repair_static(repaired) is repaired


def test_repair_static_is_noop_on_a_clean_chemistry():
    x = _mol("x")
    source = _rxn("source", reactants=None, products={x: 1})
    sink = _rxn("sink", reactants={x: 1}, products=None, rate=0.5)
    chem = _chem([x], source, sink)

    assert repair_static(chem) is chem


# ── Dynamic layer ────────────────────────────────────────────────────────────


def test_simulate_boundedness_flags_diverging_pool():
    # Source + a weak linear sink, but an autocatalytic route (p -> 2p) whose
    # net first-order rate (k_auto - k_sink) is positive: exponential blow-up
    # despite p having a bona fide consuming reaction (the static check alone
    # would miss this — it only sees "p has a consumer").
    p = _mol("p")
    source = _rxn("source", reactants=None, products={p: 1}, rate=1.0)
    autocat = _rxn("autocat", reactants={p: 1}, products={p: 2}, rate=1.0)
    sink = _rxn("sink", reactants={p: 1}, products=None, rate=0.1)
    world = _world(_chem([p], source, autocat, sink))

    report = simulate_boundedness(world, Seed(0))

    traj = {t.name: t for t in report.dynamic}
    assert traj["p"].classification == "diverging"
    assert traj["p"].factor >= 10.0
    assert report.diverging and traj["p"] in report.diverging


def test_simulate_boundedness_passes_self_limiting_pool():
    # A first-order consumer's rate rises with substrate (density-mediated
    # mass-action) — passive homeostasis is free, no repair needed.
    p = _mol("p")
    source = _rxn("source", reactants=None, products={p: 1}, rate=1.0)
    sink = _rxn("sink", reactants={p: 1}, products=None, rate=1.0)
    world = _world(_chem([p], source, sink))

    report = simulate_boundedness(world, Seed(0))

    traj = {t.name: t for t in report.dynamic}
    assert traj["p"].classification == "bounded"
    assert not report.diverging
    assert not report.collapsing


def test_simulate_boundedness_flags_collapsing_pool():
    p = _mol("p")
    sink = _rxn("sink", reactants={p: 1}, products=None, rate=1.0)
    world = _world(_chem([p], sink), concentrations={"p": 100.0})

    report = simulate_boundedness(world, Seed(0))

    traj = {t.name: t for t in report.dynamic}
    assert traj["p"].classification == "collapsing"
    assert traj["p"].factor <= 0.1
    assert report.collapsing and traj["p"] in report.collapsing


def test_simulate_boundedness_deterministic_given_seed():
    p = _mol("p")
    source = _rxn("source", reactants=None, products={p: 1}, rate=1.0)
    autocat = _rxn("autocat", reactants={p: 1}, products={p: 2}, rate=1.0)
    sink = _rxn("sink", reactants={p: 1}, products=None, rate=0.1)
    world = _world(_chem([p], source, autocat, sink))

    r1 = simulate_boundedness(world, Seed(42))
    r2 = simulate_boundedness(world, Seed(42))

    assert r1 == r2


# ── Combined convenience + real assembled worlds ────────────────────────────


def test_check_boundedness_combines_static_and_dynamic():
    x = _mol("x")
    source = _rxn("source", reactants=None, products={x: 1})
    world = _world(_chem([x], source))

    report = check_boundedness(world, Seed(0))

    assert [p.name for p in report.static_unbounded] == ["x"]
    assert not report.ok


def test_check_boundedness_passes_well_formed_world():
    x = _mol("x")
    source = _rxn("source", reactants=None, products={x: 1}, rate=1.0)
    sink = _rxn("sink", reactants={x: 1}, products=None, rate=1.0)
    world = _world(_chem([x], source, sink))

    report = check_boundedness(world, Seed(0))

    assert report.ok


def test_real_conflict_worlds_pass_boundedness():
    # Real assembled worlds (Source + ConflictCrux, every rung of the M31.1
    # ladder) — every pool has a sink/bounded fate by construction, so the
    # generator's own composed worlds should pass the gate untouched.
    for rung in ("single", "compatible", "latent", "forced"):
        world, _skeleton, _objective = draft_conflict_world(Seed(1), rung=rung)
        report = check_boundedness(world, Seed(1))
        assert report.ok, (
            f"rung={rung}: static={report.static_unbounded} dynamic="
            f"{[t for t in report.dynamic if t.classification != 'bounded']}"
        )
