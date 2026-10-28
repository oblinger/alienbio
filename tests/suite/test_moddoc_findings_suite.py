"""Defects the suite module-doc writers reproduced with the source open.

Each section pins one finding: it failed before its fix and passes after.

A. ``compact_budget`` reached the summarizer only as model-visible text
   (``budget_tokens``); the provider fn's ``max_tokens`` seam never saw it,
   so the bound the compact-turn ceiling pre-check assumes was not enforced.
B. ``_action_cost`` honoured an agent-supplied ``params["cost"]``: a model
   emitting ``cost: 0`` (or negative) beat the budget, and a non-numeric one
   raised inside the loop as a ``TrialError``.
C. A trial that died mid-episode was never taint-audited: a secret the agent
   had already been sent landed with ``taint_hits=()`` under the crash's name.
D. ``surface_brief`` left ``protocol`` (and the auditor / monitoring lines)
   structural though ``render_brief`` prints them: an id in a ``protocol`` dial
   reached the model unrenamed and the audit refused only after the spend.
E. An id followed by ``.word`` (``root/x_in.rate``) was not a whole token, so
   ``surface_text`` left it structural AND the taint audit missed it.
F. ``constitution=""`` counted as present for ``bury_commitment`` (padding
   built and stored, never shown); and ``brief_defaults`` merged after the
   control surface was resolved, so a drafter-default lever was never read.
G. An action of an unknown type raised ``ValueError`` inside the loop and
   surfaced as a ``TrialError`` instead of rejection-as-data; ``token_pattern``
   was missing from ``naming.__all__``.
H. A rate ``Intervene`` on a reaction carrying a compiled ``rate_law`` rebuilt
   it with ``rate=setpoint`` and dropped the law, silently turning it into
   mass action at the setpoint; now the runner rejects it as data and
   ``build_brief`` refuses such a declared lever.
"""

from __future__ import annotations

import dataclasses

import pytest

from alienbio.suite.agent import Measure, ReasoningStep, ScriptedAgent, Wait
from alienbio.suite.archetypes import identify_pathway
from alienbio.suite.brief import render_brief
from alienbio.suite.dist import Constant, Seed
from alienbio.suite.drafters import DRAFTERS
from alienbio.suite.llm_agent import (
    OUTPUT_BUDGET_KEY,
    LLMAgent,
    is_compact_context,
    pop_output_budget,
)
from alienbio.suite.naming import NameMap, surface_brief, token_pattern
from alienbio.suite.pipeline import build_suite
from alienbio.suite import runner as runner_mod
from alienbio.suite.runner import TaintError, TrialError, run
from alienbio.suite.types import SuiteSpec


P1_LEVERS = ["root/uptake_route_in", "root/uptake_neutral_in"]


def _p1_world(seed: int = 5, **extra):
    dials = {"variant": "commitment_no_coupling", "levers": list(P1_LEVERS), **extra}
    world, task = DRAFTERS["phase1_pressure"](Seed(seed).child("d"), dials)
    return world, task, dials


# A ---------------------------------------------------------------------------


@pytest.mark.parametrize("max_tokens", [None, 300])
def test_compact_budget_rides_the_output_budget_seam(max_tokens):
    calls: list[tuple[bool, object]] = []

    def llm_fn(directive, context, seed):
        budget, stripped = pop_output_budget(context)
        calls.append((is_compact_context(stripped), budget))
        if is_compact_context(stripped):
            return "summary"
        return {"type": "wait", "duration": 1.0}

    world, task, dials = _p1_world()
    agent = LLMAgent(
        llm_fn, Seed(5).child("llm"), memory="full", compact_at=2,
        compact_budget=77, max_tokens=max_tokens,
    )
    record = run(world, task, agent, dials, Seed(5).child("r"), max_turns=4)
    assert record.compaction is not None
    compact = [b for is_c, b in calls if is_c]
    main = [b for is_c, b in calls if not is_c]
    assert compact == [77]
    assert main and all(b == max_tokens for b in main)
    # The model-facing prompt never carries the seam key.
    assert not any(f'"{OUTPUT_BUDGET_KEY}"' in t for t in agent.prompt_texts)


# B ---------------------------------------------------------------------------


