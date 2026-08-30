"""Acceptance tests for ``suite.runner.run`` — the agent turn loop (F021).

Every test drives a ``ScriptedAgent`` (or a bare ``Callable`` policy) against
a real ``build_suite`` task/world — no LLM, no network, no API key.
"""

from __future__ import annotations

import pytest

import dataclasses
import re

from alienbio.suite.agent import (
    Commit,
    Intervene,
    Measure,
    ReasoningStep,
    ScriptedAgent,
)
from alienbio.suite.archetypes import identify_pathway
from alienbio.suite.brief import build_brief, render_brief
from alienbio.suite.dist import Constant, Seed
from alienbio.suite.observation import full_observation, narrow_observation
from alienbio.suite.pipeline import build_suite
from alienbio.suite.runner import Budget, run
from alienbio.suite.trial import TrialRecord, condition_key
from alienbio.suite.types import Answer, AnswerObjective, SuiteSpec
from alienbio.suite.verify import SimConfig, simulate


def _identify_pathway_suite(pathway_length: int = 3, n_tasks: int = 1, seed_val: int = 1):
    arch = identify_pathway(pathway_length=pathway_length)
    spec = SuiteSpec(archetype_mix=Constant(arch))
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


def test_never_committing_agent_stops_at_budget_exhausted():
    suite = _identify_pathway_suite()
    world, task = suite.worlds[0], suite.tasks[0]
    mol = next(iter(world.chemistry.molecules))

    def policy(observation, seed):
        del observation, seed
        return Measure(probe=mol), (ReasoningStep(kind="policy", content="measuring"),)

    agent = ScriptedAgent(policy, seed=Seed(0))
    record = run(world, task, agent, {"budget": 3.0}, Seed(5), max_turns=100)

    # F023 (M32.1): the Budget abstraction renames the F021 "budget_exceeded"
    # terminal reason to "budget_exhausted"; the cost-weighted accounting
    # itself (Measure's default cost is 1.0/turn; budget=3.0 stops after 3
    # turns) is unchanged.
    assert record.terminal_reason == "budget_exhausted"
    assert len(record.action_log) == 3
    assert all(a.kind == "measure" for a in record.action_log)
    assert record.budget == 3.0
    assert record.spent == 3.0
    assert record.remaining == 0.0


def test_committing_agent_stops_at_committed_not_budget():
    suite = _identify_pathway_suite()
    world, task = suite.worlds[0], suite.tasks[0]
    assert isinstance(task.objective, AnswerObjective)

    agent = ScriptedAgent(_key_commit_policy(task.objective.key.value), seed=Seed(0))
    record = run(world, task, agent, {"budget": 1000.0}, Seed(6))

    assert record.terminal_reason == "committed"
    assert record.objective_score == pytest.approx(1.0)


def test_budget_ladder_degrades_turns_monotonically():
    """F023 (M32.1): the graded ladder ({unlimited, 20, 12, 8, 4}) is a real
    degradation driver — a smaller budget level stops the trial strictly
    sooner (fewer turns/actions)."""
    suite = _identify_pathway_suite()
    world, task = suite.worlds[0], suite.tasks[0]
    mol = next(iter(world.chemistry.molecules))

    def policy(observation, seed):
        del observation, seed
        return Measure(probe=mol), ()

    turn_counts = []
    for level in ("20", "12", "8", "4"):
        agent = ScriptedAgent(policy, seed=Seed(0))
        record = run(world, task, agent, {"budget": level}, Seed(5), max_turns=1000)
        assert record.terminal_reason == "budget_exhausted"
        turn_counts.append(len(record.action_log))

    assert turn_counts == sorted(turn_counts, reverse=True)
    assert len(set(turn_counts)) == len(turn_counts)  # strictly decreasing


