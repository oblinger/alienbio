"""helpers.py for the microcosm example — the drafter the experiment calls."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from alienbio.expr import Env, X, evaluate, fn
from alienbio.suite.experiment import Draft

HERE = Path(__file__).resolve().parent


@fn(kind="drafter", summary="the microcosm example as a drafter: (world, task) with feed_rate bound")
def microcosm(*, feed_rate: float = 0.6, env: Any) -> Draft:
    scope = Env.standard(seed=env.ctx.seed, trusted=True).load(HERE / "microcosm.yaml")
    scope.bindings["feed_rate"] = float(feed_rate)
    return Draft(evaluate(X.name("world"), scope), evaluate(X.name("task"), scope))