def _pathway_world():
    spec = SuiteSpec(archetype_mix=Constant(identify_pathway(pathway_length=3)))
    suite = build_suite(spec, Seed(1), n_tasks=1, distractor_count=1)
    return suite.worlds[0], suite.tasks[0]


@pytest.mark.parametrize("cost", [0, -100.0, 0.25, "free", None])
def test_agent_supplied_cost_does_not_buy_budget(cost):
    world, task = _pathway_world()
    mol = next(iter(world.chemistry.molecules))

    def policy(observation, seed):
        del observation, seed
        return Measure(probe=mol, params={"cost": cost}), (ReasoningStep(kind="policy", content="m"),)

    record = run(world, task, ScriptedAgent(policy, seed=Seed(0)), {"budget": 3.0}, Seed(5), max_turns=20)
    assert record.terminal_reason == "budget_exhausted"
    assert record.spent == 3.0
    assert len(record.action_log) == 3
    assert all(a.accepted for a in record.action_log)
    assert all("cost" in a.reason and "ignored" in a.reason for a in record.action_log)


def test_no_cost_key_leaves_the_reason_empty():
    world, task = _pathway_world()
    mol = next(iter(world.chemistry.molecules))

    def policy(observation, seed):
        del observation, seed
        return Measure(probe=mol), ()

    record = run(world, task, ScriptedAgent(policy, seed=Seed(0)), {"budget": 2.0}, Seed(5), max_turns=20)
    assert [a.reason for a in record.action_log] == ["", ""]


# C ---------------------------------------------------------------------------


class _LeakThenCrash:
    """Sends a prompt naming a hidden reaction id on turn 0, crashes on turn 1."""

    def __init__(self, leak: str) -> None:
        self._leak = leak
        self._texts: list[str] = []

    @property
    def prompt_texts(self):
        return tuple(self._texts)

    def act(self, observation):
        if self._texts:
            raise RuntimeError("provider 500")
        self._texts.append(f"the world contains {self._leak} somewhere")
        return Wait(duration=1.0), ()


def test_a_crashed_trial_is_still_taint_audited():
    world, task, dials = _p1_world()
    leak = next(r for r in world.chemistry.reactions if r not in P1_LEVERS)
    with pytest.raises(TaintError) as info:
        run(world, task, _LeakThenCrash(leak), dials, Seed(5), max_turns=5)
    assert info.value.record.taint_hits == (leak,)
    assert info.value.record.terminal_reason == "error"
    assert isinstance(info.value.__cause__, RuntimeError)


def test_a_clean_crashed_trial_stays_a_trial_error():
    world, task = _pathway_world()
    with pytest.raises(TrialError) as info:
        run(world, task, _LeakThenCrash("nothing-secret-here"), {}, Seed(5), max_turns=5)
    assert info.value.record.taint_hits == ()


def test_an_audit_failure_on_the_partial_record_leaves_the_trial_error(monkeypatch):
    world, task, dials = _p1_world()
    leak = next(r for r in world.chemistry.reactions if r not in P1_LEVERS)

    def broken(*a, **k):
        raise ValueError("audit broke")

    monkeypatch.setattr(runner_mod, "audit_prompts", broken)
    with pytest.raises(TrialError) as info:
        run(world, task, _LeakThenCrash(leak), dials, Seed(5), max_turns=5)
    assert isinstance(info.value.cause, RuntimeError)
    assert any("audit broke" in n for n in getattr(info.value, "__notes__", []))


# D ---------------------------------------------------------------------------


def test_protocol_reaches_the_agent_in_surface_names():
    world, task, dials = _p1_world()
    leak = P1_LEVERS[0]
    dials = {**dials, "protocol": f"First check {leak}, then decide.", "opaque_names": True}
    systems: list[str] = []

    def llm_fn(directive, context, seed):
        systems.append(directive)
        return {"type": "wait", "duration": 1.0}

    agent = LLMAgent(llm_fn, Seed(5).child("llm"), memory="full")
    record = run(world, task, agent, dials, Seed(5).child("r"), max_turns=2)
    assert record.taint_hits == ()
    assert systems and all(leak not in s for s in systems)
    assert any(f"Protocol: First check {record.name_map[leak]}, then decide." in s for s in systems)


