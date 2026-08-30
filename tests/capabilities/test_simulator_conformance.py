"""M48.6 — simulator conformance, as properties.

Hypothesis draws random reaction systems — stoichiometry, rate constants,
every ``Modulation`` kind, compiled rate expressions, one or two
compartments — and every block in the library with random parameters; the
reference simulator and the JAX core must agree to float64 precision on
all of them, every concentration must stay finite and non-negative, and a
closed 1:1 system must conserve its total.
"""

from __future__ import annotations

import math

import pytest
from hypothesis import given, settings, strategies as st

from alienbio.bio import CompartmentTreeImpl, ReactionSpec, WorldSimulatorImpl, WorldStateImpl
from alienbio.bio.reaction import Modulation
from alienbio.expr import Env, X, evaluate
from alienbio.suite.verify import SimConfig, simulate

try:
    from alienbio.bio.jax_simulator import JaxWorldSimulator

    HAS_JAX = True
except ImportError:  # pragma: no cover
    HAS_JAX = False

needs_jax = pytest.mark.skipif(not HAS_JAX, reason="JAX not installed")

# ---------------------------------------------------------------------------
# strategies
# ---------------------------------------------------------------------------

positive = st.floats(min_value=0.01, max_value=2.0, allow_nan=False, allow_infinity=False)
conc = st.floats(min_value=0.0, max_value=5.0, allow_nan=False, allow_infinity=False)


@st.composite
def modulation(draw):
    kind = draw(st.sampled_from(["activator", "inhibitor", "michaelis", "hill", ""]))
    if kind == "activator":
        return Modulation(kind=kind, a=draw(positive))
    if kind == "inhibitor":
        return Modulation(kind=kind, Ki=draw(positive))
    if kind == "michaelis":
        return Modulation(kind=kind, Vmax=draw(positive), K=draw(positive))
    if kind == "hill":
        return Modulation(kind=kind, Vmax=draw(positive), K=draw(positive), n=draw(st.sampled_from([1.0, 2.0, 3.0])))
    return Modulation(kind="catalyst")  # inert


@st.composite
def rate_law(draw, n_mol):
    """A small random rate expression over molecule ids: constants, species,
    the four operators, exp / sqrt, a modulation."""
    def leaf():
        return draw(st.one_of(st.builds(lambda c: ("const", c), positive), st.builds(lambda i: ("species", i), st.integers(0, n_mol - 1))))

    a, b = leaf(), leaf()
    op = draw(st.sampled_from(["add", "mul", "div", "sqrt", "exp", "mod"]))
    if op == "sqrt":
        return ("sqrt", a)
    if op == "exp":
        return ("exp", ("neg", a))
    if op == "mod":
        return ("mul", a, ("mod", "michaelis", draw(st.integers(0, n_mol - 1)), {"K": draw(positive), "Vmax": draw(positive)}))
    return (op, a, b)


@st.composite
def system(draw):
    n_mol = draw(st.integers(2, 5))
    n_rxn = draw(st.integers(1, 4))
    reactions = []
    for i in range(n_rxn):
        r = draw(st.integers(0, n_mol - 1))
        p = draw(st.integers(0, n_mol - 1).filter(lambda x: x != r))
        mods = {}
        if draw(st.booleans()):
            m = draw(st.integers(0, n_mol - 1).filter(lambda x: x not in (r, p)))
            mods[m] = draw(modulation())
        law = draw(rate_law(n_mol)) if draw(st.booleans()) else None
        reactions.append(ReactionSpec(f"r{i}", {r: float(draw(st.integers(1, 2)))}, {p: float(draw(st.integers(1, 2)))}, rate_constant=draw(positive), modulators=mods, rate_law=law))
    comps = draw(st.integers(1, 2))
    tree = CompartmentTreeImpl()
    root = tree.add_root("organism")
    if comps == 2:
        tree.add_child(root, "cell")
    state = WorldStateImpl(tree=tree, num_molecules=n_mol)
    for c in range(comps):
        for m in range(n_mol):
            state.set(c, m, draw(conc))
    return tree, reactions, n_mol, state, draw(st.sampled_from([0.01, 0.05, 0.1])), draw(st.integers(1, 25))


# ---------------------------------------------------------------------------
# properties
# ---------------------------------------------------------------------------


def _finite_nonnegative(state, comps, n_mol):
    for c in range(comps):
        for m in range(n_mol):
            v = state.get(c, m)
            assert math.isfinite(v) and v >= 0.0, (c, m, v)


@settings(max_examples=60, deadline=None)
@given(system())
def test_reference_keeps_every_concentration_finite_and_non_negative(sys_):
    tree, reactions, n_mol, state, dt, steps = sys_
    final = WorldSimulatorImpl(tree, reactions, [], num_molecules=n_mol, dt=dt).run(state, steps=steps)[-1]
    _finite_nonnegative(final, tree.num_compartments, n_mol)


@needs_jax
@settings(max_examples=60, deadline=None)
@given(system())
def test_jax_matches_the_reference_on_random_systems(sys_):
    tree, reactions, n_mol, state, dt, steps = sys_
    ref = WorldSimulatorImpl(tree, reactions, [], num_molecules=n_mol, dt=dt).run(state, steps=steps)[-1]
    jx = JaxWorldSimulator(tree, reactions, num_molecules=n_mol, dt=dt).run(state, steps=steps)[-1]
    for c in range(tree.num_compartments):
        for m in range(n_mol):
            assert jx.get(c, m) == pytest.approx(ref.get(c, m), abs=1e-8, rel=1e-8), (c, m)


