"""M47.10 — the full rate grammar compiles and runs on both simulators.

A ``!q`` rate law beyond ``k × modulations`` (Michaelis–Menten over the
substrate, sums, ``exp`` / ``sqrt`` algebra, several modulations mixed with
algebra) compiles to a ``bio.rate_expr`` tree, realises onto the reaction,
and the reference simulator and the JAX core agree on it to float64
precision. Modulations (the product form) also now reach the JAX core — it
used to run mass action only.
"""

from __future__ import annotations

import math

import pytest

from alienbio.bio import CompartmentTreeImpl, ReactionSpec, WorldSimulatorImpl, WorldStateImpl
from alienbio.bio.rate_expr import eval_rate, from_json, implicit_mass_action, species_of, to_json, to_text
from alienbio.bio.reaction import Modulation
from alienbio.expr import Env, ExprError, X, evaluate
from alienbio.suite.rate_law import compile_rate
from alienbio.suite.verify import SimConfig, simulate

try:
    import jax  # noqa: F401

    HAS_JAX = True
except ImportError:  # pragma: no cover
    HAS_JAX = False


def _law(text: str, *, reactants=("S",), products=("P",), bindings=None):
    env = Env.standard(seed=1, bindings=bindings or {})
    return compile_rate(evaluate(X.quote(X.parse(text)), env), env, reactants=list(reactants), products=list(products))


# ---------------------------------------------------------------------------
# compilation
# ---------------------------------------------------------------------------


def test_product_form_still_compiles_to_modulations_not_an_expression():
    law = _law("k * hill(M, 0.5, n=2)", bindings={"k": 0.4})
    assert law.expr is None and [m.kind for m in law.modulations] == ["hill"] and law.modifier_pools == ("M",)


def test_substrate_saturation_over_a_reactant_is_the_whole_rate():
    law = _law("Vmax * S / (Km + S)", bindings={"Vmax": 2.0, "Km": 0.5})
    assert law.expr is not None and law.modulations == ()
    expr = law.realize_expr(Env.standard(seed=1).ctx.seed)
    assert species_of(expr) == {"S"} and not implicit_mass_action(expr, ["S"])
    assert eval_rate(expr, lambda s: 1.0) == pytest.approx(2.0 * 1.0 / 1.5)
    assert to_text(expr) == "((2.0 * S) / (0.5 + S))"


def test_algebra_with_modulations_and_math_and_dists():
    law = _law("k * hill(M, 0.5, n=2) + sqrt(A) * exp(-I) + lognormal(0.0, 0.1)", reactants=("A",), products=("B",), bindings={"k": 0.3})
    expr = law.realize_expr(Env.standard(seed=2).ctx.seed)
    assert species_of(expr) == {"M", "A", "I"} and set(law.expr_pools) == {"A", "I", "M"}
    value = eval_rate(expr, {"M": 0.5, "A": 4.0, "I": 0.0}.__getitem__)
    drawn = eval_rate(expr, {"M": 0.0, "A": 0.0, "I": 100.0}.__getitem__)  # only the drawn constant survives
    assert value == pytest.approx(0.3 * 0.5 + 2.0 + drawn)
    assert from_json(to_json(expr)) == expr


def test_what_is_still_refused_names_the_node():
    with pytest.raises(ExprError, match="unknown head 'source'|outside the rate grammar"):
        _law("k * source(pool='A')", bindings={"k": 1.0})
    with pytest.raises(ExprError, match="bool"):
        _law("True")


# ---------------------------------------------------------------------------
# the world: expression laws through the block heads
# ---------------------------------------------------------------------------

DOC = """
Vmax: 2.0
Km: 0.5
sk: !skeleton
  root: !block
    children:
      feed: !source {pool: S, rate: 1.0}
      conv: !reaction {reactants: [S], products: [P], rate: !q 'Vmax * S / (Km + S)'}
      gate: !reaction {reactants: [P], products: [Q], rate: !q '0.3 * hill(E, 0.5, n=2) * inhibitor(I, 1.0)'}
      odd: !reaction {reactants: [Q], products: [R], rate: !q 'sqrt(Q) * exp(-0.1 * E) + 0.05'}
      supplyE: !source {pool: E, rate: 0.2}
      supplyI: !source {pool: I, rate: 0.1}
w: !world {skeleton: !x sk, initial: {S: 1.0, E: 0.5, I: 0.2}}
"""