def test_surface_brief_covers_every_printed_text_field():
    world, task, dials = _p1_world()
    agent = ScriptedAgent(lambda obs, sd: (Wait(duration=1.0), ()), Seed(0))
    brief = run(world, task, agent, dials, Seed(5).child("r"), max_turns=1).brief
    nm = NameMap.of({"root/secret_pool": "m99"})
    text = "watch root/secret_pool closely"
    brief = dataclasses.replace(
        brief, protocol=text, monitor=text, monitoring=text, context_padding=text,
        constitution="keep root/secret_pool low",
    )
    rendered = render_brief(surface_brief(brief, nm))
    assert "root/secret_pool" not in rendered
    assert rendered.count("m99") == 5


# E ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text, surfaced",
    [
        ("raise root/x_in.rate now", "raise m01.rate now"),
        ("see rate.root/x_in", "see rate.m01"),
        ("root/x_in.", "m01."),
    ],
)
def test_an_id_beside_a_dotted_word_is_surfaced(text, surfaced):
    assert NameMap.of({"root/x_in": "m01"}).surface_text(text) == surfaced


def test_an_id_beside_a_dotted_word_is_audited():
    assert token_pattern("root/x_in").search("raise root/x_in.rate now")
    assert token_pattern("root/x_in").search("see rate.root/x_in")
    assert not token_pattern("root/x_in").search("root/x_in_b")
    assert not token_pattern("m01").search("xm01")


def test_a_dotted_leak_in_a_prompt_is_a_taint_hit():
    world, task, dials = _p1_world()
    leak = next(r for r in world.chemistry.reactions if r not in P1_LEVERS)
    with pytest.raises(TaintError) as info:
        run(world, task, _LeakThenCrash(f"{leak}.rate"), dials, Seed(5), max_turns=5)
    assert leak in info.value.record.taint_hits


# F ---------------------------------------------------------------------------


def _with_defaults(task, defaults):
    return dataclasses.replace(task, setup={**task.setup, "brief_defaults": defaults})


@pytest.mark.parametrize("constitution", [None, ""])
def test_bury_commitment_refuses_an_empty_constitution(constitution):
    world, task, dials = _p1_world()
    dials = {**dials, "bury_commitment": 50}
    if constitution is not None:
        dials["constitution"] = constitution
    with pytest.raises(ValueError, match="needs a constitution to bury"):
        run(world, task, ScriptedAgent((Wait(duration=1.0),), Seed(0)), dials, Seed(5), max_turns=1)


def test_constitution_in_history_refuses_an_empty_constitution():
    world, task, dials = _p1_world()
    dials = {**dials, "constitution_in_history": True, "constitution": ""}
    with pytest.raises(ValueError, match="needs a constitution to displace"):
        run(world, task, ScriptedAgent((Wait(duration=1.0),), Seed(0)), dials, Seed(5), max_turns=1)


def _wait_agent():
    return ScriptedAgent(lambda obs, sd: (Wait(duration=1.0), ()), Seed(0))


def test_a_drafter_default_lever_is_the_control_surface():
    world, task, dials = _p1_world()
    dials = {k: v for k, v in dials.items() if k != "levers"}
    task = _with_defaults(task, {"levers": [{"id": P1_LEVERS[0], "max_rate": 3}]})
    brief = run(world, task, _wait_agent(), dials, Seed(5), max_turns=1).brief
    assert brief.affordances.levers == (P1_LEVERS[0],)
    assert brief.affordances.max_rates == {P1_LEVERS[0]: 3.0}


def test_an_explicit_lever_dial_still_beats_the_default():
    world, task, dials = _p1_world()
    task = _with_defaults(task, {"levers": [P1_LEVERS[0]]})
    brief = run(world, task, _wait_agent(), dials, Seed(5), max_turns=1).brief
    assert brief.affordances.levers == tuple(P1_LEVERS)


def test_a_drafter_default_lever_on_the_readout_is_refused():
    world, task, dials = _p1_world()
    target = task.question.structured["target"]
    dials = {k: v for k, v in dials.items() if k != "levers"}
    task = _with_defaults(task, {"levers": [target]})
    with pytest.raises(ValueError, match="readout molecule"):
        run(world, task, _wait_agent(), dials, Seed(5), max_turns=1)


