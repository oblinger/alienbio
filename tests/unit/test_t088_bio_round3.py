"""T088 bio round 3: conservation, molecule/atom, energy, compartment tree,
makers and jax_core findings from the module-doc pass (2026-10-28)."""

from __future__ import annotations

import pytest

from alienbio.bio.atom import AtomImpl, COMMON_ATOMS
from alienbio.bio.compartment_tree import CompartmentTreeImpl
from alienbio.bio.conservation import VACUOUS, BALANCED, conservation_outcome
from alienbio.bio.energy import EnergyError, validate_energy
from alienbio.bio.reaction import Modulation
from alienbio.bio.world_simulator import ReactionSpec, WorldSimulatorImpl
from alienbio.bio.world_state import WorldStateImpl
from alienbio.infra.mk import mk
import alienbio.bio.makers  # noqa: F401  (registers mk.M / mk.R / mk.C)
from alienbio.suite.dist import Seed
from alienbio.suite.phase1_gen import build_phase1_skeleton


C = COMMON_ATOMS["C"]
H = COMMON_ATOMS["H"]
O = COMMON_ATOMS["O"]
CL = COMMON_ATOMS["Cl"]


# ── conservation 1: a vacuous pass is a distinct outcome ─────────────────


def test_generated_skeleton_conservation_reads_vacuous():
    skeleton = build_phase1_skeleton(coupling="up")
    skeleton.materialize(Seed(1))
    assert skeleton.validate() is None  # the generator's gate still passes
    assert skeleton.conservation == VACUOUS


def test_conservation_outcome_balanced_and_violated():
    a = mk.M("a", atoms={C: 1, O: 2})
    b = mk.M("b", atoms={C: 1, O: 2})
    two_b = mk.M("c", atoms={C: 2, O: 4})
    ok = mk.C("w", [a, b], [mk.R("r", {a: 1}, {b: 1})])
    bad = mk.C("w", [a, two_b], [mk.R("r", {a: 1}, {two_b: 1})])
    assert conservation_outcome(ok) == BALANCED
    assert conservation_outcome(bad).startswith("violated")
    x, y = mk.M("x"), mk.M("y")
    assert conservation_outcome(mk.C("w", [x, y], [mk.R("r", {x: 1}, {y: 2})])) == VACUOUS


# ── molecule 1–2: Hill order and honest atom equality ────────────────────


def test_symbol_is_hill_order():
    assert mk.M("hcl", atoms={H: 1, CL: 1}).symbol == "ClH"
    assert mk.M("glucose", atoms={O: 6, H: 12, C: 6}).symbol == "C6H12O6"
    assert mk.M("water", atoms={O: 1, H: 2}).symbol == "H2O"


def test_atoms_with_one_symbol_and_different_weights_are_not_equal():
    fake = AtomImpl("C", "Fake", 99.0)
    assert fake != C
    assert AtomImpl("C", "Carbon", C.atomic_weight) == C


def test_chemistry_refuses_two_atoms_under_one_symbol():
    fake = AtomImpl("C", "Fake", 99.0)
    a = mk.M("a", atoms={C: 1})
    b = mk.M("b", atoms={fake: 1})
    with pytest.raises(ValueError, match="different atom under the symbol 'C'"):
        mk.C("w", [a, b], [])
    with pytest.raises(ValueError, match="share a symbol"):
        mk.M("ab", atoms={C: 1, fake: 1})


# ── energy 2: the fail-visibly wrapper checks by default ─────────────────


def test_validate_energy_checks_spontaneity_by_default():
    hi = mk.M("hi", formation_energy=1.0)
    lo = mk.M("lo", formation_energy=2.0)
    uphill = mk.C("w", [hi, lo], [mk.R("r", {hi: 1}, {lo: 1})])
    with pytest.raises(EnergyError):
        validate_energy(uphill)
    assert validate_energy(uphill, spontaneity=False) is None


# ── compartment_tree 1–4 ─────────────────────────────────────────────────


def test_add_child_negative_parent_leaves_tree_unchanged():
    tree = CompartmentTreeImpl()
    tree.add_root("org")
    with pytest.raises(ValueError):
        tree.add_child(-1, "bad")
    assert tree.num_compartments == 1


