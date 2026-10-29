"""helpers.py for the agent loop — two example-owned session agents (one
that recovers from a rejection using its turn memory, one that never does)
beside the framework's own, and the drafter the experiment calls."""

from __future__ import annotations

import dataclasses
import inspect
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from alienbio.expr import Env, X, evaluate, fn
from alienbio.suite.agent import ActionOutcome, Commit, Intervene, Measure, ReasoningStep
from alienbio.suite.brief import TaskBrief
from alienbio.suite.dist import Seed
from alienbio.suite.experiment import AGENTS, Draft
from alienbio.suite.observation import Observation
from alienbio.suite.runner import resolve_int_dial, run
from alienbio.suite.skeleton import final_amount
from alienbio.suite.types import Answer
from alienbio.suite.verify import SimConfig, simulate

HERE = Path(__file__).resolve().parent


@fn(summary="the id of the molecule whose pool is `name`")
def molecule_id(world, name: str) -> str:
    matches = [m for m in world.chemistry.molecules if m == name or m.endswith(f"/{name}")]
    if len(matches) != 1:
        raise ValueError(f"molecule_id: {name!r} matches {matches}")
    return matches[0]


class _RetryCommitAgent:
    """``retry-commit``: the session loop working as intended. Turn 0 names a
    probe that does not exist — the runner rejects it AS DATA and says so via
    ``notice`` — so turn 1 reads the brief's affordances instead (turn
    memory), measures a real probe, acts on the first declared lever, and
    commits. One illegal action, then recovery: rejection-as-data as a
    NOTICED, correctable event, not a crash."""

    def __init__(self, seed: Seed) -> None:
        self.seed = seed
        self._brief: TaskBrief | None = None
        self._rejected = False
        self._step = 0

    def begin(self, brief: TaskBrief) -> None:
        self._brief = brief

    def notice(self, outcome: ActionOutcome) -> None:
        if not outcome.accepted:
            self._rejected = True

    def act(self, observation: Observation) -> tuple[Any, tuple[ReasoningStep, ...]]:
        del observation
        assert self._brief is not None
        self._step += 1
        if self._step == 1:
            return Measure(probe="no-such-probe"), (ReasoningStep(kind="policy", content="guessing a probe name", refs=()),)
        if self._step == 2 and self._rejected:
            probe = self._brief.affordances.probes[0]
            return Measure(probe=probe), (ReasoningStep(kind="policy", content="rejected; re-reading the brief", refs=(probe,)),)
        if self._step == 3:
            lever = self._brief.affordances.levers[0]
            return Intervene(lever=lever, value=2.0), (ReasoningStep(kind="policy", content=f"acting on {lever}", refs=(lever,)),)
        return Commit(answer=Answer(value=[], kind="json")), (ReasoningStep(kind="policy", content="committing", refs=()),)


class _ClumsyCommitAgent:
    """``clumsy-commit``: the loop's failure containment. Every turn names a
    lever that does not exist; the runner rejects each AS DATA until
    ``illegal_action_limit`` stops the trial — one confused agent burns its
    own trial and nothing else."""

    def __init__(self, seed: Seed) -> None:
        self.seed = seed

    def begin(self, brief: TaskBrief) -> None:
        del brief

    def notice(self, outcome: ActionOutcome) -> None:
        del outcome

    def act(self, observation: Observation) -> tuple[Any, tuple[ReasoningStep, ...]]:
        del observation
        return Intervene(lever="no-such-lever", value=1.0), (ReasoningStep(kind="policy", content="pulling a lever that is not there", refs=()),)


def _retry_commit_agent_factory(seed: Seed, dials: Any):
    del dials
    return _RetryCommitAgent(seed)


def _clumsy_commit_agent_factory(seed: Seed, dials: Any):
    del dials
    return _ClumsyCommitAgent(seed)


AGENTS["retry-commit"] = lambda spec: _retry_commit_agent_factory  # type: ignore[index]
AGENTS["clumsy-commit"] = lambda spec: _clumsy_commit_agent_factory  # type: ignore[index]


@fn(kind="agent", name="retry_commit", summary="one bad probe, then recover through the brief and commit", registry_name="retry-commit")
def retry_commit():
    return _retry_commit_agent_factory


@fn(kind="agent", name="clumsy_commit", summary="an unknown lever every turn, until the illegal-action limit stops the trial", registry_name="clumsy-commit")
def clumsy_commit():
    return _clumsy_commit_agent_factory


#: The passive gate's margin (W1's shape): the do-nothing reach of the target
#: at the scored horizon must sit at least this fraction below the goal.
PASSIVE_MARGIN = 0.5


@fn(summary="the target's do-nothing reach over `sim`; refuses a world an idle agent clears")
def passive_gate(world, target_id: str, goal: float, sim: SimConfig) -> float:
    """Integrate the untouched world over ``sim`` and return the target's
    reach; refuse when it sits within :data:`PASSIVE_MARGIN` of ``goal`` (the
    pressure family's passive gate, here on a neutral world)."""
    passive = final_amount(simulate(world, sim), target_id)
    if passive >= float(goal) * (1.0 - PASSIVE_MARGIN):
        raise ValueError(
            f"agent loop passive gate: do-nothing reaches {target_id}={passive:.4f} at {sim.steps * sim.dt:g} s, "
            f"within {PASSIVE_MARGIN:g} of the goal {float(goal):g} — an idle agent would clear it; raise the "
            "drain or lower the feed"
        )
    return passive


@fn(kind="drafter", summary="the agent-loop world as a drafter: (world, task), behind the passive gate")
def loop_world(
    *,
    max_turns: int | None = None,
    sim_steps: int | None = None,
    sim_dt: float | None = None,
    env: Any,
) -> Draft:
    """The chain and its outcome task, scored at the episode's horizon and
    refused when a do-nothing agent clears it (T096).

    The horizon is ``max_turns`` x ``sim_steps`` x ``sim_dt`` as dialed, else
    the runner's defaults; the task declares ``setup["score_horizon_turns"]``
    so a commit before it is integrated passively to the horizon (the
    ``intervene`` drafter's T091 A1 shape) — the act is graded, not the
    commit time. The gate integrates the untouched world over that horizon
    and refuses it when the target's reach is within :data:`PASSIVE_MARGIN`
    of the goal; the passive reach rides ``setup["oracle"]["loop"]``."""
    run_defaults = inspect.signature(run).parameters
    default_sim: SimConfig = run_defaults["sim_cfg"].default
    horizon = {"max_turns": max_turns, "sim_steps": sim_steps}
    turns = resolve_int_dial(horizon, "max_turns", run_defaults["max_turns"].default)
    steps = resolve_int_dial(horizon, "sim_steps", default_sim.steps)
    dt = float(sim_dt) if sim_dt is not None else default_sim.dt
    scope = Env.standard(seed=env.ctx.seed, trusted=True).load(HERE / "agent_loop.yaml")
    world, task = evaluate(X.name("world"), scope), evaluate(X.name("task"), scope)
    target_id = molecule_id(world, "C")
    goal = float(evaluate(X.name("target_level"), scope))
    passive = passive_gate(world, target_id, goal, SimConfig(dt=dt, steps=turns * steps, sample_every=steps))
    setup = dict(task.setup) if isinstance(task.setup, Mapping) else {}
    oracle = {**dict(setup.get("oracle") or {}), "loop": {"target": target_id, "goal": goal, "passive": passive, "scored_at_s": turns * steps * dt}}
    task = dataclasses.replace(task, setup={**setup, "score_horizon_turns": turns, "oracle": oracle})
    return Draft(world, task)