def test_a_drafter_default_lever_on_a_hidden_pool_is_refused():
    world, task, dials = _p1_world(variant="coupling_unobservable")
    hidden = task.setup["hidden_ids"][0]
    dials = {k: v for k, v in dials.items() if k not in ("levers", "variant")}
    task = _with_defaults(task, {"levers": [hidden]})
    # The hidden pool is also this variant's tracked readout, so the readout
    # refusal (checked first) fires; either way the default was read.
    with pytest.raises(ValueError, match="structurally hidden|readout molecule"):
        run(world, task, _wait_agent(), dials, Seed(5), max_turns=1)


# G ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class _Dance:
    params: dict = dataclasses.field(default_factory=dict)


@pytest.mark.parametrize("illegal_cost", [None, 2.0])
def test_an_unknown_action_type_is_rejected_as_data(illegal_cost):
    world, task = _pathway_world()
    agent = ScriptedAgent(lambda obs, sd: (_Dance(), ()), Seed(0))
    kwargs = {} if illegal_cost is None else {"illegal_action_cost": illegal_cost}
    record = run(world, task, agent, {}, Seed(5), max_turns=4, illegal_action_limit=2, **kwargs)
    assert record.terminal_reason == "illegal_limit"
    assert record.illegal_actions == 2
    assert [a.accepted for a in record.action_log] == [False, False]
    assert all("unknown action type" in a.reason for a in record.action_log)
    assert record.spent == (0.0 if illegal_cost is None else 2 * illegal_cost)


def test_token_pattern_is_exported():
    import alienbio.suite.naming as naming

    assert "token_pattern" in naming.__all__


# H ---------------------------------------------------------------------------


def _with_law(world, reaction_id):
    from alienbio.bio.chemistry import ChemistryImpl
    from alienbio.bio.rate_expr import const, to_json
    from alienbio.bio.reaction import ReactionImpl
    from alienbio.bio.world import WorldImpl
    from alienbio.infra.entity import MockDat

    chem = world.chemistry
    old = chem.reactions[reaction_id]
    reactions = dict(chem.reactions)
    reactions[reaction_id] = ReactionImpl(
        reaction_id, reactants=old.reactants, products=old.products,
        modifiers=old.modifiers, rate=old.rate, rate_law=to_json(const(2.0)),
        dat=MockDat(f"rxn/{reaction_id}"),
    )
    new_chem = ChemistryImpl(
        chem.local_name, atoms=chem.atoms, molecules=chem.molecules,
        reactions=reactions, dat=MockDat(f"chem/{chem.local_name}"),
    )
    return WorldImpl(new_chem, world.compartments, flows=world.flows, population_laws=world.population_laws)


def test_a_rate_intervene_on_a_rate_law_reaction_is_rejected():
    from alienbio.suite.agent import Intervene

    world, task = _pathway_world()
    rxn = next(iter(world.chemistry.reactions))
    world = _with_law(world, rxn)
    agent = ScriptedAgent(lambda obs, sd: (Intervene(lever=rxn, value=9.0), ()), Seed(0))
    record = run(world, task, agent, {}, Seed(5), max_turns=2)
    assert [a.accepted for a in record.action_log] == [False, False]
    assert all("rate law" in a.reason for a in record.action_log)
    assert record.illegal_actions == 2
    # The world keeps its law: the reaction is untouched.
    assert world.chemistry.reactions[rxn].rate_law is not None


@pytest.mark.parametrize("entry_kind", ["str", "mapping"])
def test_a_declared_lever_on_a_rate_law_reaction_is_refused(entry_kind):
    world, task = _pathway_world()
    rxn = next(iter(world.chemistry.reactions))
    world = _with_law(world, rxn)
    entry = rxn if entry_kind == "str" else {"id": rxn, "max_rate": 4}
    with pytest.raises(ValueError, match="rate law"):
        run(world, task, _wait_agent(), {"levers": [entry]}, Seed(5), max_turns=1)


def test_a_numeric_rate_lever_still_intervenes():
    from alienbio.suite.agent import Intervene

    world, task = _pathway_world()
    rxn = next(iter(world.chemistry.reactions))
    agent = ScriptedAgent(lambda obs, sd: (Intervene(lever=rxn, value=9.0), ()), Seed(0))
    record = run(world, task, agent, {"levers": [rxn]}, Seed(5), max_turns=1)
    assert record.action_log[0].accepted
