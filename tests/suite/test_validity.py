"""Tests for M27.3 — world-validity predicates (realness gates A + C).

(A) ``non_obvious_causal`` — a verify-predicate that accepts a world only when
the perturbation produces a non-trivial trajectory change.
(C) ``is_shortcut_resistant`` — the ground-truth answer must not be reproducible
by a cheap structural heuristic (degree / two-hop centrality).
"""

from __future__ import annotations

from alienbio.bio.chemistry import ChemistryImpl
from alienbio.bio.molecule import MoleculeImpl
from alienbio.bio.reaction import ReactionImpl
from alienbio.bio.world import Compartment, WorldImpl
from alienbio.infra.entity import MockDat
from alienbio.suite.validity import is_shortcut_resistant, non_obvious_causal
from alienbio.suite.verify import SimConfig, simulate


def _world(rate: float = 0.3) -> WorldImpl:
    a = MoleculeImpl("A", name="A", dat=MockDat("mol/A"))
    b = MoleculeImpl("B", name="B", dat=MockDat("mol/B"))
    r1 = ReactionImpl(
        "R1", reactants={a: 1.0}, products={b: 1.0}, rate=rate, dat=MockDat("rxn/R1")
    )
    chem = ChemistryImpl(
        "world",
        molecules={"A": a, "B": b},
        reactions={"R1": r1},
        dat=MockDat("chem/world"),
    )
    comps = (Compartment("cell", None, "cell", 1.0, concentrations={"A": 100.0, "B": 0.0}),)
    return WorldImpl(chem, comps)


# ── (A) non_obvious_causal ──────────────────────────────────────────────────

_CFG = SimConfig(dt=0.1, steps=50, sample_every=10)


def test_non_obvious_causal_true_when_perturbation_reveals():
    baseline = simulate(_world(rate=0.3), _CFG)
    perturbed = simulate(_world(rate=0.9), _CFG)  # different dynamics
    assert non_obvious_causal(min_deviation=1e-3)(baseline, perturbed) is True


def test_non_obvious_causal_false_when_no_change():
    world = _world()
    baseline = simulate(world, _CFG)
    identical = simulate(world, _CFG)  # zero deviation
    assert non_obvious_causal(min_deviation=1e-3)(baseline, identical) is False


def test_non_obvious_causal_respects_threshold():
    baseline = simulate(_world(rate=0.3), _CFG)
    perturbed = simulate(_world(rate=0.9), _CFG)
    # An absurdly high threshold rejects even a real deviation.
    assert non_obvious_causal(min_deviation=1e9)(baseline, perturbed) is False


# ── (C) is_shortcut_resistant ───────────────────────────────────────────────

def _star_chem() -> ChemistryImpl:
    """A star: A participates in three reactions (highest degree); B/C/D leaves."""
    mols = {x: MoleculeImpl(x, name=x, dat=MockDat(f"mol/{x}")) for x in ("A", "B", "C", "D")}
    a, b, c, d = mols["A"], mols["B"], mols["C"], mols["D"]
    r1 = ReactionImpl("R1", reactants={a: 1.0}, products={b: 1.0}, dat=MockDat("rxn/R1"))
    r2 = ReactionImpl("R2", reactants={a: 1.0}, products={c: 1.0}, dat=MockDat("rxn/R2"))
    r3 = ReactionImpl("R3", reactants={a: 1.0}, products={d: 1.0}, dat=MockDat("rxn/R3"))
    return ChemistryImpl(
        "world", molecules=mols, reactions={"R1": r1, "R2": r2, "R3": r3}, dat=MockDat("chem/world")
    )


def test_shortcut_resistant_false_when_answer_is_top_degree():
    # A is the highest-degree node; an answer of {A} is crackable by the heuristic.
    assert is_shortcut_resistant(_star_chem(), {"A"}, top_k=1) is False


def test_shortcut_resistant_true_when_answer_is_peripheral():
    # A leaf node is not what any cheap centrality heuristic would surface.
    assert is_shortcut_resistant(_star_chem(), {"B"}, top_k=1) is True


def test_empty_answer_is_trivially_resistant():
    assert is_shortcut_resistant(_star_chem(), set()) is True