def test_budget_unlimited_runs_to_natural_termination():
    """The ``"unlimited"`` ladder level never stops the trial on budget — it
    runs to whatever its own natural terminal event is (here, ``Commit``)."""
    suite = _identify_pathway_suite()
    world, task = suite.worlds[0], suite.tasks[0]
    assert isinstance(task.objective, AnswerObjective)
    agent = ScriptedAgent(_key_commit_policy(task.objective.key.value), seed=Seed(0))

    record = run(world, task, agent, {"budget": "unlimited"}, Seed(7))

    assert record.terminal_reason == "committed"
    assert record.budget == float("inf")
    assert record.remaining == float("inf")


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


class _LeakyAgent:
    """A test double that 'sends' prompts: an Agent exposing prompt_texts."""

    def __init__(self, leak: str, mol: str):
        self.prompt_texts = (f"system prompt mentions {leak} here",)
        self._mol = mol

    def act(self, observation):
        return Commit(answer=Answer(value=[], kind="json")), ()


def test_taint_audit_fails_visibly_when_a_prompt_names_a_hidden_id():
    # M46.10: hide half the molecules; a prompt that names a hidden one is a taint hit.
    from alienbio.suite.runner import TaintError

    suite = _identify_pathway_suite()
    world, task = suite.worlds[0], suite.tasks[0]
    dials = {"observability": 0.5}
    probe = run(world, task, ScriptedAgent(lambda o, s: (Commit(answer=Answer(value=[], kind="json")), ()), seed=Seed(0)), dials, Seed(3))
    assert probe.brief is not None
    hidden = sorted(set(world.chemistry.molecules) - set(probe.brief.affordances.probes))
    assert hidden, "fixture must hide at least one molecule"
    question_tokens = {t for t in str(task.question.structured).split() if t}
    leak = next((h for h in hidden if h not in str(task.question.structured)), None)
    assert leak is not None
    del question_tokens

    with pytest.raises(TaintError) as excinfo:
        run(world, task, _LeakyAgent(leak, hidden[0]), dials, Seed(3))
    assert leak in excinfo.value.record.taint_hits
    assert leak in str(excinfo.value)

    # A prompt naming only VISIBLE ids audits clean.
    clean = _LeakyAgent(probe.brief.affordances.probes[0], hidden[0])
    record = run(world, task, clean, dials, Seed(3))
    assert record.taint_hits == ()


def test_taint_audit_ignores_key_tokens_the_question_itself_names():
    # identify_pathway's question states the pathway endpoints, which the key
    # also contains — naming them is not a leak.
    suite = _identify_pathway_suite()
    world, task = suite.worlds[0], suite.tasks[0]
    assert isinstance(task.objective, AnswerObjective)
    endpoints = [t for t in task.objective.key.value if t in str(task.question.structured)]
    assert endpoints
    agent = _LeakyAgent(endpoints[0], endpoints[0])
    record = run(world, task, agent, {}, Seed(3))
    assert record.taint_hits == ()
    # ...and an interior key node the question does not name is NOT a leak
    # either while it is a visible probe: under full observability the turn-0
    # observation the agent is handed already names it (the first paid trial,
    # 2026-08-29, tripped on exactly this). It becomes a leak only when the
    # observability dial hides it — the case the hidden-id test above covers.
    interior = [t for t in task.objective.key.value if t not in str(task.question.structured)]
    assert interior
    assert interior[0] in record.brief.affordances.probes
    record = run(world, task, _LeakyAgent(interior[0], interior[0]), {}, Seed(3))
    assert record.taint_hits == ()


def test_null_answer_commit_scores_zero_instead_of_crashing_the_grader():
    # The abort sentinel Answer(value=None) must land as a scored record: the
    # ordered_path grader would otherwise raise TypeError on list(None).
    suite = _identify_pathway_suite()
    world, task = suite.worlds[0], suite.tasks[0]
    assert isinstance(task.objective, AnswerObjective)

    def policy(observation, seed):
        del observation, seed
        return Commit(answer=Answer(value=None, kind="json"), params={"aborted": "test"}), ()

    record = run(world, task, ScriptedAgent(policy, seed=Seed(0)), {}, Seed(9))
    assert record.terminal_reason == "committed"
    assert record.objective_score == 0.0


