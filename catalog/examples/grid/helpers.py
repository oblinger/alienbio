"""helpers.py for the grid — the grid generator sized to the `complexity`
and `n_nodes` dials, two id lookups, two example-owned scripted agents
(`trend_commit`, `prior_commit`, registered beside the framework's own), and the drafter
the experiment calls."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from alienbio.expr import Env, X, evaluate, fn
from alienbio.suite.agent import Commit, ScriptedAgent, Wait
from alienbio.suite.dist import Seed
from alienbio.suite.experiment import AGENTS, Draft
from alienbio.suite.observation import Observation
from alienbio.suite.types import Answer

HERE = Path(__file__).resolve().parent


@fn(summary="a grid of `rows` chains, each `steps` reactions long, with a source and a drain per row")
def grid_children(steps: int, rows: int, feed: float = 0.5, *, env: Any) -> dict[str, Any]:
    """Row r is ``S{r} -> X{r}_1 -> ... -> P{r}``; every row is fed at ``feed``
    and its product drained. Built through the registered ``source`` /
    ``reaction`` / ``sink`` heads so the result is a mapping of blocks."""
    steps, rows = max(1, int(steps)), max(1, int(rows))
    source, reaction, sink = (env.head(h).fn for h in ("source", "reaction", "sink"))
    out: dict[str, Any] = {}
    for r in range(rows):
        pools = [f"S{r}"] + [f"X{r}_{i}" for i in range(1, steps)] + [f"P{r}"]
        out[f"feed{r}"] = source(pool=pools[0], rate=float(feed), name=f"feed{r}", env=env.child(f"feed{r}"))
        for i in range(steps):
            key = f"row{r}_step{i}"
            out[key] = reaction(reactants=[pools[i]], products=[pools[i + 1]], rate=0.4, name=key, env=env.child(key))
        out[f"drain{r}"] = sink(pool=pools[-1], rate=0.1, name=f"drain{r}", env=env.child(f"drain{r}"))
    return out


@fn(summary="the id of the first reaction of row 0")
def first_reaction(world) -> str:
    matches = [rid for rid in world.chemistry.reactions if rid.endswith("/row0_step0/rxn")]
    if len(matches) != 1:
        raise ValueError(f"first_reaction: row0_step0 matches {matches}")
    return matches[0]


@fn(summary="the id of the molecule whose pool is `name`")
def molecule_id(world, name: str) -> str:
    matches = [m for m in world.chemistry.molecules if m == name or m.endswith(f"/{name}")]
    if len(matches) != 1:
        raise ValueError(f"molecule_id: {name!r} matches {matches}")
    return matches[0]


# ---- an agent of the example's own: watch row 0's product, commit its trend -

def _make_trend_policy(target_suffix: str = "/P0", eps: float = 1e-6):
    """Turn 1: note the target's level and wait. Turn 2: commit the direction
    it moved — the naive guess that the unperturbed trend is the answer. A
    toy, but one that answers, so the live arm scores against the idle twin."""
    before: dict[str, float] = {}

    def level(observation: Observation) -> float:
        for compartment in observation:
            for probe, value in compartment.items():
                if probe.endswith(target_suffix):
                    return float(value)
        raise KeyError(f"trend-commit: no probe ends with {target_suffix!r}")

    def policy(observation: Observation, seed: Seed):
        del seed
        now = level(observation)
        if "level" not in before:
            before["level"] = now
            return Wait(duration=1.0), ()
        delta = now - before["level"]
        answer = "up" if delta > eps else "down" if delta < -eps else "same"
        return Commit(answer=Answer(value=answer, kind="node_id")), ()

    return policy


def _trend_commit_agent_factory(seed: Seed, dials: Any):
    del dials
    return ScriptedAgent(_make_trend_policy(), seed=seed)


AGENTS["trend-commit"] = lambda spec: _trend_commit_agent_factory  # type: ignore[index]


@fn(kind="agent", name="trend_commit", summary="watch row 0's product one step, then commit the direction it moved", registry_name="trend-commit")
def trend_commit():
    return _trend_commit_agent_factory


# ---- and a prior-only control: never look, commit the textbook answer ----

def _make_prior_policy(answer: str = "down"):
    """Commit at once the answer a prior about chains gives — starve a step
    and its product falls — without observing anything. The pair (trend,
    prior) shows what the harness is for: two scripted controls, one right
    for the wrong reason, one wrong for a plausible one, each against idle."""

    def policy(observation: Observation, seed: Seed):
        del observation, seed
        return Commit(answer=Answer(value=answer, kind="node_id")), ()

    return policy


def _prior_commit_agent_factory(seed: Seed, dials: Any):
    del dials
    return ScriptedAgent(_make_prior_policy(), seed=seed)


AGENTS["prior-commit"] = lambda spec: _prior_commit_agent_factory  # type: ignore[index]


@fn(kind="agent", name="prior_commit", summary="never look; commit the prior that a starved step's product falls", registry_name="prior-commit")
def prior_commit():
    return _prior_commit_agent_factory


@fn(kind="drafter", summary="the grid as a drafter: (world, task) with complexity and n_nodes bound")
def grid(*, complexity: int = 2, n_nodes: int = 3, env: Any) -> Draft:
    scope = Env.standard(seed=env.ctx.seed, trusted=True).load(HERE / "grid.yaml")
    scope.bindings["complexity"] = int(complexity)
    scope.bindings["n_nodes"] = int(n_nodes)
    return Draft(evaluate(X.name("world"), scope), evaluate(X.name("task"), scope))