@settings(max_examples=40, deadline=None)
@given(system())
def test_a_closed_one_to_one_system_conserves_its_total(sys_):
    tree, reactions, n_mol, state, dt, steps = sys_
    balanced = [ReactionSpec(r.name, {k: 1.0 for k in r.reactants}, {k: 1.0 for k in r.products}, r.rate_constant, modulators=r.modulators, rate_law=r.rate_law) for r in reactions]
    final = WorldSimulatorImpl(tree, balanced, [], num_molecules=n_mol, dt=dt).run(state, steps=steps)[-1]
    for c in range(tree.num_compartments):
        before = sum(state.get(c, m) for m in range(n_mol))
        after = sum(final.get(c, m) for m in range(n_mol))
        assert after == pytest.approx(before, abs=1e-9)


# ---------------------------------------------------------------------------
# every block in the library, both backends
# ---------------------------------------------------------------------------

BLOCK_DOCS = {
    "source_sink": "feed: !source {pool: A, rate: !x r}\ndrain: !sink {pool: A, rate: !x r2}",
    "reaction": "feed: !source {pool: A, rate: !x r}\nconv: !reaction {reactants: [A], products: [B], rate: !x r2}\ndrain: !sink {pool: B, rate: 0.1}",
    "rate_law": "feed: !source {pool: S, rate: !x r}\nconv: !reaction {reactants: [S], products: [P], rate: !q 'r2 * S / (0.5 + S)'}\ndrain: !sink {pool: P, rate: 0.1}",
    "crux": "feed: !source {pool: P, rate: !x r}\nsplit: !crux {precursor: P, kA: !x r2, kB: 0.3}",
    "signal": "feed: !source {pool: A, rate: !x r}\nmod: !source {pool: S, rate: 0.2}\ngate: !signal {in_pool: A, out_pool: B, modifier: S, kind: activator, a: !x r2}\ndrain: !sink {pool: B, rate: 0.1}",
    "inhibit": "feed: !source {pool: A, rate: !x r}\nmod: !source {pool: I, rate: 0.2}\ngate: !inhibit {in_pool: A, out_pool: B, modifier: I, Ki: !x r2}",
    "enzyme": "feed: !source {pool: S, rate: !x r}\nmod: !source {pool: E, rate: 0.2}\ncat: !enzyme {substrate: S, product: P, enzyme: E, Vmax: !x r2, K: 0.5}",
    "cooperative": "feed: !source {pool: A, rate: !x r}\nmod: !source {pool: M, rate: 0.2}\ngate: !cooperative {in_pool: A, out_pool: B, modifier: M, K: 0.5, n: 2, Vmax: !x r2}",
    "insult": "feed: !source {pool: A, rate: !x r}\nstress: !insult {pool: A, rate: !x r2}",
    "transport": "feed: !source {pool: A, rate: !x r, container: cell}\npipe: !transport {pool: A, container: cell, dest_container: cell2, rate: !x r2}",
    "lattice": "patch: !lattice {k: 3, molecule: A, diffusion: !x r2}",
}


@pytest.mark.parametrize("name", sorted(BLOCK_DOCS))
@settings(max_examples=8, deadline=None)
@given(r=positive, r2=positive, seed=st.integers(0, 10_000))
def test_every_block_simulates_finite_on_the_reference_and_matches_jax(name, r, r2, seed):
    doc = f"r: {r}\nr2: {r2}\nsk: !skeleton\n  root: !block\n    children:\n" + "\n".join("      " + line for line in BLOCK_DOCS[name].splitlines()) + "\nw: !world {skeleton: !x sk}\n"
    world = Env.standard(seed=seed).load("<block>", text=doc).force_all()["w"]
    cfg = SimConfig(dt=0.05, steps=20, sample_every=20)
    ref = simulate(world, cfg).states[-1]
    n_mol = ref.num_molecules
    _finite_nonnegative(ref, len(world.compartments), n_mol)
    if HAS_JAX and not world.population_laws:
        ref_sim = WorldSimulatorImpl.from_chemistry(world.chemistry, world.initial_state.tree, flows=list(world.flow_objs), dt=cfg.dt)
        jx = JaxWorldSimulator(world.initial_state.tree, ref_sim._reactions, num_molecules=n_mol, dt=cfg.dt, flows=list(world.flow_objs))
        jx_final = jx.run(world.initial_state.copy(), steps=cfg.steps)[-1]
        for c in range(len(world.compartments)):
            for m in range(n_mol):
                assert jx_final.get(c, m) == pytest.approx(ref.get(c, m), abs=1e-8, rel=1e-8), (name, c, m)


@settings(max_examples=5, deadline=None)
@given(g=positive, d=positive)
def test_the_population_block_runs_finite_on_the_reference(g, d):
    doc = f"sk: !skeleton\n  root: !block\n    children:\n      feed: !source {{pool: food, rate: 0.5}}\n      herd: !population {{name: herd, growth_rate: {g}, death_rate: {d}}}\nw: !world {{skeleton: !x sk}}\n"
    world = Env.standard(seed=1).load("<pop>", text=doc).force_all()["w"]
    final = simulate(world, SimConfig(dt=0.05, steps=20, sample_every=20)).states[-1]
    _finite_nonnegative(final, len(world.compartments), final.num_molecules)
