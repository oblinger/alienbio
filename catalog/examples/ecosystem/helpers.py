"""helpers.py — executed by ``_includes_`` under a trusted load. Nothing here
knows about YAML: three registered heads, one guard, one plain function and
the drafter that turns ecosystem.yaml into a task for the experiment runner.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from alienbio.expr import Env, GuardViolation, X, evaluate, expander, fn, guard
from alienbio.suite.experiment import Draft
from alienbio.suite.skeleton import final_amount

HERE = Path(__file__).resolve().parent


# FUNCTION head: arguments arrive evaluated.
@fn(summary="carrier weight for the i-th energy state")
def carrier_weight(i: int) -> float:
    return 100.0 + 10.0 * i


# EXPANDER head: arguments arrive as forms, plus the environment. It returns
# a FORM (a block of reactions) that the interpreter evaluates in the caller's
# scope — so the pools it names are namespaced by the calling template
# instance, and the ``rate`` form left in every hop is drawn per hop.
@expander(summary="a conversion chain src -> x1 -> ... -> dst, as a block")
def chain(args, kwargs, env):
    src, dst = (evaluate(a, env) for a in args)
    n = int(evaluate(kwargs.get("length", 3), env))
    rate = kwargs.get("rate", X.parse("lognormal(0.1, 0.3)"))
    # interior pools are private to THIS chain: prefix them with the call's
    # key (chain0, chain1, ...) so two chains in one organism never alias
    label = env.path.rsplit(".", 1)[-1] if env.path else "chain"
    mids = [f"{label}.x{i}" for i in range(1, n)]
    nodes = [str(src), *mids, str(dst)]
    return X.block(
        children={
            f"hop{i}": X.reaction(reactants=[a], products=[b], rate=rate)
            for i, (a, b) in enumerate(zip(nodes, nodes[1:]), 1)
        }
    )


# GUARDS: predicates over what a call produced (here, the chain's block).
@guard(summary="the chain is short enough")
def max_pathway_length(block, ctx, max_length: int = 5) -> bool:
    if len(block.children) + 1 > max_length:
        raise GuardViolation(f"pathway too long: {len(block.children)} hops, max_length={max_length}")
    return True


@guard(summary="every hop has a product")
def no_dead_hops(block, ctx) -> bool:
    return all(any(p.direction.name == "OUT" for p in child.ports) for child in block.children)


# Not registered: reached only through !py. The scorer receives the trial's
# whole Timeline and reads the final level of vash's activated carrier.
def health_score(timeline) -> float:
    state = timeline.states[-1]
    ids = [m for m in (state.molecule_ids or ()) if str(m).endswith("vash.energy.ME2")]
    level = final_amount(timeline, ids[0]) if ids else 0.0
    return max(0.0, min(1.0, level / 4.0))


# DRAFTER head: what the experiment file's `task: !q ecosystem(chains=chains)`
# calls, once per trial, under the trial's seed. It loads this very file into
# a fresh environment with n_chains bound to the condition's value and returns
# the world and the task the file defines.
@fn(kind="drafter", summary="the ecosystem example as a drafter: (world, task) from ecosystem.yaml")
def ecosystem(*, chains: int = 2, env: Any) -> Draft:
    scope = Env.standard(seed=env.ctx.seed, trusted=True).load(HERE / "ecosystem.yaml")
    scope.bindings["n_chains"] = int(chains)
    return Draft(evaluate(X.name("world"), scope), evaluate(X.name("task"), scope))
