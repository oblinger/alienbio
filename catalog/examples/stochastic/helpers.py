"""helpers.py for the stochastic environment — reading the reproducible
Poisson insult schedule off the materialized skeleton, running the world
through the schedule (an instantaneous loss of the stressed pool at each
drawn time), the recovery predicate over the resulting trace, an id lookup,
and the drafter the experiment calls."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from alienbio.bio.world_simulator import WorldSimulatorImpl
from alienbio.expr import Env, X, evaluate, fn
from alienbio.suite.blocks import PressureBlock
from alienbio.suite.experiment import Draft

HERE = Path(__file__).resolve().parent


@fn(summary="the id of the molecule whose pool is `name`")
def molecule_id(world, name: str) -> str:
    matches = [m for m in world.chemistry.molecules if m == name or m.endswith(f"/{name}")]
    if len(matches) != 1:
        raise ValueError(f"molecule_id: {name!r} matches {matches}")
    return matches[0]


@fn(summary="the id of the reaction whose skeleton node is `name`")
def reaction_id(world, name: str) -> str:
    matches = [rid for rid in world.chemistry.reactions if rid.endswith(f"/{name}/rxn")]
    if len(matches) != 1:
        raise ValueError(f"reaction_id: {name!r} matches {matches}")
    return matches[0]


@fn(summary="the Poisson insult times the materialized skeleton drew (sorted, reproducible per seed)")
def insult_times(skeleton) -> tuple:
    blocks = [b for b in skeleton.root.walk() if isinstance(b, PressureBlock) and b.poisson is not None]
    if len(blocks) != 1:
        raise ValueError(f"insult_times: expected exactly one Poisson insult block, found {len(blocks)}")
    return tuple(blocks[0].insult_times)


@fn(summary="simulate the world through the insult schedule: at each drawn time the stressed pool loses `loss`; returns {trace: [[t, level], ...], insults: [...]}")
def run_with_insults(
    world,
    times,
    stressed: str,
    loss: float = 1.0,
    dt: float = 0.05,
    horizon: float = 20.0,
) -> dict[str, Any]:
    """Piecewise integration: reference simulator between insults, and at each
    insult time the stressed pool drops by ``loss`` (floored at zero) — the
    discrete event the cached schedule encodes. The trace samples the
    stressed pool's level at every segment boundary and every ``dt`` step."""
    state = world.initial_state.copy()
    sim = WorldSimulatorImpl.from_chemistry(world.chemistry, state.tree, flows=list(world.flow_objs), dt=dt)
    mol_index = list(world.chemistry.molecules).index(stressed)

    trace: list[list[float]] = [[0.0, state.get(0, mol_index)]]
    now = 0.0
    events = sorted(t for t in times if t <= horizon)
    for boundary in events + [horizon]:
        steps = max(0, int(round((boundary - now) / dt)))
        if steps:
            for i, s in enumerate(sim.run(state.copy(), steps=steps)):
                trace.append([now + (i + 1) * dt, s.get(0, mol_index)])
                state = s
        now = boundary
        if boundary in events:
            state = state.copy()
            state.set(0, mol_index, max(0.0, state.get(0, mol_index) - loss))
            trace.append([now, state.get(0, mol_index)])
    return {"trace": trace, "insults": list(events)}


@fn(summary="True when the stressed pool recovers to `level` within `tau` after EVERY insult")
def recovered(run: dict, level: float, tau: float) -> dict[str, Any]:
    """The recovery predicate over a `run_with_insults` result: for each
    insult, did the trace climb back to ``level`` by ``t + tau``? Returns
    ``{ok: bool, per_insult: [bool, ...]}`` — a timeline predicate, checked,
    not judged."""
    trace = run["trace"]
    per_insult: list[bool] = []
    for t0 in run["insults"]:
        window = [x for t, x in trace if t0 < t <= t0 + tau]
        per_insult.append(any(x >= level for x in window))
    return {"ok": all(per_insult), "per_insult": per_insult}


@fn(kind="drafter", summary="the stochastic environment as a drafter: (world, predict task)")
def stochastic_world(*, env: Any) -> Draft:
    scope = Env.standard(seed=env.ctx.seed, trusted=True).load(HERE / "stochastic.yaml")
    return Draft(evaluate(X.name("world"), scope), evaluate(X.name("task"), scope))