def test_expression_laws_reach_the_reaction_and_the_reference_simulator():
    values = Env.standard(seed=3).load("<rates>", text=DOC).force_all()
    world = values["w"]
    rxns = world.chemistry.reactions
    conv = next(r for rid, r in rxns.items() if rid.endswith("conv/rxn"))
    assert conv.rate_law is not None and to_text(conv.rate_law).startswith("((2.0 * ")
    odd = next(r for rid, r in rxns.items() if rid.endswith("odd/rxn"))
    assert {m.name for m in odd.modifiers} == {"root/E"}  # a read-only dependency, recorded as an inert modifier
    gate = next(r for rid, r in rxns.items() if rid.endswith("gate/rxn"))
    assert [m.kind for m in gate.modifiers.values()] == ["hill", "inhibitor"]
    timeline = simulate(world, SimConfig(dt=0.05, steps=40, sample_every=40))
    final = timeline.states[-1]
    ids = list(final.molecule_ids or ())
    p = final.get(0, ids.index("root/P"))
    assert p > 0.0 and math.isfinite(p)
    # a saved reaction round-trips its law
    from alienbio.bio.reaction import ReactionImpl

    back = ReactionImpl.hydrate(conv.attributes(), molecules={m.name: m for m in [*conv.reactants, *conv.products]})
    assert back.rate_law == conv.rate_law


# ---------------------------------------------------------------------------
# JAX parity
# ---------------------------------------------------------------------------


def _tree_and_state(values):
    tree = CompartmentTreeImpl()
    root = tree.add_root("organism")
    tree.add_child(root, "cell")
    state = WorldStateImpl(tree=tree, num_molecules=len(values))
    for c in range(2):
        for m, v in enumerate(values):
            state.set(c, m, v * (1.0 if c == 0 else 0.5))
    return tree, state


@pytest.mark.skipif(not HAS_JAX, reason="JAX not installed")
def test_jax_matches_reference_on_modulations_and_expression_laws():
    from alienbio.bio.jax_simulator import JaxWorldSimulator

    S, P, Q, E, I = range(5)
    mm = ("div", ("mul", ("const", 2.0), ("species", S)), ("add", ("const", 0.5), ("species", S)))
    odd = ("add", ("mul", ("sqrt", ("species", Q)), ("exp", ("neg", ("mul", ("const", 0.1), ("species", E))))), ("const", 0.05))
    reactions = [
        ReactionSpec("conv", {S: 1.0}, {P: 1.0}, rate_law=mm),                                   # whole rate
        ReactionSpec("gate", {P: 1.0}, {Q: 1.0}, rate_constant=0.3,
                     modulators={E: Modulation(kind="hill", Vmax=1.0, K=0.5, n=2.0), I: Modulation(kind="inhibitor", Ki=1.0)}),
        ReactionSpec("odd", {Q: 1.0}, {P: 0.5}, rate_law=odd),                                   # implicit mass action × law
        ReactionSpec("act", {E: 1.0}, {I: 1.0}, rate_constant=0.2, modulators={S: Modulation(kind="activator", a=2.0)}),
        ReactionSpec("sat", {I: 1.0}, {E: 1.0}, rate_constant=0.1, modulators={P: Modulation(kind="michaelis", Vmax=1.5, K=0.3)}),
    ]
    tree, state = _tree_and_state([1.0, 0.2, 0.1, 0.5, 0.2])
    ref = WorldSimulatorImpl(tree, reactions, [], num_molecules=5, dt=0.05)
    jx = JaxWorldSimulator(tree, reactions, num_molecules=5, dt=0.05)
    ref_final = ref.run(state, steps=60)[-1]
    jx_final = jx.run(state, steps=60)[-1]
    fast = jx.run_fast(state, steps=60)
    for c in range(2):
        for m in range(5):
            assert ref_final.get(c, m) == pytest.approx(jx_final.get(c, m), abs=1e-9), (c, m)
            assert ref_final.get(c, m) == pytest.approx(fast.get(c, m), abs=1e-9), (c, m)
    assert sum(ref_final.get(0, m) for m in range(5)) > 0.0
