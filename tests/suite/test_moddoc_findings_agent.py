"""Module-doc pass findings on ``suite/agent.py`` and ``protocols/bio.py`` (T088)."""

from __future__ import annotations

import subprocess
import sys
import typing

import pytest

from alienbio.suite.agent import Commit, Measure, PolicyStep, ScriptedAgent, Wait
from alienbio.suite.archetypes import identify_pathway
from alienbio.suite.dist import Constant, Seed
from alienbio.suite.pipeline import build_suite
from alienbio.suite.runner import TrialError, run
from alienbio.suite.types import Answer, SuiteSpec


def _world_task():
    spec = SuiteSpec(archetype_mix=Constant(identify_pathway(pathway_length=3)))
    suite = build_suite(spec, Seed(1), n_tasks=1, distractor_count=1)
    return suite.worlds[0], suite.tasks[0]


def test_a_wait_step_list_type_checks_and_runs(tmp_path):
    """`PolicyStep` names `Wait`, so a step list holding one type-checks, and
    the runner plays it as an accepted wait."""
    assert Wait in typing.get_args(PolicyStep)
    snippet = tmp_path / "wait_steps.py"
    snippet.write_text(
        "from alienbio.suite.agent import Commit, PolicyStep, Wait\n"
        "from alienbio.suite.types import Answer\n"
        "steps: tuple[PolicyStep, ...] = (\n"
        "    Wait(duration=1.0),\n"
        "    Commit(answer=Answer(value=[], kind='ordered_path')),\n"
        ")\n"
    )
    result = subprocess.run(
        [sys.executable, "-m", "pyright", "--pythonpath", sys.executable, str(snippet)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "0 errors" in result.stdout

    world, task = _world_task()
    steps: tuple[PolicyStep, ...] = (
        Wait(duration=1.0),
        Commit(answer=Answer(value=[], kind="ordered_path")),
    )
    record = run(world, task, ScriptedAgent(steps, seed=Seed(0)), {}, Seed(4))
    assert [a.kind for a in record.action_log] == ["wait", "commit"]
    assert all(a.accepted for a in record.action_log)


def test_exhaustion_without_a_commit_names_the_turn():
    """A list with no Commit and a longer `max_turns` exhausts on the turn
    after its last step; the message says so rather than citing a Commit."""
    world, task = _world_task()
    mol = next(iter(world.chemistry.molecules))
    agent = ScriptedAgent((Measure(probe=mol), Measure(probe=mol)), seed=Seed(0))
    with pytest.raises(TrialError) as info:
        run(world, task, agent, {}, Seed(4), max_turns=5)
    cause = info.value.__cause__
    assert isinstance(cause, RuntimeError)
    message = str(cause)
    assert "terminal Commit" not in message
    assert "no Commit" in message
    assert "all 2 steps" in message
    assert "turn 2" in message


def test_exhaustion_after_a_commit_still_says_commit():
    agent = ScriptedAgent((Commit(answer=Answer(value=[], kind="json")),), seed=Seed(0))
    agent.act(())
    with pytest.raises(RuntimeError, match=r"all 1 steps fired after its terminal Commit; .* turn 1"):
        agent.act(())


def test_suite_exports_the_agent_seams():
    import alienbio.suite as suite
    from alienbio.suite import agent

    for name in ("ActionOutcome", "SessionAgent", "ProbeAgent", "ObservationPredicate"):
        assert name in suite.__all__
        assert getattr(suite, name) is getattr(agent, name)


def test_a_float_rate_reaction_conforms_to_the_reaction_protocol():
    """`Reaction.rate` is `float` on the Protocol, matching `ReactionImpl`,
    which refuses a non-number."""
    from alienbio.bio.reaction import ReactionImpl
    from alienbio.infra.entity import MockDat
    from alienbio.protocols.bio import Reaction

    hints = typing.get_type_hints(Reaction.rate.fget)  # type: ignore[attr-defined]
    assert hints["return"] is float
    rxn = ReactionImpl("r1", rate=0.25, reactants={}, products={}, dat=MockDat("rxn/r1"))
    assert isinstance(rxn, Reaction)
    assert isinstance(rxn.rate, float)
