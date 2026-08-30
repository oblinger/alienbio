"""M48.3 — every head, every special form.

Every head the standard environment registers from the framework's own
modules is *called* by at least one test in the tree (statically: its name
appears as ``X.<head>(``, ``!<head>`` or ``"<head>"`` somewhere under
``tests/``), and every head has a signature the registry can describe.
"""

from __future__ import annotations

import re
from pathlib import Path

from alienbio.expr import Env, registry

TESTS = Path(__file__).resolve().parents[1]


def _framework_heads() -> list[str]:
    Env.standard()
    return sorted(
        name for name in registry.names()
        if not name.startswith("op:")
        and (getattr(registry.get(name).fn, "__module__", "") or "").startswith(("alienbio.", "builtins", "math"))
    )


def _test_corpus() -> str:
    return "\n".join(p.read_text() for p in TESTS.rglob("test_*.py"))


def test_every_framework_head_is_called_somewhere_in_the_tests():
    corpus = _test_corpus()
    uncalled = []
    for name in _framework_heads():
        patterns = (rf"X\.{re.escape(name)}\(", rf"!{re.escape(name)}\b", rf"[\"']{re.escape(name)}[\"']", rf"\b{re.escape(name)}\(")
        if not any(re.search(p, corpus) for p in patterns):
            uncalled.append(name)
    assert not uncalled, f"heads no test calls: {uncalled}"


def test_every_head_describes_itself():
    rows = {r["name"]: r for r in registry.describe()}
    for name in _framework_heads():
        row = rows[name]
        assert row["kind"] and row["signature"], name
        head = registry.get(name)
        assert head.is_special or head.is_expander or head.is_function, name


def test_the_heads_no_other_test_reaches_are_called_here():
    """The heads the rest of the tree never calls, each exercised once."""
    from alienbio.expr import X, evaluate
    from alienbio.suite.blocks import CooperativeBindingBlock, InhibitionBlock, PopulationBlock, PressureBlock, SignalingBlock
    from alienbio.suite.types import AnswerObjective, GraderSpec, OutcomeObjective

    env = Env.standard(seed=4)
    assert evaluate(X.constant(3), env) == 3
    assert evaluate(X.exponential(1.0), env) >= 0.0 and evaluate(X.poisson(2.0), env) >= 0
    assert evaluate(X.log(1.0), env) == 0.0 and evaluate(X.pow(2, 3), env) == 8
    assert isinstance(evaluate(X.signal(in_pool="A", out_pool="B", modifier="S", kind="activator", a=1.0), env), SignalingBlock)
    assert isinstance(evaluate(X.inhibit(in_pool="A", out_pool="B", modifier="I", Ki=0.5), env), InhibitionBlock)
    assert isinstance(evaluate(X.cooperative(in_pool="A", out_pool="B", modifier="M", K=0.5, n=2), env), CooperativeBindingBlock)
    assert isinstance(evaluate(X.insult(pool="A", rate=0.1), env), PressureBlock)
    assert isinstance(evaluate(X.population(name="cells", growth_rate=0.1, death_rate=0.05), env), PopulationBlock)
    assert evaluate(X.grader(kind="node_set", partial=True), env) == GraderSpec(kind="node_set", config={"partial": True})
    d = evaluate(X.diagnose(n_nodes=4), env)
    q = evaluate(X.diagnose_q(skeleton=d.task.skeleton, world=d.world), env)
    assert isinstance(q["objective"], AnswerObjective)
    p = evaluate(X.predict(n_nodes=4), env)
    pq = evaluate(X.predict_q(skeleton=p.task.skeleton, world=p.world, reaction_id="m0_m1", target_id="m3"), env)
    assert isinstance(pq["objective"], AnswerObjective)
    i = evaluate(X.intervene(n_nodes=4), env)
    iq = evaluate(X.intervene_q(skeleton=i.task.skeleton, world=i.world, target_value=1.0), env)
    assert isinstance(iq["objective"], OutcomeObjective)
    vocab = evaluate(X.vocabulary(world=d.world, extra_tokens=["up"]), env)
    assert vocab is not None
    flux = evaluate(X.Transport(origin="a", dest="b", molecule="glucose", rate=0.2), env)
    assert flux.driver_molecule == "glucose" and flux.stoichiometry == {"glucose": 1.0}
