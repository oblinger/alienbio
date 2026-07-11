"""H4: order-independent simultaneous reaction extent.

The three simulators (ReferenceSimulatorImpl, WorldSimulatorImpl, and the JAX
core via JaxWorldSimulator) apply every reaction's extent from the SAME frozen
start-of-step state and ration shared reactants by single-pass proportional
min-ratio scaling. This module pins the four H4 properties:

  * order-independence   -- permuting the reaction list changes nothing
  * non-negativity        -- competing reactions never drive a species negative
  * mass conservation     -- total is non-increasing through depletion
  * cross-sim agreement   -- all three sims agree on the same chemistry
"""

from __future__ import annotations

import itertools

import pytest

from alienbio.bio.molecule import MoleculeImpl
from alienbio.bio.reaction import ReactionImpl
from alienbio.bio.chemistry import ChemistryImpl
from alienbio.bio.state import StateImpl
from alienbio.bio.simulator import ReferenceSimulatorImpl
from alienbio.bio.compartment_tree import CompartmentTreeImpl
from alienbio.bio.world_state import WorldStateImpl
from alienbio.bio.world_simulator import ReactionSpec, WorldSimulatorImpl

try:
    import jax  # noqa: F401

    HAS_JAX = True
except ImportError:
    HAS_JAX = False


class MockDat:
    def __init__(self, path: str):
        self.path = path


# A reaction described independently of any simulator:
#   reactants / products : {molecule_name: stoich}, k : rate constant.
class RxnSpec:
    def __init__(self, name, reactants, products, k):
        self.name = name
        self.reactants = reactants
        self.products = products
        self.k = k


def _mass_action_rate(reactants, k):
    """Callable mass-action rate for the Chemistry/Reference path, matching the
    ID-based world/JAX sims (rate = k * Π conc**stoich)."""

    def rate(state):
        v = k
        for name, coef in reactants.items():
            v *= state[name] ** coef
        return v

    return rate


def build_reference(mol_names, rxns, initial, dt):
    mols = {n: MoleculeImpl(n, dat=MockDat(f"mol/{n}")) for n in mol_names}
    reactions = {}
    for r in rxns:
        reactions[r.name] = ReactionImpl(
            r.name,
            reactants={mols[n]: c for n, c in r.reactants.items()},
            products={mols[n]: c for n, c in r.products.items()},
            rate=_mass_action_rate(r.reactants, r.k),
            dat=MockDat(f"rxn/{r.name}"),
        )
    chem = ChemistryImpl(
        "test", molecules=mols, reactions=reactions, dat=MockDat("chem/test")
    )
    state = StateImpl(chem, initial=dict(initial))
    return ReferenceSimulatorImpl(chem, dt=dt), state


def build_world(mol_names, rxns, initial, dt):
    mol_to_id = {n: i for i, n in enumerate(mol_names)}
    tree = CompartmentTreeImpl()
    tree.add_root("organism")
    specs = [
        ReactionSpec(
            r.name,
            {mol_to_id[n]: c for n, c in r.reactants.items()},
            {mol_to_id[n]: c for n, c in r.products.items()},
            rate_constant=r.k,
        )
        for r in rxns
    ]
    sim = WorldSimulatorImpl(
        tree, specs, [], num_molecules=len(mol_names), dt=dt
    )
    state = WorldStateImpl(tree=tree, num_molecules=len(mol_names))
    for n, v in initial.items():
        state.set(0, mol_to_id[n], v)
    return sim, state, mol_to_id


def build_jax(mol_names, rxns, initial, dt):
    from alienbio.bio.jax_simulator import JaxWorldSimulator

    mol_to_id = {n: i for i, n in enumerate(mol_names)}
    tree = CompartmentTreeImpl()
    tree.add_root("organism")
    specs = [
        ReactionSpec(
            r.name,
            {mol_to_id[n]: c for n, c in r.reactants.items()},
            {mol_to_id[n]: c for n, c in r.products.items()},
            rate_constant=r.k,
        )
        for r in rxns
    ]
    sim = JaxWorldSimulator(tree, specs, num_molecules=len(mol_names), dt=dt)
    state = WorldStateImpl(tree=tree, num_molecules=len(mol_names))
    for n, v in initial.items():
        state.set(0, mol_to_id[n], v)
    return sim, state, mol_to_id


