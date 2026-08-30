"""helpers.py for the kinetics kit — the reference-vs-JAX comparison, two
id lookups, and the drafter the experiment calls."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from alienbio.bio.world_simulator import WorldSimulatorImpl
from alienbio.expr import Env, X, evaluate, fn
from alienbio.suite.experiment import Draft

HERE = Path(__file__).resolve().parent


@fn(summary="the id of the reaction whose skeleton node is `name` (e.g. r_mm)")
def reaction_id(world, name: str) -> str:
    matches = [rid for rid in world.chemistry.reactions if rid.endswith(f"/{name}/rxn")]
    if len(matches) != 1:
        raise ValueError(f"reaction_id: {name!r} matches {matches}")
    return matches[0]


@fn(summary="the id of the molecule whose pool is `name`")
def molecule_id(world, name: str) -> str:
    matches = [m for m in world.chemistry.molecules if m == name or m.endswith(f"/{name}")]
    if len(matches) != 1:
        raise ValueError(f"molecule_id: {name!r} matches {matches}")
    return matches[0]


@fn(summary="largest |reference - JAX| over every compartment and molecule after `steps` steps of `dt`")
def compare(world, steps: int = 100, dt: float = 0.05) -> dict[str, Any]:
    """Run the same world on the reference simulator and (when installed) the
    JAX core; report the largest divergence. ``{"max_abs_diff": float,
    "jax": bool, "steps": int}`` — ``jax`` is False when JAX is absent, in
    which case the diff is 0.0 by definition (nothing to compare)."""
    state0 = world.initial_state.copy()
    ref_sim = WorldSimulatorImpl.from_chemistry(world.chemistry, state0.tree, flows=list(world.flow_objs), dt=dt)
    ref = ref_sim.run(state0.copy(), steps=steps)[-1]
    try:
        from alienbio.bio.jax_simulator import JaxWorldSimulator
    except ImportError:
        return {"max_abs_diff": 0.0, "jax": False, "steps": steps}
    jx = JaxWorldSimulator(state0.tree, ref_sim.reactions, num_molecules=ref.num_molecules, dt=dt, flows=list(world.flow_objs))
    jfinal = jx.run(state0.copy(), steps=steps)[-1]
    worst = 0.0
    for c in range(ref.tree.num_compartments):
        for m in range(ref.num_molecules):
            worst = max(worst, abs(ref.get(c, m) - jfinal.get(c, m)))
    return {"max_abs_diff": worst, "jax": True, "steps": steps}


@fn(kind="drafter", summary="the kinetics kit as a drafter: (world, task) with enzyme_level bound")
def kinetics(*, enzyme_level: float = 0.8, env: Any) -> Draft:
    scope = Env.standard(seed=env.ctx.seed, trusted=True).load(HERE / "kinetics.yaml")
    scope.bindings["enzyme_level"] = float(enzyme_level)
    return Draft(evaluate(X.name("world"), scope), evaluate(X.name("task"), scope))
