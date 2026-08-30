"""M47.2 — layers 0–2 as heads: distributions as Dists, the block library with
pools-as-names binding, skeleton / world / sim / verify, and the six generative
world drafters."""

from __future__ import annotations

import pytest

from alienbio.expr import Env, ExprError, X, evaluate, fn, registry
from alienbio.suite.dist import Constant, Dist, Seed
from alienbio.suite.skeleton import PortDir, Skeleton, SkeletonBlock
from alienbio.suite.verify import SimConfig, simulate

CRUX_WORLD = """
supply_rate: 10.0
k_a: !q lognormal(0.0, 0.3)
sk: !skeleton
  crux: root/crux
  control_surface: [root/supply.precursor]
  root: !block
    role: crux
    children:
      supply: !source {pool: precursor, rate: !x supply_rate}
      crux:   !crux   {precursor: precursor, kA: !x k_a, kB: 0.7}
world: !world {skeleton: !x sk}
"""


def test_block_binds_children_that_name_the_same_pool():
    env = Env.standard(seed=3).load("crux.yaml", text=CRUX_WORLD)
    sk = evaluate(X.name("sk"), env)
    assert isinstance(sk, Skeleton)
    root = sk.root
    assert {c.name for c in root.children} == {"supply", "crux"}
    assert [p.name for p in root.ports] == ["precursor"] and root.ports[0].direction is PortDir.OUT
    assert {(b.a, b.b) for b in root.pool_bindings} == {("self.precursor", "supply.precursor"), ("self.precursor", "crux.precursor")}
    w = evaluate(X.name("world"), env)
    chem = w.chemistry
    supply_rxn = next(r for rid, r in chem.reactions.items() if rid.startswith("root/supply"))
    route_a = next(r for rid, r in chem.reactions.items() if rid.endswith("route_a/rxn"))
    assert list(supply_rxn.products)[0] is list(route_a.reactants)[0]  # one shared molecule
    assert supply_rxn.rate == 10.0
    assert route_a.rate != 1.0  # drawn from the quoted lognormal, not the class default
    assert simulate(w, SimConfig(steps=20)).states[-1] is not None


def test_dist_slots_accept_numbers_quoted_forms_and_dists():
    env = Env.standard(seed=1)
    s1 = evaluate(X.source(pool="A", rate=2.5), env)
    assert s1.rate == Constant(2.5)
    s2 = evaluate(X.source(pool="A", rate=X.quote(X.lognormal(0, 1))), env)
    assert isinstance(s2.rate, Dist) and s2.rate.sample(Seed(1)) == s2.rate.sample(Seed(1))
    with pytest.raises(ExprError, match="source.rate"):
        evaluate(X.source(pool="A", rate="fast"), env)
    with pytest.raises(ExprError, match="source.rate"):
        evaluate(X.source(pool="A", rate=True), env)


def test_reaction_head_and_block_names_come_from_the_document_key():
    env = Env.standard(seed=1)
    frag = evaluate(
        {"root": X.block(children={
            "feed": X.source(pool="A"),
            "r1": X.reaction(reactants=["A"], products=["B"], rate=0.4, stoich={"A": 2.0}),
            "drain": X.sink(pool="B"),
        })},
        env,
    )["root"]
    assert isinstance(frag, SkeletonBlock)
    names = {c.name for c in frag.children}
    assert names == {"feed", "r1", "drain"}
    r1 = next(c for c in frag.children if c.name == "r1")
    assert r1.stoich == {"A": 2.0} and r1.rate == Constant(0.4)
    assert {p.name: p.direction for p in frag.ports} == {"A": PortDir.OUT, "B": PortDir.OUT}
    with pytest.raises(ExprError, match="reaction: needs"):
        evaluate(X.reaction(), env)
    with pytest.raises(ExprError, match="unknown role"):
        evaluate(X.block(children={}, role="bogus"), env)


def test_world_initial_sets_a_pool_by_name_and_sim_builds_config():
    env = Env.standard(seed=2).load("crux.yaml", text=CRUX_WORLD)
    w = evaluate(X.world(skeleton=X.name("sk"), initial={"precursor": 5.0}), env)
    mol = w.compartments[0]
    assert mol.concentrations["root/precursor"] == 5.0
    with pytest.raises(ExprError, match="no pool or molecule"):
        evaluate(X.world(skeleton=X.name("sk"), initial={"nope": 1.0}), env)
    assert evaluate(X.sim(dt=0.05, steps=40), env) == SimConfig(dt=0.05, steps=40, sample_every=10)