# A chemistry where reactions COMPETE for shared reactants:
#   r_ab: A + B -> C
#   r_ad: A -> D          (competes with r_ab for A)
#   r_be: B -> E          (competes with r_ab for B)
COMPETING = [
    RxnSpec("r_ab", {"A": 1, "B": 1}, {"C": 1}, k=0.7),
    RxnSpec("r_ad", {"A": 1}, {"D": 1}, k=0.9),
    RxnSpec("r_be", {"B": 1}, {"E": 1}, k=0.5),
]
COMPETING_MOLS = ["A", "B", "C", "D", "E"]
COMPETING_INIT = {"A": 1.0, "B": 0.8, "C": 0.0, "D": 0.0, "E": 0.0}


# ── Order-independence ─────────────────────────────────────────────────────────


class TestOrderIndependence:
    """Permuting the reaction list yields an identical trajectory."""

    def test_reference_order_independent(self):
        base_sim, base_state = build_reference(
            COMPETING_MOLS, COMPETING, COMPETING_INIT, dt=1.0
        )
        base = [
            {n: s[n] for n in COMPETING_MOLS}
            for s in base_sim.run(base_state, steps=8)
        ]
        for perm in itertools.permutations(COMPETING):
            sim, state = build_reference(
                COMPETING_MOLS, list(perm), COMPETING_INIT, dt=1.0
            )
            traj = sim.run(state, steps=8)
            for i, s in enumerate(traj):
                for n in COMPETING_MOLS:
                    assert s[n] == pytest.approx(base[i][n], abs=1e-12), (perm, i, n)

    def test_world_order_independent(self):
        base_sim, base_state, mid = build_world(
            COMPETING_MOLS, COMPETING, COMPETING_INIT, dt=1.0
        )
        base = [
            [s.get(0, mid[n]) for n in COMPETING_MOLS]
            for s in base_sim.run(base_state, steps=8)
        ]
        for perm in itertools.permutations(COMPETING):
            sim, state, mid2 = build_world(
                COMPETING_MOLS, list(perm), COMPETING_INIT, dt=1.0
            )
            traj = sim.run(state, steps=8)
            for i, s in enumerate(traj):
                for j, n in enumerate(COMPETING_MOLS):
                    assert s.get(0, mid2[n]) == pytest.approx(base[i][j], abs=1e-12)

    @pytest.mark.skipif(not HAS_JAX, reason="JAX not installed")
    def test_jax_order_independent(self):
        base_sim, base_state, mid = build_jax(
            COMPETING_MOLS, COMPETING, COMPETING_INIT, dt=1.0
        )
        base = [
            [s.get(0, mid[n]) for n in COMPETING_MOLS]
            for s in base_sim.run(base_state, steps=8)
        ]
        for perm in itertools.permutations(COMPETING):
            sim, state, mid2 = build_jax(
                COMPETING_MOLS, list(perm), COMPETING_INIT, dt=1.0
            )
            traj = sim.run(state, steps=8)
            for i, s in enumerate(traj):
                for j, n in enumerate(COMPETING_MOLS):
                    assert s.get(0, mid2[n]) == pytest.approx(base[i][j], abs=1e-9)


# ── Non-negativity under competition ───────────────────────────────────────────


class TestNonNegativityUnderCompetition:
    """Two+ reactions sharing a scarce reactant: nothing goes negative and
    total consumed of the scarce species never exceeds what was available."""

    def test_reference_no_negative_and_bounded_consumption(self):
        sim, state = build_reference(
            COMPETING_MOLS, COMPETING, COMPETING_INIT, dt=1.0
        )
        traj = sim.run(state, steps=15)
        for s in traj:
            for n in COMPETING_MOLS:
                assert s[n] >= -1e-12, f"{n} went negative: {s[n]}"
        # One-step scarce-reactant consumption bound: in the very first step,
        # A (=1.0) is demanded by r_ab (0.7*1*0.8=0.56) and r_ad (0.9*1=0.9),
        # total 1.46 > 1.0, so the fix must ration A. Consumed A <= available A.
        first = traj[0]
        second = traj[1]
        consumed_a = first["A"] - second["A"]
        assert consumed_a <= first["A"] + 1e-12
        assert second["A"] >= -1e-12

    def test_world_no_negative(self):
        sim, state, mid = build_world(
            COMPETING_MOLS, COMPETING, COMPETING_INIT, dt=1.0
        )
        traj = sim.run(state, steps=15)
        for s in traj:
            for n in COMPETING_MOLS:
                assert s.get(0, mid[n]) >= -1e-12

    @pytest.mark.skipif(not HAS_JAX, reason="JAX not installed")
    def test_jax_no_negative(self):
        sim, state, mid = build_jax(
            COMPETING_MOLS, COMPETING, COMPETING_INIT, dt=1.0
        )
        traj = sim.run(state, steps=15)
        for s in traj:
            for n in COMPETING_MOLS:
                assert s.get(0, mid[n]) >= -1e-9

    def test_scarce_reactant_two_reactions_split_fairly(self):
        """A is scarce; r_ad and r_ab both consume it. Proportional rationing:
        neither can over-consume, and A cannot be driven below zero even with a
        huge combined desired demand."""
        rxns = [
            RxnSpec("r_ad", {"A": 1}, {"D": 1}, k=100.0),
            RxnSpec("r_ab", {"A": 1, "B": 1}, {"C": 1}, k=100.0),
        ]
        mols = ["A", "B", "C", "D"]
        init = {"A": 1.0, "B": 1.0, "C": 0.0, "D": 0.0}
        sim, state = build_reference(mols, rxns, init, dt=1.0)
        nxt = sim.step(state)
        assert nxt["A"] == pytest.approx(0.0, abs=1e-12)
        assert nxt["A"] >= -1e-12
        # C + D produced == A consumed (== 1.0); mass moved, none created.
        assert nxt["C"] + nxt["D"] == pytest.approx(1.0, abs=1e-12)