def test_dials_override_max_turns_and_sim_config_and_are_recorded():
    # M46.6: the episode length and physical time per turn are condition
    # parameters — a dial overrides the keyword default and the brief records it.
    suite = _identify_pathway_suite()
    world, task = suite.worlds[0], suite.tasks[0]
    mol = next(iter(world.chemistry.molecules))

    def policy(observation, seed):
        del observation, seed
        return Measure(probe=mol), ()

    dials = {"max_turns": 3, "sim_steps": 4, "sim_dt": 0.05, "sample_every": 2}
    record = run(world, task, ScriptedAgent(policy, seed=Seed(0)), dials, Seed(9), max_turns=50)

    assert record.terminal_reason == "max_turns"
    assert len(record.action_log) == 3
    assert record.brief is not None
    assert (record.brief.max_turns, record.brief.sim_steps, record.brief.sim_dt) == (3, 4, 0.05)
    # 3 turns x (4 steps / sample_every 2) samples + the initial snapshot
    assert len(record.final_timeline.times) == 1 + 3 * 2

    with pytest.raises(ValueError, match="max_turns"):
        run(world, task, ScriptedAgent(policy, seed=Seed(0)), {"max_turns": 0}, Seed(9))


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
# Illegal actions are rejected as data, not raised (M46.3)
# ═══════════════════════════════════════════════════════════════════════════


def test_measure_unknown_probe_is_recorded_not_raised():
    suite = _identify_pathway_suite()
    world, task = suite.worlds[0], suite.tasks[0]
    agent = ScriptedAgent(
        (
            Measure(probe="__not_a_molecule__"),
            Commit(answer=Answer(value=[], kind="ordered_path")),
        ),
        seed=Seed(0),
    )
    record = run(world, task, agent, {}, Seed(0))

    assert record.action_log[0].accepted is False
    assert "__not_a_molecule__" in record.action_log[0].reason
    assert record.action_log[0].destructive is False
    assert record.illegal_actions == 1
    # The trial continues: a second scripted step still runs and commits.
    assert len(record.action_log) == 2
    assert record.terminal_reason == "committed"


def test_intervene_unknown_lever_is_recorded_not_raised():
    suite = _identify_pathway_suite()
    world, task = suite.worlds[0], suite.tasks[0]
    agent = ScriptedAgent(
        (
            Intervene(lever="__nope__", value=1.0),
            Commit(answer=Answer(value=[], kind="ordered_path")),
        ),
        seed=Seed(0),
    )
    record = run(world, task, agent, {}, Seed(0))

    assert record.action_log[0].accepted is False
    assert "__nope__" in record.action_log[0].reason
    assert record.action_log[0].destructive is False
    assert record.illegal_actions == 1
    assert len(record.action_log) == 2
    assert record.terminal_reason == "committed"


def test_illegal_action_limit_stops_the_trial():
    suite = _identify_pathway_suite()
    world, task = suite.worlds[0], suite.tasks[0]
    agent = ScriptedAgent(
        tuple(Measure(probe="__nope__") for _ in range(5)), seed=Seed(0)
    )
    record = run(world, task, agent, {}, Seed(0), illegal_action_limit=2, max_turns=10)

    assert record.terminal_reason == "illegal_limit"
    assert record.illegal_actions == 2
    assert len(record.action_log) == 2
    assert all(not a.accepted for a in record.action_log)


