"""helpers.py for the cascade — the depth-sized signalling chain, the
perturbation the diagnose task is about, an id lookup, and the drafter the
experiment calls."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from alienbio.expr import Env, X, evaluate, fn
from alienbio.suite.arch_diagnose import perturb_reaction_rate
from alienbio.suite.experiment import Draft

HERE = Path(__file__).resolve().parent


@fn(summary="the signalling cascade's blocks, with `depth` amplification stages between receptor and output")
def cascade_children(depth: int, *, env: Any) -> dict[str, Any]:
    """The whole wiring, sized to the indirection-depth dial:

    - ``receptor`` — a `signal` block (linear activator): the ligand ``L``
      drives ``R -> S0``;
    - ``amp0 .. amp{depth-1}`` — `enzyme` blocks (michaelis): ``S{i} -> S{i+1}``
      catalysed by ``E`` — each stage is one more inferential step between
      the perturbable steps and the readout;
    - ``output`` — a `cooperative` block (hill): the last stage drives
      ``P -> O`` with a sigmoidal response;
    - ``feedback`` — a `signal` block: ``O`` accelerates the drain of ``S0``
      (negative feedback closing the loop);
    - ``buffer`` / ``unbuffer`` — a reversible complexation ``O + B <-> OB``
      that absorbs output spikes;
    - supplies and drains so every pool has a bounded fate.
    """
    depth = max(1, int(depth))
    heads = {h: env.head(h).fn for h in ("source", "sink", "reaction", "signal", "enzyme", "cooperative")}

    def make(head: str, key: str, **kwargs: Any):
        return heads[head](**kwargs, name=key, env=env.child(key))

    out: dict[str, Any] = {
        "feed_L": make("source", "feed_L", pool="L", rate=0.25),
        "feed_R": make("source", "feed_R", pool="R", rate=0.3),
        "feed_P": make("source", "feed_P", pool="P", rate=0.3),
        "feed_E": make("source", "feed_E", pool="E", rate=0.1),
        "receptor": make("signal", "receptor", in_pool="R", out_pool="S0", modifier="L", kind="activator", a=2.0, rate=0.2),
    }
    for i in range(depth):
        key = f"amp{i}"
        out[key] = make("enzyme", key, substrate=f"S{i}", product=f"S{i+1}", enzyme="E", Vmax=1.2, K=0.5, rate=0.2)
    out["output"] = make("cooperative", "output", in_pool="P", out_pool="O", modifier=f"S{depth}", Vmax=1.2, K=0.5, n=2, rate=0.05)
    out["feedback"] = make("signal", "feedback", in_pool="S0", out_pool="W", modifier="O", kind="activator", a=1.5, rate=0.1)
    out["buffer"] = make("reaction", "buffer", reactants=["O", "B"], products=["OB"], rate=0.3)
    out["unbuffer"] = make("reaction", "unbuffer", reactants=["OB"], products=["O", "B"], rate=0.05)
    out["drain_O"] = make("sink", "drain_O", pool="O", rate=0.08)
    out["drain_W"] = make("sink", "drain_W", pool="W", rate=0.2)
    out["drain_E"] = make("sink", "drain_E", pool="E", rate=0.05)
    out[f"drain_S{depth}"] = make("sink", f"drain_S{depth}", pool=f"S{depth}", rate=0.05)
    return out


@fn(summary="the id of the reaction whose skeleton node is `name` (e.g. amp0)")
def reaction_of(world, name: str) -> str:
    matches = [rid for rid in world.chemistry.reactions if rid.endswith(f"/{name}/rxn")]
    if len(matches) != 1:
        raise ValueError(f"reaction_of: {name!r} matches {matches}")
    return matches[0]


@fn(summary="the id of the molecule whose pool is `name`")
def mol_of(world, name: str) -> str:
    matches = [m for m in world.chemistry.molecules if m == name or m.endswith(f"/{name}")]
    if len(matches) != 1:
        raise ValueError(f"mol_of: {name!r} matches {matches}")
    return matches[0]


@fn(summary="a copy of the world with the named step throttled to `factor` of its rate")
def throttle(world, name: str, factor: float = 0.25):
    return perturb_reaction_rate(world, reaction_of(world, name), float(factor))


@fn(kind="drafter", summary="the cascade as a drafter: (perturbed world, diagnose task) with depth bound")
def cascade(*, depth: int = 2, env: Any) -> Draft:
    scope = Env.standard(seed=env.ctx.seed, trusted=True).load(HERE / "cascade.yaml")
    scope.bindings["depth"] = int(depth)
    return Draft(evaluate(X.name("pworld"), scope), evaluate(X.name("task"), scope))