def test_str_draws_connectors_at_every_depth():
    tree = CompartmentTreeImpl()
    root = tree.add_root("org")
    organ = tree.add_child(root, "organ")
    cell = tree.add_child(organ, "cell")
    tree.add_child(cell, "nucleus")
    assert str(tree).splitlines() == [
        "org (0)",
        "└── organ (1)",
        "    └── cell (2)",
        "        └── nucleus (3)",
    ]


def test_from_dict_copies_and_validates():
    tree = CompartmentTreeImpl()
    tree.add_child(tree.add_root(), "cell")
    data = tree.to_dict()
    rebuilt = CompartmentTreeImpl.from_dict(data)
    rebuilt.add_child(0, "more")
    assert len(data["parents"]) == 2
    for bad in (
        {"parents": [None, None], "names": ["a", "b"]},
        {"parents": [1, 0], "names": ["a", "b"]},
        {"parents": [None, 2, 1], "names": ["a", "b", "c"]},
        {"parents": [None, 7], "names": ["a", "b"]},
        {"parents": [None], "names": ["a", "b"]},
    ):
        with pytest.raises(ValueError):
            CompartmentTreeImpl.from_dict(bad)


def test_children_is_a_copy():
    tree = CompartmentTreeImpl()
    root = tree.add_root()
    tree.children(root).append(99)
    assert tree.children(root) == []


# ── makers 1: a local-name collision refuses ─────────────────────────────


def test_mk_c_refuses_two_entities_sharing_a_local_name():
    with pytest.raises(ValueError, match="share the local name 'A'"):
        mk.C("w", [mk.M("A"), mk.M("A", description="second")], [])
    a = mk.M("A")
    assert list(mk.C("w", [a, a], []).molecules) == ["A"]


# ── jax_core 1–2: bad compartment ids refuse; Ki = 0 is the perfect-inhibitor limit ──


def _two_compartments() -> CompartmentTreeImpl:
    tree = CompartmentTreeImpl()
    tree.add_child(tree.add_root(), "cell")
    return tree


@pytest.mark.parametrize("comps", [[-1], [5], [True]])
def test_reference_refuses_a_compartment_id_outside_the_tree(comps):
    spec = ReactionSpec("r", {0: 1}, {1: 1}, compartments=comps)
    with pytest.raises(ValueError, match="compartment"):
        WorldSimulatorImpl(_two_compartments(), [spec], [], 2)


def test_jax_refuses_a_compartment_id_outside_the_tree():
    jax_sim = pytest.importorskip("alienbio.bio.jax_simulator")
    if not jax_sim.HAS_JAX:
        pytest.skip("JAX not installed")
    for comps in ([-1], [5]):
        spec = ReactionSpec("r", {0: 1}, {1: 1}, compartments=comps)
        with pytest.raises(ValueError, match="compartment"):
            jax_sim.JaxWorldSimulator(_two_compartments(), [spec], 2)


def test_ki_zero_inhibitor_absent_leaves_rate_alone_on_both_backends():
    tree = _two_compartments()
    spec = [
        ReactionSpec(
            "r", {0: 1}, {1: 1}, rate_constant=1.0,
            modulators={2: Modulation(kind="inhibitor", Ki=0.0)},
        )
    ]
    state = WorldStateImpl(tree=tree, num_molecules=3)
    state.set(0, 0, 1.0)
    state.set(1, 0, 1.0)
    state.set(1, 2, 0.5)  # inhibitor present only in compartment 1
    ref = WorldSimulatorImpl(tree, spec, [], 3, dt=0.1).step(state)
    assert ref.get(0, 1) == pytest.approx(0.1)
    assert ref.get(1, 1) == 0.0
    jax_sim = pytest.importorskip("alienbio.bio.jax_simulator")
    if jax_sim.HAS_JAX:
        jx = jax_sim.JaxWorldSimulator(tree, spec, 3, dt=0.1).step(state)
        assert jx.get(0, 1) == pytest.approx(0.1)
        assert jx.get(1, 1) == 0.0


def test_modulation_refuses_a_negative_ki():
    with pytest.raises(ValueError, match="Ki"):
        Modulation(kind="inhibitor", Ki=-1.0)
    with pytest.raises(ValueError, match="Ki"):
        Modulation(kind="inhibitor", Ki=float("nan"))
