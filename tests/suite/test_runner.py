"""Acceptance tests for ``suite.runner.run`` — the agent turn loop (F021).

Every test drives a ``ScriptedAgent`` (or a bare ``Callable`` policy) against
a real ``build_suite`` task/world — no LLM, no network, no API key.
"""

from __future__ import annotations

import pytest

from alienbio.suite.agent import Commit, Intervene, Measure, ReasoningStep, ScriptedAgent
from alienbio.suite.archetypes import identify_pathway
from alienbio.suite.dist import Constant, Seed
from alienbio.suite.observation import narrow_observation
from alienbio.suite.pipeline import build_suite
from alienbio.suite.runner import run
from alienbio.suite.trial import TrialRecord, condition_key
from alienbio.suite.types import Answer, AnswerObjective, SuiteSpec
from alienbio.suite.verify import SimConfig, simulate


def _identify_pathway_suite(pathway_length: int = 3, n_tasks: int = 1, seed_val: int = 1):
    arch = identify_pathway(pathway_length=pathway_length)
    spec = SuiteSpec(archetype_mix=Constant(arch), per_archetype={}, seed=0)
    return build_suite(spec, Seed(seed_val), n_tasks=n_tasks, distractor_count=1)


def _key_commit_policy(key_value):
    """A ScriptedAgent policy that commits the (correct) answer immediately."""
    return (Commit(answer=Answer(value=list(key_value), kind="ordered_path")),)


# ═══════════════════════════════════════════════════════════════════════════
# ScriptedAgent end-to-end against an existing build_suite task (acceptance gate)
# ═══════════════════════════════════════════════════════════════════════════


def test_scripted_agent_end_to_end_commits_and_grades_perfectly():
    suite = _identify_pathway_suite()
    world, task = suite.worlds[0], suite.tasks[0]
    assert isinstance(task.objective, AnswerObjective)

    agent = ScriptedAgent(_key_commit_policy(task.objective.key.value), seed=Seed(0))
    dials = {"observability": 1.0}
    record = run(world, task, agent, dials, Seed(7))

    assert isinstance(record, TrialRecord)
    assert record.task_id == task.world
    assert record.condition_key == condition_key(dials)
    assert record.terminal_reason == "committed"
    assert record.objective_score == pytest.approx(1.0)
    assert record.deliberation_trace.depth() == 1
    assert len(record.action_log) == 1
    assert record.action_log[0].kind == "commit"
    assert len(record.final_timeline.states) >= 1


def test_answer_objective_task_that_never_commits_scores_zero():
    suite = _identify_pathway_suite()
    world, task = suite.worlds[0], suite.tasks[0]
    mol = next(iter(world.chemistry.molecules))

    policy = (Measure(probe=mol), Measure(probe=mol), Measure(probe=mol))
    agent = ScriptedAgent(policy, seed=Seed(0))
    with pytest.raises(RuntimeError, match="policy exhausted"):
        run(world, task, agent, {}, Seed(1), max_turns=10)
    # A fresh agent that runs out its turns via max_turns (policy never
    # exhausted mid-run) scores 0.0 — no Commit, nothing to grade.
    agent2 = ScriptedAgent(policy, seed=Seed(0))
    record = run(world, task, agent2, {}, Seed(1), max_turns=3)
    assert record.terminal_reason == "max_turns"
    assert record.objective_score == 0.0


# ═══════════════════════════════════════════════════════════════════════════
# No-op / measure-only agent: world evolves exactly as a plain simulate() would
# ═══════════════════════════════════════════════════════════════════════════


def test_measure_only_agent_matches_plain_simulate_over_same_total_steps():
    suite = _identify_pathway_suite()
    world, task = suite.worlds[0], suite.tasks[0]
    mol = next(iter(world.chemistry.molecules))

    n_measure_turns = 3
    policy = tuple(Measure(probe=mol) for _ in range(n_measure_turns)) + (
        Commit(answer=Answer(value=[], kind="ordered_path")),
    )
    agent = ScriptedAgent(policy, seed=Seed(0))
    sim_cfg = SimConfig(steps=5, sample_every=5)

    record = run(world, task, agent, {}, Seed(3), sim_cfg=sim_cfg, max_turns=10)
    total_turns = n_measure_turns + 1  # + the Commit turn's own burst
    assert record.terminal_reason == "committed"

    baseline = simulate(
        world, SimConfig(steps=sim_cfg.steps * total_turns, sample_every=sim_cfg.steps)
    )

    got = record.final_timeline.states[-1].as_array()
    want = baseline.states[-1].as_array()
    assert (got == want).all()


