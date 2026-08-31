"""helpers.py for the agent loop — two example-owned session agents (one
that recovers from a rejection using its turn memory, one that never does)
beside the framework's own, and the drafter the experiment calls."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from alienbio.expr import Env, X, evaluate, fn
from alienbio.suite.agent import ActionOutcome, Commit, Intervene, Measure, ReasoningStep
from alienbio.suite.brief import TaskBrief
from alienbio.suite.dist import Seed
from alienbio.suite.experiment import AGENTS, Draft
from alienbio.suite.observation import Observation
from alienbio.suite.types import Answer

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


@fn(kind="drafter", summary="the agent-loop world as a drafter: (world, task)")
def loop_world(*, env: Any) -> Draft:
    scope = Env.standard(seed=env.ctx.seed, trusted=True).load(HERE / "agent_loop.yaml")
    return Draft(evaluate(X.name("world"), scope), evaluate(X.name("task"), scope))