# ── Mass conservation through depletion (C1 preserved) ─────────────────────────


class TestMassConservation:
    def test_reference_total_non_increasing_under_competition(self):
        sim, state = build_reference(
            COMPETING_MOLS, COMPETING, COMPETING_INIT, dt=1.0
        )
        traj = sim.run(state, steps=20)
        totals = [sum(s[n] for n in COMPETING_MOLS) for s in traj]
        # Pure conversions (1->1 and 1+1->1): A+B->C loses one unit of count,
        # so total (by molecule count) is non-increasing, never increasing.
        for i in range(1, len(totals)):
            assert totals[i] <= totals[0] + 1e-12

    def test_world_total_non_increasing(self):
        sim, state, mid = build_world(
            COMPETING_MOLS, COMPETING, COMPETING_INIT, dt=1.0
        )
        traj = sim.run(state, steps=20)
        totals = [sum(s.get(0, mid[n]) for n in COMPETING_MOLS) for s in traj]
        for i in range(1, len(totals)):
            assert totals[i] <= totals[0] + 1e-12


# ── Cross-sim agreement ────────────────────────────────────────────────────────


@pytest.mark.skipif(not HAS_JAX, reason="JAX not installed")
class TestCrossSimAgreement:
    """Reference, World, and JAX now agree on the same chemistry (H4)."""

    def _agree(self, mol_names, rxns, initial, steps, dt=1.0, tol=1e-6):
        ref_sim, ref_state = build_reference(mol_names, rxns, initial, dt)
        w_sim, w_state, w_id = build_world(mol_names, rxns, initial, dt)
        j_sim, j_state, j_id = build_jax(mol_names, rxns, initial, dt)

        ref = ref_sim.run(ref_state, steps=steps)[-1]
        w = w_sim.run(w_state, steps=steps)[-1]
        j = j_sim.run(j_state, steps=steps)[-1]

        for n in mol_names:
            rv = ref[n]
            wv = w.get(0, w_id[n])
            jv = j.get(0, j_id[n])
            assert wv == pytest.approx(rv, abs=tol), (n, "world", wv, rv)
            assert jv == pytest.approx(rv, abs=tol), (n, "jax", jv, rv)

    def test_competing_chemistry_all_three_agree(self):
        self._agree(COMPETING_MOLS, COMPETING, COMPETING_INIT, steps=30)

    def test_chain_chemistry_all_three_agree(self):
        # A -> B -> C chain (shares molecule B: product of one, reactant of the
        # other -- the case that used to diverge under sequential application).
        rxns = [
            RxnSpec("r1", {"A": 1}, {"B": 1}, k=0.3),
            RxnSpec("r2", {"B": 1}, {"C": 1}, k=0.2),
        ]
        self._agree(["A", "B", "C"], rxns, {"A": 10.0, "B": 0.0, "C": 0.0}, steps=40)

    def test_stoichiometric_chemistry_all_three_agree(self):
        rxns = [RxnSpec("r1", {"A": 2}, {"B": 1}, k=0.05)]
        self._agree(["A", "B"], rxns, {"A": 10.0, "B": 0.0}, steps=40)

    def test_depletion_chemistry_all_three_agree(self):
        # Huge rate forces the rationing/clamp path on every step.
        rxns = [RxnSpec("r1", {"A": 1}, {"B": 1}, k=100.0)]
        self._agree(["A", "B"], rxns, {"A": 1.0, "B": 0.0}, steps=20)