def test_wait_only_agent_matches_measure_only_agent_world_evolution():
    from alienbio.suite.agent import Wait

    suite = _identify_pathway_suite()
    world, task = suite.worlds[0], suite.tasks[0]
    mol = next(iter(world.chemistry.molecules))

    measure_policy = (Measure(probe=mol), Commit(answer=Answer(value=[], kind="ordered_path")))
    wait_policy = (Wait(duration=1.0), Commit(answer=Answer(value=[], kind="ordered_path")))
    sim_cfg = SimConfig(steps=5, sample_every=5)

    r1 = run(world, task, ScriptedAgent(measure_policy, seed=Seed(0)), {}, Seed(4), sim_cfg=sim_cfg)
    r2 = run(world, task, ScriptedAgent(wait_policy, seed=Seed(0)), {}, Seed(4), sim_cfg=sim_cfg)
    assert (r1.final_timeline.states[-1].as_array() == r2.final_timeline.states[-1].as_array()).all()


# ═══════════════════════════════════════════════════════════════════════════
# Budget / commit termination
# ═══════════════════════════════════════════════════════════════════════════


def test_never_committing_agent_stops_at_budget_exceeded():
    suite = _identify_pathway_suite()
    world, task = suite.worlds[0], suite.tasks[0]
    mol = next(iter(world.chemistry.molecules))

    def policy(observation, seed):
        del observation, seed
        return Measure(probe=mol), (ReasoningStep(kind="policy", content="measuring"),)

    agent = ScriptedAgent(policy, seed=Seed(0))
    record = run(world, task, agent, {"budget": 3.0}, Seed(5), max_turns=100)

    assert record.terminal_reason == "budget_exceeded"
    # Measure's default cost is 1.0/turn; budget=3.0 stops after 3 turns.
    assert len(record.action_log) == 3
    assert all(a.kind == "measure" for a in record.action_log)


def test_committing_agent_stops_at_committed_not_budget():
    suite = _identify_pathway_suite()
    world, task = suite.worlds[0], suite.tasks[0]
    assert isinstance(task.objective, AnswerObjective)

    agent = ScriptedAgent(_key_commit_policy(task.objective.key.value), seed=Seed(0))
    record = run(world, task, agent, {"budget": 1000.0}, Seed(6))

    assert record.terminal_reason == "committed"
    assert record.objective_score == pytest.approx(1.0)


def test_max_turns_reached_without_commit_or_budget():
    suite = _identify_pathway_suite()
    world, task = suite.worlds[0], suite.tasks[0]
    mol = next(iter(world.chemistry.molecules))

    def policy(observation, seed):
        del observation, seed
        return Measure(probe=mol), ()

    agent = ScriptedAgent(policy, seed=Seed(0))
    record = run(world, task, agent, {}, Seed(9), max_turns=4)  # unlimited budget

    assert record.terminal_reason == "max_turns"
    assert len(record.action_log) == 4


# ═══════════════════════════════════════════════════════════════════════════
# Determinism
# ═══════════════════════════════════════════════════════════════════════════