def test_verify_redraws_until_the_predicate_holds():
    calls = {"n": 0}

    @fn(name="_t_perturb")
    def perturb(w):
        return w

    @fn(name="_t_valid")
    def valid(base, pert):
        calls["n"] += 1
        return calls["n"] >= 3

    env = Env.standard(seed=2).load("crux.yaml", text=CRUX_WORLD)
    w = evaluate(X.verify(world=X.name("world"), perturb="_t_perturb", valid="_t_valid", max_redraws=4, sim=X.sim(steps=5)), env)
    assert calls["n"] == 3 and w.chemistry is not None
    calls["n"] = -100
    with pytest.raises(ExprError, match="no world passed"):
        evaluate(X.verify(world=X.name("world"), perturb="_t_perturb", valid="_t_valid", max_redraws=1, sim=X.sim(steps=5)), env)


def test_generative_world_drafters_are_heads_under_the_node_seed():
    env = Env.standard(seed=5)
    out = evaluate({"w": X.pressure_world(pi=0.5, complexity=1, k_fast=X.quote(X.lognormal(-0.7, 0.2)))}, env)["w"]
    assert set(out) == {"world", "skeleton", "objective"} and isinstance(out["skeleton"], Skeleton)
    again = evaluate({"w": X.pressure_world(pi=0.5, complexity=1, k_fast=X.quote(X.lognormal(-0.7, 0.2)))}, Env.standard(seed=5))["w"]
    assert set(out["world"].chemistry.reactions) == set(again["world"].chemistry.reactions)
    d = evaluate(X.diagnosis_world(n_nodes=4), env)
    assert set(d) == {"world", "skeleton"}
    p = evaluate(X.prediction_world(n_nodes=4), env)
    assert "reaction_id" in p
    i = evaluate(X.intervention_world(n_nodes=4), env)
    assert set(i["target"]) == {"molecule", "value"}
    c = evaluate(X.conflict_world(rung="forced"), env)
    assert set(c) == {"world", "skeleton", "objective"}
    pair = evaluate(X.delta_pair(), env)
    assert len(pair) == 2 and set(pair[0]) == {"world", "skeleton", "objective"}
    assert registry.get("pressure_world").guarded_params == {"pi"}


# ---------------------------------------------------------------------------
# M47.3 — rate laws, the compiled tier
# ---------------------------------------------------------------------------


def test_rate_law_compiles_k_times_modulations_and_algebra_beyond_it():
    from alienbio.suite.rate_law import RateLaw, compile_rate

    env = Env.standard(seed=1, bindings={"k": 0.4, "Kd": 0.5})
    assert compile_rate(0.4, env) == RateLaw(k=Constant(0.4))
    law = compile_rate(evaluate(X.quote(X.parse("k * hill(M, Kd, n=2) * inhibitor('I', 0.1)")), env), env, reactants=["S"])
    assert law.k == Constant(0.4) and [m.kind for m in law.modulations] == ["hill", "inhibitor"]
    assert law.modifier_pools == ("M", "I")
    assert law.modulations[0].sample(Seed(1)).n == 2.0 and law.modulations[0].sample(Seed(1)).K == 0.5
    # a constant factor may be computed (exp of a constant, a draw) — it is still a constant k
    assert compile_rate(evaluate(X.quote(X.parse("2 * exp(k)")), env), env).k == Constant(2 * __import__("math").exp(0.4))
    # beyond the product form the law compiles to an expression (M47.10), not a refusal
    for algebra in ("k + 1", "k / 2", "Vmax * S / (Km + S)", "hill(S, 0.5)", "exp(M)"):
        law = compile_rate(evaluate(X.quote(X.parse(algebra)), Env.standard(seed=1, bindings={"k": 1.0, "Vmax": 1.0, "Km": 1.0})), env, reactants=["S"])
        assert law.expr is not None and law.modulations == ()
    with pytest.raises(ExprError, match="unknown head 'source'"):
        compile_rate(evaluate(X.quote(X.parse("k * source(pool='A')")), env), env)
    assert evaluate(X.parse("hill(0.5, 0.5, n=2)"), env) == pytest.approx(0.5)  # a rate head is a plain function outside a law


def test_reaction_with_a_rate_law_materializes_with_modifiers():
    doc = """
k: 0.4
sk: !skeleton
  root: !block
    children:
      feed: !source {pool: S, rate: 2.0}
      mod:  !source {pool: M, rate: 0.1}
      r1:   !reaction {reactants: [S], products: [P], rate: !q "k * hill(M, 0.5, n=2)"}
      drain: !sink {pool: P}
      drainM: !sink {pool: M}
world: !world {skeleton: !x sk}
"""
    env = Env.standard(seed=4).load("law.yaml", text=doc)
    w = evaluate(X.name("world"), env)
    rxn = next(r for rid, r in w.chemistry.reactions.items() if rid.startswith("root/r1"))
    assert rxn.rate == 0.4
    (mod_mol, modulation), = rxn.modifiers.items()
    assert mod_mol.name == "root/M" and modulation.kind == "hill" and modulation.n == 2.0
    assert simulate(w, SimConfig(steps=10)).states[-1] is not None
