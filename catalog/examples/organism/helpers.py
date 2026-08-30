"""helpers.py for the organism example — two gates as guards, and the drafter."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from alienbio.bio.energy import EnergyError, validate_energy
from alienbio.expr import Env, GuardViolation, X, evaluate, fn, guard
from alienbio.suite.boundedness import check_boundedness
from alienbio.suite.experiment import Draft
from alienbio.suite.verify import SimConfig

HERE = Path(__file__).resolve().parent


# GUARD: energy accounting (F018) — every internal reaction runs downhill.
@guard(summary="every internal reaction has ΔG < 0 (sources and sinks exempt)")
def energy_valid(world, ctx) -> bool:
    try:
        validate_energy(world.chemistry, spontaneity=True, exempt_boundary=True)
    except EnergyError as exc:
        raise GuardViolation(str(exc)) from None
    return True


# GUARD: the boundedness gate (F019) — no pool grows or collapses without bound.
@guard(summary="every pool has a bounded fate, statically and under simulation")
def bounded(world, ctx) -> bool:
    report = check_boundedness(world, ctx.seed, sim_cfg=SimConfig(dt=0.1, steps=100, sample_every=10))
    if not report.ok:
        names = [u.name for u in report.static_unbounded] + [t.name for t in report.diverging + report.collapsing]
        raise GuardViolation(f"unbounded pools: {names}")
    return True


# DRAFTER: the experiment's `task: !q organism(transport_rate=...)`.
@fn(kind="drafter", summary="the organism example as a drafter: (body, task) with transport_rate bound")
def organism(*, transport_rate: float = 0.3, env: Any) -> Draft:
    scope = Env.standard(seed=env.ctx.seed, trusted=True).load(HERE / "organism.yaml")
    scope.bindings["transport_rate"] = float(transport_rate)
    return Draft(evaluate(X.name("body"), scope), evaluate(X.name("task"), scope))