def test_run_is_deterministic_same_inputs_same_record():
    suite = _identify_pathway_suite()
    world, task = suite.worlds[0], suite.tasks[0]
    mol = next(iter(world.chemistry.molecules))
    original_concentration = world.initial_state.get(0, list(world.chemistry.molecules).index(mol))

    policy = (
        Measure(probe=mol),
        Intervene(lever=mol, value=42.0),
        Commit(answer=Answer(value=[], kind="ordered_path")),
    )
    dials = {"observability": 0.8, "observation_noise": 0.1, "budget": 1000.0}

    r1 = run(world, task, ScriptedAgent(policy, seed=Seed(11)), dials, Seed(21))
    r2 = run(world, task, ScriptedAgent(policy, seed=Seed(11)), dials, Seed(21))

    assert r1.action_log == r2.action_log
    assert r1.objective_score == r2.objective_score
    assert r1.terminal_reason == r2.terminal_reason
    assert [s.as_array().tolist() for s in r1.final_timeline.states] == [
        s.as_array().tolist() for s in r2.final_timeline.states
    ]

    # The Intervene(lever=mol, ...) concentration edit never leaked back into
    # the original world's initial_state across either call — each `run` only
    # ever mutates fresh, per-call copies (this is WHY two calls agree).
    mol_idx = list(world.chemistry.molecules).index(mol)
    assert world.initial_state.get(0, mol_idx) == original_concentration


# ═══════════════════════════════════════════════════════════════════════════
# Fail-visibly: unknown probe / lever
# ═══════════════════════════════════════════════════════════════════════════


def test_measure_unknown_probe_raises():
    suite = _identify_pathway_suite()
    world, task = suite.worlds[0], suite.tasks[0]
    agent = ScriptedAgent((Measure(probe="__not_a_molecule__"),), seed=Seed(0))
    with pytest.raises(ValueError, match="unknown probe"):
        run(world, task, agent, {}, Seed(0))


def test_intervene_unknown_lever_raises():
    suite = _identify_pathway_suite()
    world, task = suite.worlds[0], suite.tasks[0]
    agent = ScriptedAgent((Intervene(lever="__nope__", value=1.0),), seed=Seed(0))
    with pytest.raises(ValueError, match="unknown lever"):
        run(world, task, agent, {}, Seed(0))


# ═══════════════════════════════════════════════════════════════════════════
# Intervene: rate lever actually changes the dynamics
# ═══════════════════════════════════════════════════════════════════════════


def test_intervene_rate_lever_zeroes_out_reaction():
    suite = _identify_pathway_suite()
    world, task = suite.worlds[0], suite.tasks[0]
    reaction_id = next(iter(world.chemistry.reactions))
    sim_cfg = SimConfig(steps=5, sample_every=5)

    policy = (
        Intervene(lever=reaction_id, value=0.0),
        Commit(answer=Answer(value=[], kind="ordered_path")),
    )
    record = run(world, task, ScriptedAgent(policy, seed=Seed(0)), {}, Seed(2), sim_cfg=sim_cfg)

    # A rate of 0.0 freezes every concentration exactly at the initial state
    # (nothing left to react with a zeroed rate).
    got = record.final_timeline.states[-1].as_array()
    want = world.initial_state.as_array()
    assert (got == want).all()

    # The original world's chemistry was never mutated by the Intervene.
    assert world.chemistry.reactions[reaction_id].rate != 0.0


# ═══════════════════════════════════════════════════════════════════════════
# Shared narrower helper: observability + noise are seed-deterministic
# ═══════════════════════════════════════════════════════════════════════════


def test_narrow_observation_deterministic_same_seed():
    suite = _identify_pathway_suite()
    world = suite.worlds[0]
    dials = {"observability": 0.5, "observation_noise": 0.2}

    o1 = narrow_observation(world.initial_state, dials, Seed(42))
    o2 = narrow_observation(world.initial_state, dials, Seed(42))
    assert o1 == o2


def test_narrow_observation_differs_across_seeds():
    suite = _identify_pathway_suite()
    world = suite.worlds[0]
    dials = {"observability": 0.5, "observation_noise": 0.2}

    o1 = narrow_observation(world.initial_state, dials, Seed(1))
    o2 = narrow_observation(world.initial_state, dials, Seed(2))
    assert o1 != o2


def test_narrow_observation_unset_dials_is_full_ground_truth():
    suite = _identify_pathway_suite()
    world = suite.worlds[0]
    from alienbio.suite.observation import full_observation

    obs = narrow_observation(world.initial_state, {}, Seed(0))
    assert obs == full_observation(world.initial_state)