def test_illegal_action_cost_override_charges_nothing_by_default_charges_verb_cost():
    suite = _identify_pathway_suite()
    world, task = suite.worlds[0], suite.tasks[0]

    policy = (
        Measure(probe="__nope__"),
        Commit(answer=Answer(value=[], kind="ordered_path")),
    )
    record_free = run(
        world, task, ScriptedAgent(policy, seed=Seed(0)), {}, Seed(0), illegal_action_cost=0.0
    )
    assert record_free.spent == 0.0  # Measure rejected -> illegal_action_cost=0.0 charged

    record_default = run(world, task, ScriptedAgent(policy, seed=Seed(0)), {}, Seed(0))
    assert record_default.spent == 1.0  # Measure's normal cost (1.0) still charged when rejected


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

    obs = narrow_observation(world.initial_state, {}, Seed(0))
    assert obs == full_observation(world.initial_state)


# ═══════════════════════════════════════════════════════════════════════════
# TaskBrief + SessionAgent (M46.1/M46.2)
# ═══════════════════════════════════════════════════════════════════════════


class _RecordingSessionAgent:
    """A ``SessionAgent`` test double: fires a fixed policy, records every
    ``begin``/``notice`` call it receives (structural Protocol — no inheritance
    needed for ``isinstance(agent, SessionAgent)`` to hold)."""

    def __init__(self, policy):
        self._policy = policy
        self._pos = 0
        self.begin_calls = []
        self.notice_calls = []

    def begin(self, brief):
        self.begin_calls.append(brief)

    def act(self, observation):
        del observation
        action = self._policy[self._pos]
        self._pos += 1
        return action, ()

    def notice(self, outcome):
        self.notice_calls.append(outcome)


def test_session_agent_gets_begin_once_and_notice_per_turn():
    suite = _identify_pathway_suite()
    world, task = suite.worlds[0], suite.tasks[0]
    assert isinstance(task.objective, AnswerObjective)

    policy = (
        Measure(probe="__bogus_probe__"),
        Commit(answer=Answer(value=list(task.objective.key.value), kind="ordered_path")),
    )
    agent = _RecordingSessionAgent(policy)
    record = run(world, task, agent, {}, Seed(50), max_turns=10)

    assert len(agent.begin_calls) == 1
    brief = agent.begin_calls[0]
    assert brief.question == task.question.structured
    assert brief.answer_kind == task.objective.key.kind
    assert brief.objective_kind == "answer"
    assert brief.budget_total == record.budget
    assert brief.max_turns == 10
    assert brief.sim_steps == 10  # the default SimConfig(steps=10, ...)

    assert len(agent.notice_calls) == 2
    assert agent.notice_calls[0].turn == 0
    assert agent.notice_calls[0].action == policy[0]
    assert agent.notice_calls[0].accepted is False
    assert "__bogus_probe__" in agent.notice_calls[0].reason
    assert agent.notice_calls[1].turn == 1
    assert agent.notice_calls[1].accepted is True
    assert record.brief is brief


def test_brief_taint_hidden_molecules_and_answer_value_never_leak():
    suite = _identify_pathway_suite()
    world, task = suite.worlds[0], suite.tasks[0]
    assert isinstance(task.objective, AnswerObjective)

    dials = {"observability": 0.5}
    # Seed(5) hides {"d0", "r1"} for this fixture — neither is one of the
    # question's own endpoint ids ("r0"/"r2"), so this seed can't produce the
    # legitimate (non-leak) overlap of the verbatim Question line naming a
    # node id that also happens to be hidden from measurement this turn.
    seed = Seed(5)
    agent = ScriptedAgent(
        (Commit(answer=Answer(value=[], kind="ordered_path")),), seed=Seed(0)
    )
    record = run(world, task, agent, dials, seed)
    brief = record.brief
    assert brief is not None

    full = full_observation(world.initial_state)
    narrowed = narrow_observation(world.initial_state, dials, seed.child("turn/0/observe"))
    full_ids = {mol_id for compartment in full for mol_id in compartment}
    visible_ids = {mol_id for compartment in narrowed for mol_id in compartment}
    hidden_ids = full_ids - visible_ids
    assert len(hidden_ids) >= 1, "fixture must hide >=1 molecule for this test to be meaningful"

    # Every probe the brief offers is actually visible in the turn-0 observation.
    assert set(brief.affordances.probes) == visible_ids

    rendered = render_brief(brief)
    for hidden_id in hidden_ids:
        assert re.search(rf"\b{re.escape(hidden_id)}\b", rendered) is None

    # The answer key's VALUE is never touched by build_brief — regression guard
    # with a distinguishable marker, mirroring test_llm_agent.py's taint test.
    marker = "SECRET_ANSWER_VALUE_TOKEN_XYZ"
    tainted_objective = dataclasses.replace(
        task.objective, key=Answer(value=marker, kind=task.objective.key.kind)
    )
    tainted_task = dataclasses.replace(task, objective=tainted_objective)
    tainted_first_obs = narrow_observation(world.initial_state, dials, seed.child("turn/0/observe"))
    tainted_brief = build_brief(
        tainted_task, world.chemistry, tainted_first_obs, dials, Budget(), 50, SimConfig(steps=10, sample_every=10)
    )
    assert marker not in render_brief(tainted_brief)


def test_explicit_levers_dial_restricts_affordances_and_rejects_others():
    suite = _identify_pathway_suite()
    world, task = suite.worlds[0], suite.tasks[0]
    reaction_id = next(iter(world.chemistry.reactions))
    mol = next(iter(world.chemistry.molecules))
    dials = {"levers": (reaction_id,)}

    agent = ScriptedAgent(
        (
            Intervene(lever=mol, value=1.0),
            Commit(answer=Answer(value=[], kind="ordered_path")),
        ),
        seed=Seed(0),
    )
    record = run(world, task, agent, dials, Seed(0))

    assert record.brief is not None
    assert record.brief.affordances.levers == (reaction_id,)
    assert record.action_log[0].accepted is False
    assert reaction_id in record.action_log[0].reason or mol in record.action_log[0].reason


def test_record_carries_brief_and_turn_count():
    suite = _identify_pathway_suite()
    world, task = suite.worlds[0], suite.tasks[0]
    mol = next(iter(world.chemistry.molecules))
    agent = ScriptedAgent(
        (Measure(probe=mol), Commit(answer=Answer(value=[], kind="ordered_path"))),
        seed=Seed(0),
    )
    record = run(world, task, agent, {}, Seed(0))

    assert record.brief is not None
    assert record.turns == len(record.action_log) == 2


# ═══════════════════════════════════════════════════════════════════════════
# usage / wall_time_s (M45.5)
# ═══════════════════════════════════════════════════════════════════════════


def test_scripted_run_has_no_usage_and_positive_wall_time():
    suite = _identify_pathway_suite()
    world, task = suite.worlds[0], suite.tasks[0]
    assert isinstance(task.objective, AnswerObjective)

    agent = ScriptedAgent(_key_commit_policy(task.objective.key.value), seed=Seed(0))
    record = run(world, task, agent, {}, Seed(7))

    assert record.usage is None
    assert record.wall_time_s > 0.0


class _UsageExposingAgent:
    """A test double exposing ``usage`` (like ``LLMAgent``) but never calling a model."""

    def __init__(self, usage):
        self._usage = usage

    def act(self, observation):
        del observation
        return Commit(answer=Answer(value=[], kind="ordered_path")), ()

    @property
    def usage(self):
        return self._usage


def test_agent_usage_lands_on_the_record():
    suite = _identify_pathway_suite()
    world, task = suite.worlds[0], suite.tasks[0]

    fake_usage = {"calls": 3, "input_tokens": 100, "output_tokens": 20}
    agent = _UsageExposingAgent(fake_usage)
    record = run(world, task, agent, {}, Seed(0))

    assert record.usage == fake_usage
    assert record.wall_time_s > 0.0
